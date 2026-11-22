# Stripe payments playbook

How to take money without the three classic holes: prices set by the browser, access granted on
the "thank you" page, and webhooks anyone can fake. The two code files below are tested by
Seatbelt's test suite (signature check, duplicate events, unpaid sessions, price from the server).

## Contents

1. Explain the flow to the user
2. What to set up in Stripe
3. Database tables
4. Start a payment (server)
5. Confirm a payment (webhook, server)
6. The success page
7. Subscriptions
8. Testing, then going live
9. Costs
10. Mistakes to watch for

## 1. Explain the flow to the user

> When someone pays, they go to Stripe's own secure payment page, so card details never touch
> your app. Afterwards, Stripe sends your app a signed message (a **webhook**) saying "this
> payment succeeded". Only that signed message marks the booking as paid. The "thank you" page
> just says thanks, because anyone could visit it without paying.

## 2. What to set up in Stripe

1. Create the product and price in the Stripe dashboard (**Product catalogue > Add product**).
   Copy the **price ID** (starts `price_`). The app sends this ID, never an amount.
2. Keys: **Developers > API keys**. The secret key (`sk_test_...`, later `sk_live_...`) goes in
   server env vars only, as `STRIPE_SECRET_KEY`.
3. Webhook endpoint: **Developers > Webhooks** (Workbench in newer dashboards) > add endpoint
   with your live URL, for example `https://yourdomain.com/api/webhooks/stripe`, listening to
   `checkout.session.completed`. Copy its signing secret (`whsec_...`) into
   `STRIPE_WEBHOOK_SECRET`. Test mode and live mode endpoints have different secrets.

## 3. Database tables

Uses the `services` and `bookings` tables from `supabase.md` patterns 3 and 4, plus a price ID on
each service and a table that remembers which Stripe events were already handled:

```sql
alter table public.services add column stripe_price_id text;

create table public.stripe_events (
  id text primary key,
  received_at timestamptz not null default now()
);
alter table public.stripe_events enable row level security;
-- No policies: only server code with the service role touches this table.
```

## 4. Start a payment (server)

Next.js App Router example. The page calls `POST /api/checkout` with the booking ID and the
user's login token. The server looks up the booking and price itself.

<!-- test: checkout_route -->
```ts
// app/api/checkout/route.ts  (server only: never import this into a page component)
import Stripe from "stripe";
import { createClient } from "@supabase/supabase-js";

const stripe = new Stripe(process.env.STRIPE_SECRET_KEY!);
const admin = createClient(process.env.SUPABASE_URL!, process.env.SUPABASE_SERVICE_ROLE_KEY!, {
  auth: { persistSession: false },
});

export async function POST(req: Request) {
  // 1. Who is asking? Check the login token on the server.
  const token = (req.headers.get("authorization") ?? "").replace("Bearer ", "");
  const { data: auth } = await admin.auth.getUser(token);
  if (!auth?.user) return Response.json({ error: "Please log in" }, { status: 401 });

  // 2. Which booking? Only trust the ID, and check it belongs to this user.
  const { bookingId } = await req.json();
  const { data: booking } = await admin
    .from("bookings")
    .select("id, user_id, status, services(stripe_price_id)")
    .eq("id", bookingId)
    .single();
  if (!booking || booking.user_id !== auth.user.id) {
    return Response.json({ error: "Booking not found" }, { status: 404 });
  }
  if (booking.status !== "pending") {
    return Response.json({ error: "This booking is already paid or cancelled" }, { status: 409 });
  }

  // 3. The price comes from your database, never from the browser.
  const session = await stripe.checkout.sessions.create({
    mode: "payment",
    line_items: [{ price: booking.services.stripe_price_id, quantity: 1 }],
    client_reference_id: auth.user.id,
    metadata: { booking_id: booking.id },
    success_url: `${process.env.SITE_URL}/booking/thanks?session_id={CHECKOUT_SESSION_ID}`,
    cancel_url: `${process.env.SITE_URL}/booking/${booking.id}`,
  });
  return Response.json({ url: session.url });
}
```

## 5. Confirm a payment (webhook, server)

