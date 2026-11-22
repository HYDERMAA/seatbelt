"""Tests for scripts/check_live.py against local fake websites.

The basic tests need nothing extra. The database tests run the real PostgREST server (the same
software behind Supabase's Data API) against a local PostgreSQL with Supabase-style roles, behind
a tiny gateway that maps a publishable key to the anon role the way Supabase does.
Set SEATBELT_PG (psql connection string) and SEATBELT_POSTGREST (path to the postgrest binary).
"""
import base64
import hashlib
import hmac
import http.server
import json
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import unittest
import urllib.request
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "skills", "seatbelt", "scripts", "check_live.py")
SHIM = os.path.join(HERE, "supabase_shim.sql")
PG = os.environ.get("SEATBELT_PG")
POSTGREST = os.environ.get("SEATBELT_POSTGREST")
JWT_SECRET = "seatbelt-test-secret-that-is-at-least-32-chars"
PUBLISHABLE = "sb_publishable_" + "TeSt" * 6
FAKE_OPENAI = "sk-" + "proj-" + "Ab1" * 12 + "Zz"


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def jwt(payload):
    enc = lambda d: base64.urlsafe_b64encode(json.dumps(d, separators=(",", ":")).encode()).rstrip(b"=").decode()
    head = enc({"alg": "HS256", "typ": "JWT"}) + "." + enc(payload)
    sig = hmac.new(JWT_SECRET.encode(), head.encode(), hashlib.sha256).digest()
    return head + "." + base64.urlsafe_b64encode(sig).rstrip(b"=").decode()


ANON_JWT = jwt({"role": "anon", "iss": "supabase"})


