// Real Stripe library (so signature checks are genuine), with Checkout creation stubbed out.
import RealStripe from "REAL_STRIPE_PATH";
export default class Stripe extends RealStripe {
  constructor(key, opts) {
    super(key, opts);
    this.checkout = { sessions: { create: async (params) => { globalThis.__created = params; return { url: "https://checkout.stripe.test/s" }; } } };
  }
}