<!-- test: webhook_route -->
```ts
// app/api/webhooks/stripe/route.ts
import Stripe from "stripe";
import { createClient } from "@supabase/supabase-js";

const stripe = new Stripe(process.env.STRIPE_SECRET_KEY!);
const admin = createClient(process.env.SUPABASE_URL!, process.env.SUPABASE_SERVICE_ROLE_KEY!, {
  auth: { persistSession: false },
});

export async function POST(req: Request) {
  // 1. Prove the message really came from Stripe. Needs the raw body, so use req.text().
  const body = await req.text();
  const signature = req.headers.get("stripe-signature") ?? "";
  let event: Stripe.Event;
  try {
    event = stripe.webhooks.constructEvent(body, signature, process.env.STRIPE_WEBHOOK_SECRET!);
  } catch {
    return new Response("Signature check failed", { status: 400 });
  }

  // 2. Stripe can send the same event more than once. Remember each one and skip repeats.
  const { error: seenError } = await admin.from("stripe_events").insert({ id: event.id });
  if (seenError) {
    if (seenError.code === "23505") return new Response("Already handled", { status: 200 });
    return new Response("Database error", { status: 500 }); // Stripe will retry later
  }

  // 3. Only now change anything.
  if (event.type === "checkout.session.completed") {
    const session = event.data.object as Stripe.Checkout.Session;
    if (session.payment_status === "paid" && session.metadata?.booking_id) {
      await admin
        .from("bookings")
        .update({ status: "paid" })
        .eq("id", session.metadata.booking_id)
        .eq("user_id", session.client_reference_id);
    }
  }
  return new Response("ok", { status: 200 });
}
```

Other setups, same logic:
- **Express:** register the webhook route **before** `app.use(express.json())`, with
  `express.raw({ type: "application/json" })`, and pass `req.body` (a Buffer) to `constructEvent`.
- **Supabase Edge Function (Deno), common with Lovable:** read `await req.text()`, then use
  `await stripe.webhooks.constructEventAsync(body, signature, secret, undefined,
  Stripe.createSubtleCryptoProvider())`, because Deno needs the async version.
- **Lovable, Bolt, Replit:** ask the builder: "Create a server-side Stripe webhook that verifies
  the signature with the webhook signing secret from Secrets, records event IDs to skip repeats,
  and marks the booking paid only when payment_status is paid. Do not change the booking status
  anywhere else."

## 6. The success page

Show "Thanks! Confirming your payment..." and read the booking status from the database (refresh
every few seconds until it says paid). Never update anything from this page.

## 7. Subscriptions

Use `mode: "subscription"`, then keep the user's plan in the `entitlements` table
(`supabase.md` pattern 5). Update it only from webhooks: `checkout.session.completed` (start),
`customer.subscription.updated` and `customer.subscription.deleted` (changes and cancellations),
and `invoice.payment_failed` (tell the user). Let customers manage billing through Stripe's
**customer portal** rather than building your own.

## 8. Testing, then going live

1. Stay in **test mode** until everything works. Test card: `4242 4242 4242 4242`, any future
   date, any CVC.
2. On your computer: `stripe listen --forward-to localhost:3000/api/webhooks/stripe` (the
   Stripe CLI prints a separate `whsec_` secret for this).
3. Try: a successful payment (booking becomes paid), a cancelled payment (stays pending), and
   visiting the thanks page without paying (stays pending).
4. Going live: switch to live keys, create the **live** webhook endpoint, put its new signing
   secret in the host's env vars, redeploy, and make one real small payment, then refund it.

## 9. Costs

Stripe charges a fee per successful payment (a percentage plus a small fixed amount, varying by
country and card type). Check the current rates on Stripe's pricing page for your country and
include them in the user's price. There is no monthly fee for standard Checkout.

## 10. Mistakes to watch for

- Amount or price sent from the browser. Always use a price ID looked up on the server.
- Booking marked paid, or Pro granted, on the success page or in the browser.
- Webhook without `constructEvent`, or with the check removed "to make it work".
- JSON parsed before the signature check (breaks the check; use the raw body).
- Test-mode signing secret used with the live endpoint (or the other way round).
- Users able to update their own `status`, `plan` or `credits` (see `supabase.md` query E).
- Card numbers collected by your own form. Always use Stripe Checkout or Stripe Elements.
