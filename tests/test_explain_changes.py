"""Tests for scripts/explain_changes.py using throwaway git repos and a fake package registry."""
import http.server
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "skills", "seatbelt", "scripts", "explain_changes.py")
FAKE_OPENAI = "sk-" + "proj-" + "Ab1" * 12 + "Zz"


class Registry:
    """Fake npm registry: 'react' and 'stripe' exist and are popular; 'tiny-new-pkg' is new; others 404."""

    def __init__(self):
        class H(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                name = self.path.rsplit("/", 1)[-1]
                known = {"react": ("2013-05-29T00:00:00Z", 30000000), "stripe": ("2011-01-01T00:00:00Z", 4000000),
                         "tiny-new-pkg": ("2026-11-10T00:00:00Z", 12)}
                if self.path.startswith("/downloads/"):
                    body = {"downloads": known.get(name, ("", 0))[1]}
                elif name in known:
                    body = {"name": name, "time": {"created": known[name][0]}}
                else:
                    self.send_response(404)
                    self.end_headers()
                    return
                self.send_response(200)
                self.end_headers()
                self.wfile.write(json.dumps(body).encode())

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


class ExplainChanges(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="seatbelt-explain-")
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "t@example.test")
        self.git("config", "user.name", "Test")
        self.write(".gitignore", "node_modules\n")
        self.write("package.json", '{\n  "name": "app",\n  "dependencies": {\n    "react": "^18.0.0"\n  }\n}\n')
        self.write("src/App.tsx", "export default function App() { return <h1>Hi</h1> }\n")
        self.write("app/api/webhook/route.ts", "const event = stripe.webhooks.constructEvent(body, sig, secret);\nawait grant(event);\n")
        self.write("supabase/migrations/001.sql", "create table notes (id int);\nalter table notes enable row level security;\n")
        self.git("add", "-A")
        self.git("commit", "-qm", "first save point")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def git(self, *args):
        subprocess.run(["git", "-C", self.dir, *args], check=True, capture_output=True)

    def write(self, rel, text):
        path = os.path.join(self.dir, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)

    def run_it(self, *flags, env=None):
        e = dict(os.environ, **(env or {}))
        r = subprocess.run([sys.executable, SCRIPT, self.dir, "--json", *flags], capture_output=True, text=True, env=e, timeout=60)
        return r.returncode, json.loads(r.stdout)

    def texts(self, data):
        return " | ".join(w["text"] for w in data["warnings"])

    def test_nothing_changed(self):
        code, data = self.run_it()
        self.assertEqual((code, data["changed"], data["risk"]), (0, False, "NONE"))

    def test_small_safe_change(self):
        self.write("src/App.tsx", "export default function App() { return <h1>Hello there</h1> }\n")
        code, data = self.run_it()
        self.assertEqual((code, data["risk"]), (0, "LOW"))
        self.assertIn("pages and design", " ".join(data["facts"]))

    def test_dangerous_changes(self):
        self.write("app/api/webhook/route.ts", "const event = JSON.parse(body);\nawait grant(event);\n")
        self.write("supabase/migrations/002.sql", "alter table notes disable row level security;\ndrop table old_stuff;\n")
        self.write("src/ai.ts", f'const ai = new OpenAI({{ apiKey: "{FAKE_OPENAI}", dangerouslyAllowBrowser: true }})\n')
        self.write(".env.local", "OPENAI_API_KEY=abc\n")
        os.remove(os.path.join(self.dir, "src/App.tsx"))
        code, data = self.run_it()
        t = self.texts(data)
        self.assertEqual((code, data["risk"]), (1, "HIGH"))
        for phrase in ("removes the Stripe signature check", "turns OFF database rules", "deletes a whole table",
                       "OpenAI", "dangerously" if False else "browser", ".env.local is a secrets file", "src/App.tsx is deleted",
                       "back up the data"):
            self.assertIn(phrase, t)
        self.assertNotIn(FAKE_OPENAI, json.dumps(data))

    def test_package_check(self):
        self.write("package.json", '{\n  "name": "app",\n  "dependencies": {\n    "react": "^18.0.0",\n'
                   '    "stripe": "^17.0.0",\n    "react-easy-stripe-checkout-pro": "^1.0.0",\n    "tiny-new-pkg": "1.0.0"\n  }\n}\n')
        reg = Registry()
        try:
            code, data = self.run_it("--check-packages", env={"SEATBELT_NPM_REGISTRY": reg.base,
                                                               "SEATBELT_NPM_DOWNLOADS": reg.base + "/downloads"})
        finally:
            reg.close()
        t = self.texts(data)
        self.assertEqual(data["risk"], "HIGH")
        self.assertIn("'react-easy-stripe-checkout-pro' does not exist", t)
        self.assertIn("'tiny-new-pkg' exists but is little used or very new", t)
        self.assertNotIn("'stripe'", t)

    def test_package_hint_without_flag(self):
        self.write("package.json", '{\n  "name": "app",\n  "dependencies": {\n    "react": "^18.0.0",\n    "zod": "^3.0.0"\n  }\n}\n')
        code, data = self.run_it()
        self.assertIn("--check-packages", self.texts(data))
        self.assertIn("zod", " ".join(data["facts"]))

    def test_reformatted_package_is_not_new(self):
        self.write("package.json", '{\n  "name": "app",\n  "dependencies": {\n    "react": "^18.0.0",\n    "zod": "^3.0.0"\n  }\n}\n')
        code, data = self.run_it()
        facts = " ".join(data["facts"])
        self.assertIn("zod", facts)
        self.assertNotIn("react", facts.split("new packages:")[-1])

    def test_supabase_js_deletes(self):
        self.write("src/admin.ts", 'await supabase.from("notes").delete().neq("id", 0);\n'
                                   'await supabase.from("tags").delete();\n'
                                   'await supabase.from("old").delete().eq("id", oldId);\n')
        code, data = self.run_it()
        t = self.texts(data)
        self.assertIn("wipes almost the whole table", t)
        self.assertIn("check the filter", t)
        self.assertIn("app code", " ".join(data["facts"]))

    def test_not_a_git_folder(self):
        tmp = tempfile.mkdtemp()
        try:
            r = subprocess.run([sys.executable, SCRIPT, tmp], capture_output=True, text=True)
        finally:
            shutil.rmtree(tmp)
        self.assertEqual(r.returncode, 2)
        self.assertIn("first save point", r.stderr)


if __name__ == "__main__":
    unittest.main()