class Site:
    """A fake website plus a Supabase-like gateway in front of PostgREST (if running)."""

    def __init__(self, files, headers=None, spa=True, postgrest_port=None, port=None):
        self.files, self.extra_headers, self.spa, self.pg_port = files, headers or {}, spa, postgrest_port
        self.port = port or free_port()
        self.base = f"http://127.0.0.1:{self.port}"
        site = self

        class H(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_HEAD(self):
                self.do_GET()

            def do_GET(self):
                if self.path.startswith("/rest/v1/") and site.pg_port:
                    return self.gateway()
                path = self.path.split("?")[0]
                body = site.files.get(path)
                if body is None and site.spa and "." not in path.rsplit("/", 1)[-1]:
                    body = site.files.get("/")
                if body is None and site.spa and path.startswith("/.") :
                    body = site.files.get("/")  # many hosts serve index.html for unknown paths
                if body is None:
                    self.send_response(404)
                    self.end_headers()
                    return
                self.send_response(200)
                ctype = "text/html" if path == "/" or body.lstrip().startswith("<") else "application/javascript"
                self.send_header("Content-Type", ctype)
                for k, v in site.extra_headers.items():
                    self.send_header(k, v)
                self.end_headers()
                self.wfile.write(body.encode())

            def gateway(self):
                key = self.headers.get("apikey", "")
                auth = self.headers.get("Authorization")
                if key == PUBLISHABLE and not auth:
                    auth = "Bearer " + ANON_JWT
                if not auth:
                    self.send_response(401)
                    self.end_headers()
                    return
                req = urllib.request.Request(f"http://127.0.0.1:{site.pg_port}{self.path[len('/rest/v1'):]}",
                                             headers={"Authorization": auth, "Prefer": self.headers.get("Prefer", ""),
                                                      "Accept": "application/json"})
                try:
                    with urllib.request.urlopen(req, timeout=10) as r:
                        status, hdrs, body = r.status, r.headers, r.read()
                except urllib.error.HTTPError as e:
                    status, hdrs, body = e.code, e.headers, e.read()
                self.send_response(status)
                if hdrs.get("Content-Range"):
                    self.send_header("Content-Range", hdrs.get("Content-Range"))
                self.end_headers()
                self.wfile.write(body)

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", self.port), H)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


def run(url, *flags):
    r = subprocess.run([sys.executable, SCRIPT, url, "--json", *flags], capture_output=True, text=True, timeout=120)
    return r.returncode, json.loads(r.stdout)


def checks(data):
    return {(f["check"], f["severity"]) for f in data["findings"]}


INDEX = '<!doctype html><html><head><script type="module" src="/assets/index-abc123.js"></script></head><body><div id="root"></div></body></html>'


class BasicLive(unittest.TestCase):
    def test_leaky_site(self):
        js = ('const s=Ke("{api}","{pk}");const ai="{key}";import("./chunk-9.js");\n'
              '//# sourceMappingURL=index-abc123.js.map').format(api="https://abcdefghijklmnopqrst.supabase.co", pk=PUBLISHABLE, key=FAKE_OPENAI)
        site = Site({"/": INDEX, "/assets/index-abc123.js": js,
                     "/assets/chunk-9.js": 'const g="' + "AKIA" + "ABCDEFGHIJKLMNOP" + '";',
                     "/assets/index-abc123.js.map": '{"version":3,"sources":["src/App.tsx"],"mappings":""}',
                     "/.env": "OPENAI_API_KEY=" + FAKE_OPENAI + "\n"})
        try:
            code, data = run(site.base)
        finally:
            site.close()
        found = checks(data)
        self.assertEqual(code, 1)
        self.assertIn(("live-secret", "critical"), found)
        self.assertIn(("live-env-file", "critical"), found)
        self.assertIn(("live-source-map", "medium"), found)
        self.assertIn(("security-headers", "low"), found)
        self.assertNotIn(("live-git-folder", "critical"), found)  # SPA fallback page is not a .git folder
        aws = [f for f in data["findings"] if "AWS" in f["what"]]
        self.assertTrue(aws, "chunk loaded through a dynamic import should be scanned")
        self.assertNotIn(FAKE_OPENAI, json.dumps(data))  # keys are masked in the output
        self.assertTrue(any("--mine" in n for n in data["notes"]))

    def test_clean_site(self):
        js = 'const s=Ke("https://abcdefghijklmnopqrst.supabase.co","{pk}");console.log("hi")'.format(pk=PUBLISHABLE)
        headers = {"Strict-Transport-Security": "max-age=63072000", "Content-Security-Policy": "default-src 'self'; frame-ancestors 'none'",
                   "X-Content-Type-Options": "nosniff", "Referrer-Policy": "strict-origin-when-cross-origin"}
        site = Site({"/": INDEX, "/assets/index-abc123.js": js}, headers=headers)
        try:
            code, data = run(site.base)
        finally:
            site.close()
        self.assertEqual(code, 0, data)
        self.assertEqual([f for f in data["findings"] if f["severity"] in ("critical", "high")], [])

    def test_git_folder_exposed(self):
        site = Site({"/": INDEX, "/.git/HEAD": "ref: refs/heads/main\n", "/assets/index-abc123.js": "1"}, spa=False)
        try:
            code, data = run(site.base)
        finally:
            site.close()
        self.assertIn(("live-git-folder", "critical"), checks(data))

    def test_never_uses_a_leaked_secret_key(self):
        sys.path.insert(0, os.path.dirname(SCRIPT))
        import check_live
        lc = check_live.LiveCheck("http://127.0.0.1:1/")
        lc.texts = {"x": 'f("https://abcdefghijklmnopqrst.supabase.co","' + jwt({"role": "service_role"}) + '").from("users")'}
        url, key, tables, _ = lc.supabase_config()
        self.assertIsNone(key)
        self.assertEqual(tables, ["users"])

    def test_report_file(self):
        site = Site({"/": INDEX, "/assets/index-abc123.js": "const x=1"})
        out = os.path.join(HERE, "..", "dist", "test-live-report.md")
        os.makedirs(os.path.dirname(out), exist_ok=True)
        try:
            subprocess.run([sys.executable, SCRIPT, site.base, "--report", out], capture_output=True, text=True, timeout=60)
        finally:
            site.close()
        with open(out, encoding="utf-8") as fh:
            text = fh.read()
        os.remove(out)
        self.assertIn("# Seatbelt live check", text)
        self.assertIn("private window", text)


@unittest.skipUnless(PG and POSTGREST and shutil.which("psql") and os.path.exists(POSTGREST or ""),
                     "set SEATBELT_PG and SEATBELT_POSTGREST to run the live database tests")
class LiveDatabase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = "seatbelt_live_" + uuid.uuid4().hex[:8]
        admin = lambda sql, db="postgres": subprocess.run(["psql", f"{PG} dbname={db}", "-v", "ON_ERROR_STOP=1", "-qc", sql],
                                                          check=True, capture_output=True, text=True)
        admin(f"create database {cls.db}")
        with open(SHIM, encoding="utf-8") as fh:
            shim = fh.read()
        import re
        shim = re.sub(r"-- LEGACY_GRANTS_START.*?-- LEGACY_GRANTS_END\n", "", shim, flags=re.S)  # 2026 defaults
        subprocess.run(["psql", f"{PG} dbname={cls.db}", "-v", "ON_ERROR_STOP=1", "-q"], input=shim, check=True,
                       capture_output=True, text=True)
        admin("""
            create table public.profiles (id uuid primary key, full_name text, email text, phone text);
            grant select on public.profiles to anon, authenticated;
            insert into public.profiles values (gen_random_uuid(), 'Amy', 'amy@example.test', '07000'), (gen_random_uuid(), 'Bo', 'bo@example.test', '07001');
            create table public.notes (id uuid primary key default gen_random_uuid(), user_id uuid, body text);
            grant select, insert on public.notes to authenticated;
            alter table public.notes enable row level security;
            create policy own on public.notes for select to authenticated using (auth.uid() = user_id);
            insert into public.notes (user_id, body) values (gen_random_uuid(), 'private');
            create table public.services (id serial primary key, name text);
            grant select on public.services to anon;
            alter table public.services enable row level security;
            create policy pub on public.services for select to anon using (true);
            insert into public.services (name) values ('Haircut');
            create table public.orders (id int, total int);
            insert into public.orders values (1, 100);
            create table public.bookings (id int, slot text);
            grant select on public.bookings to anon;
            insert into public.bookings values (1, 'Mon 10:00');
        """, db=cls.db)
        cls.pg_port = free_port()
        conf = os.path.join(HERE, "..", "dist", f"postgrest-{cls.db}.conf")
        os.makedirs(os.path.dirname(conf), exist_ok=True)
        dsn = dict(p.split("=", 1) for p in PG.split())
        with open(conf, "w") as fh:
            fh.write(f'db-uri = "postgres://{dsn.get("user", "postgres")}@/{cls.db}?host={dsn.get("host", "/tmp")}&port={dsn.get("port", "5432")}"\n'
                     f'db-schemas = "public"\ndb-anon-role = "anon"\njwt-secret = "{JWT_SECRET}"\n'
                     f'server-port = {cls.pg_port}\nserver-host = "127.0.0.1"\n')
        cls.conf = conf
        cls.proc = subprocess.Popen([POSTGREST, conf], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(50):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{cls.pg_port}/", timeout=1)
                break
            except urllib.error.HTTPError:
                break
            except Exception:
                time.sleep(0.2)
        cls.admin = staticmethod(admin)

    @classmethod
    def tearDownClass(cls):
        cls.proc.terminate()
        cls.proc.wait(timeout=10)
        os.remove(cls.conf)
        cls.admin(f"drop database if exists {cls.db} with (force)")

    def site(self, key):
        port = free_port()
        js = ('const c=Ke("http://127.0.0.1:{p}","{k}");c.from("profiles").select();c.from("notes").select();'
              'c.from("services").select();c.from("orders").select();c.from("bookings").select();c.storage.from("avatars").upload(f)').format(p=port, k=key)
        return Site({"/": INDEX, "/assets/index-abc123.js": js}, postgrest_port=self.pg_port, port=port)

    def check_results(self, key):
        s = self.site(key)
        try:
            code, data = run(s.base, "--mine")
        finally:
            s.close()
        return code, data

    def test_publishable_key(self):
        code, data = self.check_results(PUBLISHABLE)
        self.assertEqual(code, 1)
        open_tables = {f["file"]: f for f in data["findings"] if f["check"] == "live-table-open"}
        self.assertEqual(set(open_tables), {"table profiles", "table services", "table bookings"})
        self.assertEqual(open_tables["table bookings"]["severity"], "high")   # personal-sounding table name
        self.assertEqual(open_tables["table profiles"]["severity"], "critical")   # email and phone columns
        self.assertIn("2 rows", open_tables["table profiles"]["what"])
        self.assertEqual(open_tables["table services"]["severity"], "medium")  # looks like public content
        self.assertNotIn("amy@example.test", json.dumps(data))                  # never shows the data
        db = " ".join(data["database"])
        self.assertTrue("notes: refused" in db or "notes: answered with no rows" in db, db)
        self.assertIn("orders: refused", db)   # RLS off, but no grant under the 2026 defaults
        self.assertTrue(any("avatars" in n for n in data["notes"]))

    def test_legacy_anon_jwt(self):
        code, data = self.check_results(ANON_JWT)
        self.assertIn(("live-table-open", "critical"), checks(data))

    def test_without_mine_flag_no_database_requests(self):
        s = self.site(PUBLISHABLE)
        try:
            code, data = run(s.base)
        finally:
            s.close()
        self.assertEqual(data["database"], [])


if __name__ == "__main__":
    unittest.main()
