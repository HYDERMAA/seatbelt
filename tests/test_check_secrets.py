"""Tests for skills/seatbelt/scripts/check_secrets.py.

Fake keys are built from pieces at run time so this file never contains anything that looks
like a real secret (and does not trip GitHub's secret scanning).
Run: python3 -m unittest discover -s tests
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "skills", "seatbelt", "scripts", "check_secrets.py")

FAKE_OPENAI = "sk-" + "proj-" + "A1b2C3d4" * 5
FAKE_GOOGLE = "AI" + "za" + "Sy" + "B" * 33
FAKE_STRIPE_LIVE = "sk_" + "live_" + "4eC39HqLyjWDarjtT1zdp7dc" + "X" * 4
FAKE_STRIPE_TEST = "sk_" + "test_" + "4eC39HqLyjWDarjtT1zdp7dc"
FAKE_AWS = "AK" + "IA" + "IOSFODNN7EXAMPLE"[:16].upper().ljust(16, "Q")


def fake_service_role_jwt():
    import base64

    def b64(d):
        return base64.urlsafe_b64encode(json.dumps(d).encode()).decode().rstrip("=")

    return b64({"alg": "HS256", "typ": "JWT"}) + "." + b64({"iss": "supabase", "role": "service_role"}) + "." + "s" * 43


def fake_anon_jwt():
    import base64

    def b64(d):
        return base64.urlsafe_b64encode(json.dumps(d).encode()).decode().rstrip("=")

    return b64({"alg": "HS256", "typ": "JWT"}) + "." + b64({"iss": "supabase", "role": "anon"}) + "." + "a" * 43


class ScannerTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="seatbelt-test-")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def write(self, rel, text):
        path = os.path.join(self.dir, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)

    def run_scan(self, *extra):
        r = subprocess.run([sys.executable, SCRIPT, self.dir, "--json", *extra], capture_output=True, text=True)
        data = json.loads(r.stdout)
        return r.returncode, data

    def checks(self, data):
        return {(f["check"], f["severity"]) for f in data["findings"]}

    def git(self, *args):
        subprocess.run(["git", "-C", self.dir, *args], check=True, capture_output=True)

    def test_clean_project_passes(self):
        self.write(".gitignore", ".env\n.env.*\n!.env.example\nnode_modules/\n")
        self.write("src/App.jsx", "export default function App(){ return <h1>Hello</h1> }\n")
        self.write(".env.example", "OPENAI_API_KEY=your-key-here\n")
        code, data = self.run_scan()
        self.assertEqual(code, 0, data)
        self.assertTrue(data["ready"])
        self.assertEqual(data["findings"], [])

    def test_key_in_frontend_is_critical(self):
        self.write("src/chat.js", f'const key = "{FAKE_OPENAI}";\n')
        code, data = self.run_scan()
        self.assertEqual(code, 1)
        self.assertIn(("openai-key", "critical"), self.checks(data))
        # the full key must never be printed
        self.assertNotIn(FAKE_OPENAI, json.dumps(data))

    def test_key_in_server_code_is_high(self):
        self.write("api/chat.js", f'const key = "{FAKE_GOOGLE}";\n')
        code, data = self.run_scan()
        self.assertEqual(code, 1)
        self.assertIn(("google-api-key", "high"), self.checks(data))

    def test_stripe_live_and_test(self):
        self.write("server/pay.py", f'LIVE = "{FAKE_STRIPE_LIVE}"\nTEST = "{FAKE_STRIPE_TEST}"\n')
        code, data = self.run_scan()
        found = self.checks(data)
        self.assertIn(("stripe-live-secret", "high"), found)
        self.assertIn(("stripe-test-secret", "medium"), found)

    def test_aws_key_detected(self):
        self.write("deploy/config.yml", f"aws_key: {FAKE_AWS}\n")
        code, data = self.run_scan()
        self.assertIn("aws-access-key", {c for c, _ in self.checks(data)})

    def test_service_role_jwt_detected_but_anon_ignored(self):
        self.write("server/db.js", f'const admin = "{fake_service_role_jwt()}";\n')
        self.write("src/supabase.js", f'const anon = "{fake_anon_jwt()}";\n')
        code, data = self.run_scan()
        files = {(f["check"], f["file"]) for f in data["findings"]}
        self.assertIn(("supabase-service-role-jwt", "server/db.js"), files)
        self.assertFalse(any(f == "src/supabase.js" for _, f in files), data)

    def test_service_role_word_in_frontend(self):
        self.write("src/admin.tsx", "const k = import.meta.env.VITE_SUPABASE_SERVICE_ROLE_KEY\n")
        code, data = self.run_scan()
        found = self.checks(data)
        self.assertIn(("service-role-in-frontend", "critical"), found)
        self.assertIn(("secret-behind-public-prefix", "high"), found)

    def test_public_prefix_anon_is_fine(self):
        self.write(".gitignore", ".env\n")
        self.write("src/lib.ts", "const u = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY\n")
        code, data = self.run_scan()
        self.assertEqual(code, 0, data)

    def test_public_prefix_secret_flagged(self):
        self.write("src/ai.ts", "const k = process.env.NEXT_PUBLIC_OPENAI_API_KEY\n")
        code, data = self.run_scan()
        self.assertIn(("secret-behind-public-prefix", "high"), self.checks(data))

    def test_env_not_ignored_without_git(self):
        self.write(".env", f"OPENAI_API_KEY={FAKE_OPENAI}\n")
        code, data = self.run_scan()
        self.assertIn(("env-file-not-ignored", "high"), self.checks(data))

    def test_env_ignored_is_fine(self):
        self.write(".gitignore", ".env\n")
        self.write(".env", f"OPENAI_API_KEY={FAKE_OPENAI}\n")
        code, data = self.run_scan()
        self.assertEqual(code, 0, data)

    @unittest.skipUnless(shutil.which("git"), "git not installed")
    def test_env_tracked_in_git_is_critical(self):
        self.git("init", "-q")
        self.write(".env", f"OPENAI_API_KEY={FAKE_OPENAI}\n")
        self.git("add", ".env")
        code, data = self.run_scan()
        self.assertEqual(code, 1)
        self.assertIn(("env-file-saved-in-git", "critical"), self.checks(data))

    @unittest.skipUnless(shutil.which("git"), "git not installed")
    def test_git_without_gitignore(self):
        self.git("init", "-q")
        self.write("index.html", "<h1>hi</h1>\n")
        code, data = self.run_scan()
        self.assertIn(("no-gitignore", "medium"), self.checks(data))
        self.assertEqual(code, 0)

    @unittest.skipUnless(shutil.which("git"), "git not installed")
    def test_example_env_variants_are_fine(self):
        self.git("init", "-q")
        self.write(".gitignore", ".env\n.env.local\n")
        for n in (".env.local.example", ".env.sample", "app/.env.template"):
            self.write(n, "OPENAI_API_KEY=\n")
            self.git("add", n)
        code, data = self.run_scan()
        self.assertEqual(code, 0, data)

    def test_real_key_in_example_env(self):
        self.write(".gitignore", ".env\n")
        self.write(".env.example", f"OPENAI_API_KEY={FAKE_OPENAI}\n")
        code, data = self.run_scan()
        self.assertIn(("real-key-in-example", "high"), self.checks(data))

    def test_supabase_table_without_rls(self):
        self.write("supabase/migrations/001.sql",
                   "create table public.notes (id uuid primary key, user_id uuid, body text);\n"
                   "create table public.profiles (id uuid primary key);\n"
                   "alter table public.profiles enable row level security;\n"
                   "create policy p on public.profiles for select using (true);\n")
        code, data = self.run_scan()
        found = {(f["check"], f["what"].split("'")[1] if "'" in f["what"] else "") for f in data["findings"]}
        self.assertIn(("table-without-rls", "public.notes"), found)
        self.assertNotIn(("table-without-rls", "public.profiles"), found)
        self.assertIn("policy-allows-everyone", {c for c, _ in self.checks(data)})

    def test_rls_enabled_in_later_migration(self):
        self.write("supabase/migrations/001.sql", "create table public.notes (id uuid);\n")
        self.write("supabase/migrations/002.sql", "alter table public.notes enable row level security;\n")
        code, data = self.run_scan()
        self.assertNotIn("table-without-rls", {c for c, _ in self.checks(data)}, data)

    def test_ai_client_in_browser(self):
        self.write("src/ai.js", "const c = new OpenAI({ apiKey: k, dangerouslyAllowBrowser: true })\n")
        code, data = self.run_scan()
        self.assertIn(("ai-key-in-browser", "high"), self.checks(data))

    def test_rls_before_create(self):
        self.write("supabase/migrations/001.sql",
                   "-- Enable RLS\nalter table if exists notes enable row level security;\n"
                   "create table if not exists notes (id uuid primary key, user_id uuid);\n")
        code, data = self.run_scan()
        self.assertIn(("rls-before-create", "high"), self.checks(data))
        self.assertNotIn("table-without-rls", {c for c, _ in self.checks(data)})

    def test_user_can_edit_entitlement(self):
        self.write("supabase/migrations/001.sql",
                   "create table public.profiles (id uuid primary key, is_pro boolean default false);\n"
                   "alter table public.profiles enable row level security;\n"
                   "create policy \"own\" on public.profiles for update using (auth.uid() = id);\n")
        code, data = self.run_scan()
        self.assertIn(("user-can-edit-entitlement", "high"), self.checks(data))

    def test_entitlement_guarded_by_column_grants(self):
        self.write("supabase/migrations/001.sql",
                   "create table public.profiles (id uuid primary key, display_name text, role text);\n"
                   "alter table public.profiles enable row level security;\n"
                   "create policy \"own\" on public.profiles for update using (auth.uid() = id);\n"
                   "revoke update on public.profiles from anon, authenticated;\n"
                   "grant update (display_name) on public.profiles to authenticated;\n")
        code, data = self.run_scan()
        self.assertEqual(code, 0, data)

    def test_public_bucket_and_definer(self):
        self.write("schema.sql",
                   "insert into storage.buckets (id, name, public) values ('cv', 'cv', true);\n"
                   "create function public.f() returns int language sql security definer as $$ select 1 $$;\n")
        code, data = self.run_scan()
        found = self.checks(data)
        self.assertIn(("public-bucket", "medium"), found)
        self.assertIn(("definer-without-search-path", "medium"), found)

    def test_playbook_code_scans_clean(self):
        import re as _re
        book = os.path.join(HERE, "..", "skills", "seatbelt", "playbooks")
        if not os.path.exists(os.path.join(book, "supabase.md")):
            self.skipTest("playbooks folder not found")
        with open(os.path.join(book, "supabase.md")) as fh:
            sql = _re.findall(r"```sql\n(.*?)```", fh.read(), _re.S)
        self.write("supabase/migrations/001_all.sql", "\n".join(sql))
        with open(os.path.join(book, "stripe-payments.md")) as fh:
            ts = dict(_re.findall(r"<!-- test: (\w+) -->\n```ts\n(.*?)```", fh.read(), _re.S))
        self.write("app/api/checkout/route.ts", ts["checkout_route"])
        self.write("app/api/webhooks/stripe/route.ts", ts["webhook_route"])
        self.write(".gitignore", ".env\n")
        code, data = self.run_scan()
        serious = [f for f in data["findings"] if f["severity"] in ("critical", "high")]
        self.assertEqual(serious, [], serious)

    def test_false_positive_guards(self):
        self.write("supabase/migrations/001.sql",
                   "create table public.chat_messages (id uuid primary key, user_id uuid, role text, content text);\n"
                   "alter table public.chat_messages enable row level security;\n"
                   "create policy \"own\" on public.chat_messages for all using (auth.uid() = user_id);\n")
        self.write("src/Help.tsx", "<p>Paste the anon key here, never the service_role key</p>\n")
        self.write("db/schema.sql", "create table jobs (id int);\n")
        self.write("src/i18n/en.ts", 'export default { "auth.password": "Password1!" }\n')
        self.write(".gitignore", ".env\n")
        code, data = self.run_scan()
        self.assertEqual(code, 0, data)
        found = self.checks(data)
        self.assertIn(("service-role-in-frontend", "medium"), found)
        self.assertIn(("table-without-rls", "medium"), found)
        self.assertNotIn("user-can-edit-entitlement", {c for c, _ in found})
        self.assertNotIn("hardcoded-password", {c for c, _ in found})

    def test_webhook_not_verified(self):
        self.write("app/api/webhooks/stripe/route.ts",
                   "import Stripe from 'stripe';\nexport async function POST(req){ const e = await req.json(); }\n")
        code, data = self.run_scan()
        self.assertIn(("webhook-not-verified", "high"), self.checks(data))

    def test_success_page_grant(self):
        self.write("src/pages/Success.tsx", "await supabase.from('profiles').update({ is_pro: true }).eq('id', user.id)\n")
        code, data = self.run_scan()
        self.assertIn(("success-page-grant", "high"), self.checks(data))

    def test_cors_and_debug(self):
        self.write("server/index.js", "app.use(cors({ origin: '*', credentials: true }))\n")
        self.write("server/app.py", "app.run(host='0.0.0.0', debug=True)\n")
        code, data = self.run_scan()
        found = self.checks(data)
        self.assertIn(("cors-open", "high"), found)
        self.assertIn(("debug-mode", "high"), found)

    def test_ai_in_browser(self):
        self.write("src/chat.ts", "const ai = new OpenAI({ apiKey: k, dangerouslyAllowBrowser: true })\n")
        code, data = self.run_scan()
        self.assertIn(("ai-key-in-browser", "high"), self.checks(data))

    def test_cost_guard(self):
        self.write("supabase/functions/ask/index.ts",
                   'import OpenAI from "openai";\nconst ai = new OpenAI({ apiKey: Deno.env.get("OPENAI_API_KEY") });\n'
                   'Deno.serve(async (req) => {\n  const { q } = await req.json();\n'
                   '  const r = await ai.chat.completions.create({ model: "gpt-4o-mini", messages: [{ role: "user", content: q }] });\n'
                   '  return new Response(r.choices[0].message.content);\n});\n')
        self.write("app/api/summarise/route.ts",
                   'import Anthropic from "@anthropic-ai/sdk";\nimport { ratelimit } from "@/lib/limit";\n'
                   'export async function POST(req) {\n  const user = await auth.getUser();\n  await ratelimit.limit(user.id);\n'
                   '  for (const doc of docs) {\n    await client.messages.create({ model: "claude", max_tokens: 300, messages: [] });\n  }\n}\n')
        self.write("vercel.json", '{"crons": [{"path": "/api/summarise", "schedule": "* * * * *"}]}')
        code, data = self.run_scan()
        found = self.checks(data)
        self.assertIn(("cost-ai-no-limit", "medium"), found)
        self.assertIn(("cost-no-max-tokens", "low"), found)
        self.assertIn(("cost-ai-in-loop", "low"), found)
        self.assertIn(("cost-frequent-cron", "medium"), found)
        limited = [f for f in data["findings"] if f["check"] == "cost-ai-no-limit" and f["file"].startswith("app/")]
        self.assertEqual(limited, [])
        edge = [f for f in data["findings"] if f["check"] == "cost-ai-no-limit"][0]
        self.assertIn("public key", edge["why"])
        self.assertEqual(sorted(data["paid_services"]), ["Anthropic", "OpenAI"])

    def test_hardcoded_password(self):
        self.write("server/db.js", 'const dbPassword = "Tr0ub4dor-horse";\nconst p = process.env.DB_PASSWORD;\n')
        self.write("server/form.js", 'const label = { password: "your-password" };\nconst secretName = "STRIPE_SECRET_KEY";\n'
                   'const passwordField = "current-password";\n')
        code, data = self.run_scan()
        hits = [f for f in data["findings"] if f["check"] == "hardcoded-password"]
        self.assertEqual([(f["file"], f["line"]) for f in hits], [("server/db.js", 1)])

    def test_env_in_public_folder(self):
        self.write(".gitignore", ".env\n")
        self.write("public/.env", "X=1\n")
        code, data = self.run_scan()
        self.assertIn(("env-file-public", "critical"), self.checks(data))

    def test_source_maps_in_build(self):
        self.write("dist/assets/index.js.map", "{}")
        code, data = self.run_scan()
        self.assertIn(("public-source-maps", "low"), self.checks(data))

    def test_firebase_test_mode(self):
        self.write("firestore.rules", "allow read, write: if request.time < timestamp.date(2026, 12, 1);\n")
        code, data = self.run_scan()
        self.assertIn(("firebase-test-mode", "high"), self.checks(data))

    def test_use_client_marks_frontend(self):
        self.write("lib/ai.ts", f'"use client";\nconst k = "{FAKE_OPENAI}";\n')
        code, data = self.run_scan()
        self.assertIn(("openai-key", "critical"), self.checks(data))

    @unittest.skipUnless(shutil.which("git"), "git not installed")
    def test_env_in_git_history(self):
        self.git("init", "-q")
        self.git("config", "user.email", "t@example.com")
        self.git("config", "user.name", "t")
        self.write(".env", "X=1\n")
        self.git("add", ".env")
        self.git("commit", "-qm", "oops")
        self.git("rm", "-q", "--cached", ".env")
        self.write(".gitignore", ".env\n")
        self.git("add", ".gitignore")
        self.git("commit", "-qm", "fix")
        code, data = self.run_scan()
        self.assertIn(("env-file-in-git-history", "critical"), self.checks(data))

    def test_reports(self):
        self.write("src/chat.js", f'const key = "{FAKE_OPENAI}";\n')
        out = tempfile.mkdtemp()
        try:
            md, html = os.path.join(out, "r.md"), os.path.join(out, "r.html")
            subprocess.run([sys.executable, SCRIPT, self.dir, "--report", md], capture_output=True)
            subprocess.run([sys.executable, SCRIPT, self.dir, f"--report={html}", "--json"], capture_output=True)
            with open(md) as a, open(html) as b:
                md_text, html_text = a.read(), b.read()
            self.assertIn("NOT READY", md_text)
            self.assertIn("Still to check by hand", md_text)
            self.assertNotIn(FAKE_OPENAI, md_text + html_text)
            self.assertIn("<!doctype html>", html_text)
            self.assertIn("Must fix now", html_text)
        finally:
            shutil.rmtree(out)

    def test_audit_flag_without_lockfile(self):
        r = subprocess.run([sys.executable, SCRIPT, self.dir, "--audit", "--json"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_rls_disabled(self):
        self.write("schema.sql", "alter table orders disable row level security;\n")
        code, data = self.run_scan()
        self.assertIn(("rls-disabled", "high"), self.checks(data))

    def test_firebase_open_rules(self):
        self.write("firestore.rules", "service cloud.firestore {\n match /{d=**} {\n  allow read, write: if true;\n }\n}\n")
        code, data = self.run_scan()
        self.assertIn(("firebase-open-rules", "high"), self.checks(data))

    def test_db_url_with_password(self):
        self.write("server/db.js", 'const url = "' + "postgresql://" + "admin:S3cretPass" + "@db.myhost.net:5432/app" + '";\n')
        self.write("README.md", "Use postgres://user:your-password@host/db\n")
        code, data = self.run_scan()
        files = {f["file"] for f in data["findings"] if f["check"] == "db-url-password"}
        self.assertEqual(files, {"server/db.js"})

    def test_ignore_comment(self):
        self.write("src/chat.js", f'const key = "{FAKE_OPENAI}"; // seatbelt-ignore\n')
        code, data = self.run_scan()
        self.assertEqual(code, 0, data)

    def test_node_modules_skipped(self):
        self.write("node_modules/pkg/index.js", f'const key = "{FAKE_OPENAI}";\n')
        code, data = self.run_scan()
        self.assertEqual(code, 0, data)

    def test_plain_text_report_and_usage(self):
        self.write("src/chat.js", f'const key = "{FAKE_OPENAI}";\n')
        r = subprocess.run([sys.executable, SCRIPT, self.dir], capture_output=True, text=True)
        self.assertEqual(r.returncode, 1)
        self.assertIn("MUST FIX NOW", r.stdout)
        self.assertIn("NOT READY", r.stdout)
        r2 = subprocess.run([sys.executable, SCRIPT, os.path.join(self.dir, "missing")], capture_output=True, text=True)
        self.assertEqual(r2.returncode, 2)
        r3 = subprocess.run([sys.executable, SCRIPT, "--bogus"], capture_output=True, text=True)
        self.assertEqual(r3.returncode, 2)


if __name__ == "__main__":
    unittest.main()
