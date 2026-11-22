"""Runs the TypeScript routes from skills/seatbelt/playbooks/stripe-payments.md with Node.

Needs Node 22.6+ (runs TypeScript by stripping types) and the `stripe` npm package somewhere on
disk. Point SEATBELT_STRIPE at its folder, for example:
    SEATBELT_STRIPE=/tmp/stripetest/node_modules/stripe
Skipped when SEATBELT_STRIPE is not set. No network calls are made.
"""

import os
import re
import shutil
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PLAYBOOK = os.path.join(HERE, "..", "skills", "seatbelt", "playbooks", "stripe-payments.md")
HARNESS = os.path.join(HERE, "stripe_harness")
STRIPE = os.environ.get("SEATBELT_STRIPE")


@unittest.skipUnless(STRIPE and shutil.which("node"), "set SEATBELT_STRIPE to run the Stripe tests")
class StripePlaybook(unittest.TestCase):
    def test_routes(self):
        with open(PLAYBOOK, encoding="utf-8") as fh:
            blocks = dict(re.findall(r"<!-- test: (\w+) -->\n```ts\n(.*?)```", fh.read(), re.S))
        self.assertEqual(set(blocks), {"checkout_route", "webhook_route"})
        d = tempfile.mkdtemp(prefix="seatbelt-stripe-")
        try:
            with open(os.path.join(d, "checkout.ts"), "w") as fh:
                fh.write(blocks["checkout_route"])
            with open(os.path.join(d, "webhook.ts"), "w") as fh:
                fh.write(blocks["webhook_route"])
            shutil.copy(os.path.join(HARNESS, "run.mjs"), d)
            for pkg, src in (("stripe", "fake-stripe.mjs"), ("@supabase/supabase-js", "fake-supabase.mjs")):
                p = os.path.join(d, "node_modules", pkg)
                os.makedirs(p)
                with open(os.path.join(HARNESS, src)) as fh:
                    code = fh.read().replace("REAL_STRIPE_PATH", os.path.join(os.path.abspath(STRIPE), "esm", "stripe.esm.node.js"))
                with open(os.path.join(p, "index.mjs"), "w") as fh:
                    fh.write(code)
                with open(os.path.join(p, "package.json"), "w") as fh:
                    fh.write('{"name": "%s", "type": "module", "exports": "./index.mjs"}' % pkg)
            with open(os.path.join(d, "package.json"), "w") as fh:
                fh.write('{"type": "module"}')
            r = subprocess.run(["node", "--no-warnings", "run.mjs"], cwd=d, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertEqual(r.stdout.count("PASS"), 9, r.stdout)
        finally:
            shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
