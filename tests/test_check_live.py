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
import urllib.parse
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
USER_A = "aaaaaaaa-0000-4000-8000-00000000000a"
USER_B = "bbbbbbbb-0000-4000-8000-00000000000b"
LOGINS = {"a@example.test": ("pw-for-a-test", USER_A), "b@example.test": ("pw-for-b-test", USER_B)}
TWO_USERS_ENV = {"SEATBELT_A_EMAIL": "a@example.test", "SEATBELT_A_PASSWORD": "pw-for-a-test",
                 "SEATBELT_B_EMAIL": "b@example.test", "SEATBELT_B_PASSWORD": "pw-for-b-test"}
# Fake storage: 'documents' lets anyone logged in list any folder (a mistake), 'receipts' only your own.
FILES = {"documents": {USER_A: ["cv.pdf"], USER_B: ["passport.pdf"]}, "receipts": {USER_A: ["r1.pdf"], USER_B: ["r2.pdf"]}}


def user_jwt(uid):
    return jwt({"role": "authenticated", "sub": uid, "aud": "authenticated"})


def sub_of(auth):
    try:
        part = auth.split(" ", 1)[1].split(".")[1]
        return json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4))).get("sub")
    except Exception:
        return None


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

            def do_POST(self):
                length = int(self.headers.get("Content-Length") or 0)
                data = json.loads(self.rfile.read(length) or b"{}")
                if self.path.startswith("/auth/v1/token") and self.headers.get("apikey") == PUBLISHABLE:
                    login = LOGINS.get(data.get("email"))
                    if login and login[0] == data.get("password"):
                        return self.reply(200, {"access_token": user_jwt(login[1]), "token_type": "bearer"})
                    return self.reply(400, {"error": "invalid_grant"})
                if self.path.startswith("/storage/v1/object/list/"):
                    bucket = self.path.rsplit("/", 1)[1]
                    me, folder = sub_of(self.headers.get("Authorization", "")), data.get("prefix")
                    names = FILES.get(bucket, {}).get(folder, [])
                    if bucket == "receipts" and me != folder:
                        names = []
                    return self.reply(200, [{"name": n} for n in names])
                self.reply(404, {})

            def reply(self, status, obj):
                body = json.dumps(obj).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)

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


def run(url, *flags, env=None):
    full_env = None
    if env is not None:
        full_env = {k: v for k, v in os.environ.items() if not k.startswith("SEATBELT_")}
        full_env.update(env)
    r = subprocess.run([sys.executable, SCRIPT, url, "--json", *flags], capture_output=True, text=True, timeout=120,
                       env=full_env, stdin=subprocess.DEVNULL)
    if not r.stdout.strip():
        return r.returncode, {"stderr": r.stderr}
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


