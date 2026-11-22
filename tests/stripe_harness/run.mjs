// Runs the playbook's checkout and webhook routes against real Stripe signature code,
// a fake Supabase client and no network. Prints PASS lines; exits 1 on the first failure.
import assert from "node:assert/strict";
import Stripe from "stripe";
import { db } from "@supabase/supabase-js";

process.env.STRIPE_SECRET_KEY = "sk_test_" + "harness";
process.env.STRIPE_WEBHOOK_SECRET = "whsec_" + "harnesssecret";
process.env.SUPABASE_URL = "http://localhost";
process.env.SUPABASE_SECRET_KEY = "secret-key-for-tests";
process.env.SITE_URL = "https://salon.test";

const { POST: checkout } = await import("./checkout.ts");
const { POST: webhook } = await import("./webhook.ts");
const stripe = new Stripe(process.env.STRIPE_SECRET_KEY);

db.users["tok-A"] = { id: "user-a" };
db.users["tok-B"] = { id: "user-b" };
db.bookings.push({ id: "bk1", user_id: "user-a", status: "pending", services: { stripe_price_id: "price_cut" } });
db.bookings.push({ id: "bk2", user_id: "user-a", status: "pending", services: { stripe_price_id: "price_cut" } });

const ok = (m) => console.log("PASS " + m);
const req = (body, headers = {}) => new Request("https://salon.test/api", { method: "POST", body, headers });

// --- checkout ---
let r = await checkout(req(JSON.stringify({ bookingId: "bk1" })));
assert.equal(r.status, 401); ok("checkout refuses without login");
r = await checkout(req(JSON.stringify({ bookingId: "bk1" }), { authorization: "Bearer tok-B" }));
assert.equal(r.status, 404); ok("checkout refuses someone else's booking");
r = await checkout(req(JSON.stringify({ bookingId: "bk1", price: 1 }), { authorization: "Bearer tok-A" }));
assert.equal(r.status, 200);
assert.deepEqual(globalThis.__created.line_items, [{ price: "price_cut", quantity: 1 }]);
assert.equal(globalThis.__created.metadata.booking_id, "bk1");
assert.equal(globalThis.__created.client_reference_id, "user-a");
ok("checkout uses the server's price ID and ignores a price from the browser");

// --- webhook ---
const event = (id, booking, paid = true) => JSON.stringify({
  id, object: "event", type: "checkout.session.completed",
  data: { object: { object: "checkout.session", payment_status: paid ? "paid" : "unpaid",
    client_reference_id: "user-a", metadata: { booking_id: booking } } },
});
const signed = (payload, secret = process.env.STRIPE_WEBHOOK_SECRET) =>
  req(payload, { "stripe-signature": stripe.webhooks.generateTestHeaderString({ payload, secret }) });

r = await webhook(req(event("evt_forged", "bk1"), { "stripe-signature": "t=1,v1=forged" }));
assert.equal(r.status, 400); assert.equal(db.bookings[0].status, "pending"); ok("forged webhook rejected, booking stays pending");
r = await webhook(signed(event("evt_wrongsecret", "bk1"), "whsec_other"));
assert.equal(r.status, 400); ok("webhook signed with the wrong secret rejected");
r = await webhook(signed(event("evt_unpaid", "bk2", false)));
assert.equal(r.status, 200); assert.equal(db.bookings[1].status, "pending"); ok("unpaid session does not mark paid");
r = await webhook(signed(event("evt_paid", "bk1")));
assert.equal(r.status, 200); assert.equal(db.bookings[0].status, "paid"); ok("verified paid webhook marks the booking paid");
db.bookings[0].status = "refunded-by-staff";
r = await webhook(signed(event("evt_paid", "bk1")));
assert.equal(r.status, 200); assert.equal(db.bookings[0].status, "refunded-by-staff"); ok("repeated event is skipped");
r = await checkout(req(JSON.stringify({ bookingId: "bk1" }), { authorization: "Bearer tok-A" }));
assert.equal(r.status, 409); ok("cannot pay twice for a booking that is no longer pending");
