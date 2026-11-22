# Fixing bugs calmly

The goal is to fix the problem without making three new ones. Professionals debug by narrowing
things down, one change at a time, with a way back.

## Rescue mode, first steps

1. **Does the user need it working right now?** (customers waiting, a demo in an hour). Then go
   back to the last working save point first, publish that, and debug on a copy afterwards.
2. **Save point of the broken state** too, so nothing is lost while you investigate.
3. Follow the two-strikes rule below.

## The two-strikes rule

1. Save point first (if one does not exist for the current state).
2. Get the real error. Do not guess from "it doesn't work".
3. Explain the cause in plain English.
4. One small, focused fix. Check it.
5. Still broken: one more fix with a **different** idea. Check it.
6. Still broken after two attempts: **stop**. Tell the user honestly, roll back to the last
   working save point, and choose a new approach (simpler design, different library, read the
   current official docs, or ask a developer).

Never "fix" an error by deleting data, disabling security (RLS, auth checks), hiding the error,
or removing the feature without asking.

## How to get the real error (tell the user these clicks)

- **Browser console** (where the browser lists errors):
  - Chrome or Edge: right-click the page, **Inspect**, then the **Console** tab.
  - Safari: turn on **Settings > Advanced > Show features for web developers**, then
    **Develop > Show JavaScript Console**.
  - Ask them to copy the red text, or send a screenshot.
- **Network tab** (requests the page makes): same Inspect panel, **Network** tab, reload, click
  the red line, look at **Response**.
- **Terminal:** the last 20 lines after the error.
- **Hosting logs:** Vercel, Netlify, Supabase and Replit all have a Logs page per project.
- **App builders:** copy the error message the builder shows; many have a "Try to fix" button.
  Use it once at most, then follow the two-strikes rule.

## Explain it like this

"The page is trying to load your notes, but the database is saying 'no permission'. That usually
means the safety rules on the notes table do not yet allow signed-in users to read their own
notes. I will add a rule for that, which keeps everyone else locked out."

## Common errors in plain English

| What they see | Usually means | First thing to try |
| --- | --- | --- |
| `401` / `Unauthorized` | Not logged in, or the key is missing | Check the user is signed in and the key is set in env vars |
| `403` / `permission denied` / `new row violates row-level security policy` | Logged in but the rules say no | Add the right RLS or Firebase rule for this action; do not turn RLS off |
| `404` / `Not Found` | Wrong address or file name | Check the URL, route name and spelling |
| `500` / `Internal Server Error` | The server code crashed | Read the server or hosting logs for the real message |
| `CORS` error | The browser blocked a call to another site | Call it from your server function, or allow your own site's address only |
| `undefined is not a function` / `Cannot read properties of undefined` | Code expected something that is not there yet | Check the data has loaded, and the names match |
| `Module not found` | A package is not installed or the import path is wrong | Install the package, check the path |
| `429` / `Too Many Requests` | Hit a rate limit or quota | Wait, slow down, check the provider's limits and billing |
| `Invalid API key` | Wrong, expired or missing key | Re-copy the key into env vars, restart, never paste into code |
| Blank white page | A crash in the frontend | Open the browser console |
| Works locally, broken when live | Env vars not set on the host, or wrong URLs | Add the env vars in the hosting dashboard and redeploy |

## White screen (blank page)

1. Open the browser console (above) and copy the first red error. That is usually the cause.
2. Common causes: a typo or missing import in the last change; a missing environment variable
   (for example `VITE_SUPABASE_URL` not set on the host, so the app crashes on start); data not
   loaded yet; a page that was renamed.
3. If it only happens on the live site, compare the host's environment variables with `.env`
   (names only), then redeploy, because Vite and Next.js copy public variables in at build time.
4. In app builders, use the error the builder shows. Its "fix" button counts as one of your two
   strikes.

## Stripe webhook not working

Never "fix" this by removing the signature check. Check, in order:

1. **Is Stripe sending it?** In the Stripe dashboard, open the webhook endpoint (Developers >
   Webhooks, or Workbench in newer dashboards) and look at recent deliveries and their responses.
2. **Right address?** It must be the live, public URL of the webhook route, not `localhost`.
   For testing on your computer, use the Stripe CLI: `stripe listen --forward-to
   localhost:3000/api/webhooks/stripe`, which prints its own signing secret.
3. **Right secret?** Test mode, live mode and the Stripe CLI each have a different `whsec_`
   signing secret. The one in your env vars must match the endpoint that is sending.
4. **Raw body?** Signature checks need the exact raw request body. Frameworks that parse JSON
   first break the check (Express: use `express.raw` on that route; Next.js App Router: use
   `await req.text()`).
5. **Right events?** The endpoint must be subscribed to the events your code handles (for example
   `checkout.session.completed`).
6. **Answer quickly** with a 2xx status, then do slow work. Stripe retries failed deliveries, so
   handle the same event twice safely (store processed event IDs).
7. Updating the database from the webhook needs server permissions (for example the Supabase
   service role inside the server function), because there is no logged-in user in a webhook.

Full pattern: `playbooks/stripe-payments.md` (Pro).

## Narrowing it down

- What changed since it last worked? Compare with the last save point.
- Can you reproduce it every time? Write down the exact steps.
- Undo half the recent change and see if it goes away (halving finds the cause fast).
- Add a temporary log line to see what the data really is, then remove it.

## Stuck after a rollback?

Offer options, simplest first: a simpler version of the feature, a well-known library or the
platform's built-in feature, or a short review by a developer. Write a short note of what was
tried so nobody repeats it.