class TwoUsersBasics(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, os.path.dirname(SCRIPT))
        import check_live
        self.cl = check_live

    def test_needs_mine(self):
        site = Site({"/": INDEX, "/assets/index-abc123.js": "1"})
        try:
            r = subprocess.run([sys.executable, SCRIPT, site.base, "--two-users"], capture_output=True, text=True,
                               timeout=60, stdin=subprocess.DEVNULL)
        finally:
            site.close()
        self.assertEqual(r.returncode, 2)
        self.assertIn("--mine", r.stderr)

    def test_missing_accounts_without_a_terminal(self):
        site = Site({"/": INDEX, "/assets/index-abc123.js": "1"})
        try:
            code, data = run(site.base, "--mine", "--two-users", env={})
        finally:
            site.close()
        self.assertEqual(code, 2)
        self.assertIn("SEATBELT_A_EMAIL", data["stderr"])

    def test_load_accounts(self):
        acc, err = self.cl.load_accounts(env={"SEATBELT_A_TOKEN": "t1", "SEATBELT_B_EMAIL": "b@x.test", "SEATBELT_B_PASSWORD": "p"})
        self.assertIsNone(err)
        self.assertEqual(acc["A"], {"token": "t1"})
        self.assertEqual(acc["B"]["email"], "b@x.test")
        acc, err = self.cl.load_accounts(env=dict(TWO_USERS_ENV, SEATBELT_B_EMAIL="A@example.test"))
        self.assertIsNone(acc)
        self.assertIn("same", err)
        asked = []
        acc, err = self.cl.load_accounts(env={}, ask=lambda prompt, secret: asked.append(secret) or ("pw" if secret else f"x{len(asked)}@y.test"))
        self.assertIsNone(err)
        self.assertEqual(asked, [False, True, False, True])   # passwords asked without showing them

    def test_firebase_between(self):
        """Firestore and Realtime Database, against a small fake of Google's REST endpoints."""
        enc = lambda d: base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()
        fb_token = lambda uid: enc({"alg": "none"}) + "." + enc({"user_id": uid, "sub": uid}) + ".sig"
        users = {"a@example.test": ("pa", "uidA"), "b@example.test": ("pb", "uidB")}
        docs = {"journals": [("j1", {"userId": {"stringValue": "uidA"}, "mood": {"stringValue": "x"}}),
                             ("j2", {"userId": {"stringValue": "uidB"}, "mood": {"stringValue": "y"}})],
                "profiles": [("uidA", {"email": {"stringValue": "a@example.test"}}),
                             ("uidB", {"email": {"stringValue": "b@example.test"}})]}

        class H(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def send(self, st, obj):
                b = json.dumps(obj).encode()
                self.send_response(st)
                self.end_headers()
                self.wfile.write(b)

            def me(self):
                tok = self.headers.get("Authorization", "").replace("Bearer ", "") or \
                    urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query).get("auth", [""])[0]
                try:
                    part = tok.split(".")[1]
                    return json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))["user_id"]
                except Exception:
                    return None

            def do_POST(self):
                d = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                u = users.get(d["email"])
                if u and u[0] == d["password"]:
                    return self.send(200, {"idToken": fb_token(u[1]), "localId": u[1]})
                self.send(400, {"error": {"message": "INVALID_PASSWORD"}})

            def do_GET(self):
                path = urllib.parse.urlsplit(self.path).path
                me = self.me()
                if path.startswith("/rtdb/"):
                    # rules: users/$uid readable only by that uid; notes/$uid readable by anyone logged in (mistake)
                    _, _, top, uid = path[:-5].split("/")
                    ok = (top == "notes" and me) or (top == "users" and me == uid)
                    return self.send(200 if ok else 401, {"x": True} if ok else {"error": "Permission denied"})
                parts = path.split("/documents/")[1].split("/")
                col = parts[0]
                if col == "journals":    # rule mistake: any logged-in user can read all
                    if len(parts) == 1:
                        return self.send(200, {"documents": [{"name": f"p/{col}/{i}", "fields": f} for i, f in docs[col]]})
                    return self.send(404, {})
                if col == "profiles":    # correct: only your own document
                    if len(parts) == 2 and parts[1] == me:
                        return self.send(200, {"name": f"p/profiles/{me}", "fields": dict(docs[col])[me]})
                    return self.send(403, {})
                self.send(404, {})

        srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{srv.server_address[1]}"
        old = self.cl.IDENTITY_BASE, self.cl.FIRESTORE_BASE
        self.cl.IDENTITY_BASE = self.cl.FIRESTORE_BASE = base
        try:
            lc = self.cl.LiveCheck("http://127.0.0.1:1/", mine=True, two_users=True,
                                   accounts={"A": {"email": "a@example.test", "password": "pa"},
                                             "B": {"email": "b@example.test", "password": "pb"}})
            lc.probe_firebase_between(base + "/rtdb", "demo", "AIza" + "x" * 35, {"journals", "profiles"}, {"notes"})
        finally:
            self.cl.IDENTITY_BASE, self.cl.FIRESTORE_BASE = old
            srv.shutdown()
            srv.server_close()
        cross = {f["file"]: f["severity"] for f in lc.findings if f["check"] == "live-cross-user"}
        self.assertEqual(cross.get("firestore journals"), "critical")
        self.assertEqual(cross.get("rtdb notes"), "critical")
        self.assertNotIn("firestore profiles", cross)
        self.assertNotIn("rtdb users", cross)
        self.assertNotIn("uidB", json.dumps(lc.findings))


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
            insert into public.notes (user_id, body) values ('{a}', 'a private'), ('{b}', 'b private');
            -- the classic mistake: logged in, so 'using (true)' looks safe
            create table public.diary (id uuid primary key default gen_random_uuid(), user_id uuid, mood text, body text);
            grant select on public.diary to authenticated;
            alter table public.diary enable row level security;
            create policy any_logged_in on public.diary for select to authenticated using (true);
            insert into public.diary (user_id, mood, body) values ('{a}', 'ok', 'a secret'), ('{b}', 'low', 'b secret');
            -- shared content, meant to be seen by everyone logged in
            create table public.posts (id serial primary key, author_id uuid, caption text);
            grant select on public.posts to authenticated;
            alter table public.posts enable row level security;
            create policy feed on public.posts for select to authenticated using (true);
            insert into public.posts (author_id, caption) values ('{a}', 'my dog'), ('{b}', 'my cat');
            -- owner-only profile with a paid flag
            create table public.members (id uuid primary key, display_name text, is_pro boolean default false);
            grant select on public.members to authenticated;
            alter table public.members enable row level security;
            create policy me on public.members for select to authenticated using ((select auth.uid()) = id);
            insert into public.members values ('{a}', 'A', false), ('{b}', 'B', false);
            -- nobody has used this one yet
            create table public.invoices (id serial primary key, user_id uuid, total int);
            grant select on public.invoices to authenticated;
            alter table public.invoices enable row level security;
            create policy mine on public.invoices for select to authenticated using ((select auth.uid()) = user_id);
        """.replace("{a}", USER_A).replace("{b}", USER_B), db=cls.db)
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

    def two_user_site(self):
        port = free_port()
        js = ('const c=Ke("http://127.0.0.1:{p}","{k}");' + "".join(f'c.from("{t}").select();' for t in
              ("notes", "diary", "posts", "members", "invoices")) +
              'c.storage.from("documents").upload(f);c.storage.from("receipts").upload(f)').format(p=port, k=PUBLISHABLE)
        return Site({"/": INDEX, "/assets/index-abc123.js": js}, postgrest_port=self.pg_port, port=port)

    def test_two_users(self):
        s = self.two_user_site()
        try:
            code, data = run(s.base, "--mine", "--two-users", env=TWO_USERS_ENV)
        finally:
            s.close()
        self.assertEqual(code, 1, data)
        cross = {f["file"]: f for f in data["findings"] if f["check"] == "live-cross-user"}
        self.assertEqual(cross["table diary"]["severity"], "critical")       # private diary readable by others
        self.assertIn("1 row", cross["table diary"]["what"])
        self.assertEqual(cross["table posts"]["severity"], "medium")         # shared feed: flagged gently
        self.assertEqual(cross["files documents"]["severity"], "critical")   # can list other people's folders
        self.assertIn("= author_id", cross["table posts"]["fix"])              # names the real owner column
        self.assertIn("1 row ", cross["table diary"]["what"])
        self.assertNotIn("table notes", cross)
        self.assertNotIn("table members", cross)
        self.assertNotIn("files receipts", cross)
        between = " | ".join(data["between_users"])
        self.assertIn("notes: each account saw only its own rows (good)", between)
        self.assertIn("members: each account saw only its own rows (good)", between)
        self.assertIn("invoices", between.split("Not tested")[1])
        self.assertIn("receipts: each account saw only its own folder (good)", between)
        self.assertTrue(any("is_pro" in n for n in data["notes"]))
        dump = json.dumps(data)
        for secret in ("b secret", "pw-for-a-test", "pw-for-b-test", "my cat", "passport.pdf", user_jwt(USER_A)):
            self.assertNotIn(secret, dump)                                    # never shows data or passwords

    def test_two_users_wrong_password(self):
        s = self.two_user_site()
        env = dict(TWO_USERS_ENV, SEATBELT_B_PASSWORD="wrong")
        try:
            code, data = run(s.base, "--mine", "--two-users", env=env)
        finally:
            s.close()
        self.assertTrue(any("Could not log in as test account B" in b for b in data["between_users"]))
        self.assertFalse([f for f in data["findings"] if f["check"] == "live-cross-user"])

    def test_two_users_with_tokens(self):
        s = self.two_user_site()
        try:
            code, data = run(s.base, "--mine", "--two-users",
                             env={"SEATBELT_A_TOKEN": user_jwt(USER_A), "SEATBELT_B_TOKEN": user_jwt(USER_B)})
        finally:
            s.close()
        self.assertIn("table diary", {f["file"] for f in data["findings"] if f["check"] == "live-cross-user"})

    def test_without_mine_flag_no_database_requests(self):
        s = self.site(PUBLISHABLE)
        try:
            code, data = run(s.base)
        finally:
            s.close()
        self.assertEqual(data["database"], [])


if __name__ == "__main__":
    unittest.main()
