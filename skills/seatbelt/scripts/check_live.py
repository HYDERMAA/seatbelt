#!/usr/bin/env python3
"""Seatbelt live check: looks at your LIVE website the way a stranger would, and reports in plain
English. Python 3 only, nothing to install. It only reads, and never changes anything. It never
logs in unless you ask it to with --two-users, and then only as two test accounts you made.

Use it only on a site you own or have permission to test.

What it checks:
  - secret keys inside the pages and JavaScript files the site sends to every visitor
  - files that should never be public: .env, .git, source maps
  - basic security headers and HTTPS
  - with --mine: whether your database answers strangers. It finds the Supabase address and
    PUBLIC key in your own site, then asks each table your code uses for one row, exactly as a
    stranger could. It reports how many rows are readable and which columns, never the data.
    Firebase Realtime Database and Firestore collections are checked the same way.
  - with --mine --two-users: whether one logged-in customer can see ANOTHER customer's data
    (the most common leak in AI-built apps, and one a stranger test cannot find). You make two
    test accounts on your own site, A and B, and add something private as B (a note, a booking, a
    photo). The check logs in as both, then asks as A for B's rows and files, and the other way
    round. Logging in is the only thing it sends; after that it only reads, and it reports counts
    and column names, never the data. Writes (can A change or delete B's rows?) are not tested,
    because testing them would change data; the report says how to check those by hand.

    Give the two accounts in environment variables (never on the command line, so passwords do
    not end up in your history), or leave them out and it will ask:
      SEATBELT_A_EMAIL, SEATBELT_A_PASSWORD, SEATBELT_B_EMAIL, SEATBELT_B_PASSWORD
    or, for logins without a password (magic links, Google), copy each account's access token:
      SEATBELT_A_TOKEN, SEATBELT_B_TOKEN
    Use test accounts you made, never a real customer's account.

Usage:
  python3 check_live.py https://your-site.com
  python3 check_live.py https://your-site.com --mine --report live-report.md
  python3 check_live.py https://your-site.com --mine --json
  python3 check_live.py https://your-site.com --mine --two-users --report live-report.md

Exit code: 0 no serious problems, 1 serious problems found, 2 could not run.
"""

import base64
import getpass
import json
import os
import random
import re
import string
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check_secrets as cs  # noqa: E402

UA = "Seatbelt-live-check/3.1 (+https://github.com/HYDERMAA/seatbelt)"
MAX_SCRIPTS = 40
MAX_BYTES = 8_000_000
MAX_TABLES = 40
TIMEOUT = 20
SENSITIVE_COLS = re.compile(r"email|phone|mobile|address|postcode|zip|birth|dob|passport|ssn|nin|"
                            r"health|medical|diagnos|salary|iban|card|password|token|secret|ip_address|lat|lng", re.I)
SUPABASE_URL_RE = re.compile(r"https://[a-z0-9]{15,30}\.supabase\.(?:co|in)")
CREATE_CLIENT_RE = re.compile(r"[\"'`](https?://[^\"'`\s]{4,200})[\"'`]\s*,\s*[\"'`](sb_publishable_[0-9A-Za-z_\-]{10,}|eyJ[A-Za-z0-9_\-]+\.eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+)[\"'`]")
PUBLISHABLE_RE = re.compile(r"sb_publishable_[0-9A-Za-z_\-]{10,}")
FROM_RE = re.compile(r"(storage\s*)?\.from\(\s*[\"'`]([A-Za-z_][A-Za-z0-9_]{0,62})[\"'`]\s*\)")
RTDB_RE = re.compile(r"https://[a-z0-9\-]+(?:-default-rtdb)?\.(?:firebaseio\.com|[a-z0-9\-]+\.firebasedatabase\.app)")
FB_PROJECT_RE = re.compile(r"projectId\s*:\s*[\"'`]([a-z0-9\-]{4,40})[\"'`]")
FB_APIKEY_RE = re.compile(r"apiKey\s*:\s*[\"'`](AIza[0-9A-Za-z_\-]{35})[\"'`]")
COLLECTION_RE = re.compile(r"collection\(\s*(?:[A-Za-z_$][\w$]*\s*,\s*)?[\"'`]([A-Za-z0-9_\-]{1,60})[\"'`]")
SCRIPT_SRC_RE = re.compile(r"<script[^>]+src=[\"']([^\"']+)[\"']", re.I)
LINK_JS_RE = re.compile(r"<link[^>]+href=[\"']([^\"']+\.m?js(?:\?[^\"']*)?)[\"']", re.I)
CHUNK_RE = re.compile(r"[\"'`]((?:\.{0,2}/)?(?:assets|static/js|_next/static/chunks|_next/static/[\w-]+|js|build)/[\w./\-]+\.m?js)[\"'`]")
IMPORT_RE = re.compile(r"import\(\s*[\"'`](\.{1,2}/[\w./\-]+\.m?js)[\"'`]\s*\)")
SOURCEMAP_RE = re.compile(r"//[#@]\s*sourceMappingURL=([^\s'\"]+)")
RTDB_REF_RE = re.compile(r"\bref\(\s*[A-Za-z_$][\w$]*\s*,\s*[\"'`]/?([A-Za-z0-9_\-]{1,60})[/\"'`]")
PUBLIC_LIKE = re.compile(r"post|photo|picture|image|avatar|comment|like|review|listing|product|event|service|menu|"
                         r"categor|tag|feed|recipe|article|blog|gallery|course|lesson|faq|price|plan", re.I)
PERSONAL_NAME = re.compile(r"profile|user|member|account|customer|message|chat|order|payment|invoice|booking|"
                           r"journal|note|diary|patient|health|address|contact|document|upload|private|subscri|entitle|"
                           r"appointment|mood|entry|entries|file|form|submission|ticket|task|todo|expense|transaction", re.I)
ENTITLEMENT_COLS = re.compile(r"^(is_pro|is_premium|is_paid|is_admin|is_staff|is_verified|role|roles|plan|tier|credits|"
                              r"balance|subscription\w*|paid\w*|premium\w*|admin|permissions?)$", re.I)
IDENTITY_BASE = "https://identitytoolkit.googleapis.com"   # Firebase Auth (overridden in tests)
FIRESTORE_BASE = "https://firestore.googleapis.com"
MAX_ROWS = 50
PROBE_PATHS = [
    (".env", "env"), (".env.local", "env"), (".env.production", "env"), (".env.development", "env"),
    (".git/HEAD", "git"), (".git/config", "gitconfig"),
]


def fetch(url, method="GET", headers=None, limit=MAX_BYTES, data=None):
    h = {"User-Agent": UA, "Accept": "*/*"}
    h.update(headers or {})
    if data is not None and not isinstance(data, bytes):
        data = json.dumps(data).encode()
        h.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, method=method, headers=h, data=data)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            body = r.read(limit) if method in ("GET", "POST") else b""
            return r.status, {k.lower(): v for k, v in r.headers.items()}, body, r.geturl()
    except urllib.error.HTTPError as e:
        body = e.read(200_000) if method in ("GET", "POST") else b""
        return e.code, {k.lower(): v for k, v in (e.headers or {}).items()}, body, url
    except (urllib.error.URLError, TimeoutError, ConnectionError, ValueError, OSError) as e:
        return None, {}, str(e).encode(), url


def jwt_claims(token):
    try:
        part = token.split(".")[1]
        part += "=" * (-len(part) % 4)
        data = json.loads(base64.urlsafe_b64decode(part.encode()).decode("utf-8", "ignore"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def load_accounts(env=None, ask=None):
    """Two test accounts from environment variables, or by asking. Never from the command line."""
    env = os.environ if env is None else env
    accounts = {}
    for who in ("A", "B"):
        token = env.get(f"SEATBELT_{who}_TOKEN", "").strip()
        email = env.get(f"SEATBELT_{who}_EMAIL", "").strip()
        password = env.get(f"SEATBELT_{who}_PASSWORD", "")
        if token:
            accounts[who] = {"token": token}
            continue
        if (not email or not password) and ask:
            email = email or ask(f"Test account {who}: email: ", False).strip()
            password = password or ask(f"Test account {who}: password (not shown): ", True)
        if not email or not password:
            return None, (f"Test account {who} is missing. Set SEATBELT_{who}_EMAIL and SEATBELT_{who}_PASSWORD "
                          f"(or SEATBELT_{who}_TOKEN) and run again.")
        accounts[who] = {"email": email, "password": password}
    if "email" in accounts["A"] and accounts["A"].get("email", "").lower() == accounts["B"].get("email", "").lower():
        return None, "Accounts A and B are the same. Make two different test accounts."
    return accounts, None


def terminal_ask(prompt, secret):
    if not sys.stdin or not sys.stdin.isatty():
        return ""
    return getpass.getpass(prompt) if secret else input(prompt)


class LiveCheck:
    def __init__(self, url, mine=False, two_users=False, accounts=None):
        if not re.match(r"https?://", url):
            url = "https://" + url
        self.url = url.rstrip("/") + "/"
        self.origin = "{0.scheme}://{0.netloc}".format(urllib.parse.urlsplit(self.url))
        self.mine = mine
        self.findings = []
        self.root = self.url              # for the shared report writer
        self.files_scanned = 0
        self.npm_audit = None
        self.texts = {}                   # url -> text of HTML and JS the site serves
        self.notes = []
        self.database = []                # plain summaries of database probes
        self.two_users = two_users
        self.accounts = accounts or {}
        self.between = []                 # plain summaries of the two-account test

    def add(self, severity, check, where, what, why, fix):
        self.findings.append({"severity": severity, "check": check, "file": where, "line": None,
                              "what": what, "why": why, "fix": fix})

    # ---------- gather ----------
    def gather(self):
        status, headers, body, final = fetch(self.url)
        if status is None:
            raise RuntimeError(f"Could not open {self.url}: {body.decode(errors='ignore')}")
        self.main_status, self.main_headers, self.final_url = status, headers, final
        html = body.decode("utf-8", "ignore")
        self.texts[final] = html
        self.files_scanned = 1
        queue = []
        for src in SCRIPT_SRC_RE.findall(html) + LINK_JS_RE.findall(html):
            queue.append(urllib.parse.urljoin(final, src))
        seen = set()
        while queue and len(seen) < MAX_SCRIPTS:
            u = queue.pop(0)
            if u in seen or urllib.parse.urlsplit(u).netloc != urllib.parse.urlsplit(final).netloc:
                continue
            seen.add(u)
            st, _, b, _ = fetch(u)
            if st != 200:
                continue
            js = b.decode("utf-8", "ignore")
            self.texts[u] = js
            self.files_scanned += 1
            for chunk in IMPORT_RE.findall(js):
                cu = urllib.parse.urljoin(u, chunk)
                if cu not in seen:
                    queue.append(cu)
            for chunk in CHUNK_RE.findall(js):
                cu = urllib.parse.urljoin(u if chunk.startswith(".") else self.origin + "/", chunk)
                if cu not in seen:
                    queue.append(cu)
            for sm in SOURCEMAP_RE.findall(js)[-1:]:
                if not sm.startswith("data:"):
                    self.check_source_map(urllib.parse.urljoin(u, sm))

    # ---------- checks ----------
    def check_secrets(self):
        firebase_page = any("authDomain" in t and "projectId" in t for t in self.texts.values())
        for url, text in self.texts.items():
            short = self.short(url)
            for check_id, label, rx in cs.COMPILED:
                for m in rx.finditer(text):
                    value = m.group(0)
                    if cs.PLACEHOLDER_RE.search(value):
                        continue
                    if check_id == "google-api-key" and firebase_page:
                        self.add("low", "firebase-api-key", short,
                                 f"A Google or Firebase web key is in the site ({cs.mask(value)}).",
                                 "Firebase web keys are meant to be public, but anyone can reuse them for other Google APIs if the key is not restricted.",
                                 "In Google Cloud > APIs & Services > Credentials, restrict this key to your website address and only the APIs it needs.")
                        continue
                    self.add("critical", "live-secret", short,
                             f"{label} is visible to every visitor ({cs.mask(value)}).",
                             "Anyone can open your site's files and copy it, then use it on your account.",
                             "Replace the key now in the provider's dashboard, then move the code that uses it to a server function. Removing it from the site alone is not enough.")
            for m in cs.JWT_RE.finditer(text):
                if cs.jwt_role(m.group(0)) == "service_role":
                    self.add("critical", "live-service-role", short,
                             f"Your Supabase service_role key is visible to every visitor ({cs.mask(m.group(0))}).",
                             "This key ignores every database rule. Anyone can read, change or delete all your data.",
                             "Replace it now (Supabase > Settings > API Keys), use it only in server code, and check your data for changes.")

    def check_source_map(self, url):
        st, _, b, _ = fetch(url)
        if st == 200 and b[:1] == b"{" and b'"sources"' in b[:2000] + b[-2000:]:
            self.add("medium", "live-source-map", self.short(url),
                     "Your original source code is downloadable (a source map file is public).",
                     "It makes your code, comments and any mistakes easy to read for anyone.",
                     "Turn off production source maps in your build settings, or make sure they are not uploaded.")
            self.texts[url] = b.decode("utf-8", "ignore")

    def check_paths(self):
        rand = "".join(random.choice(string.ascii_lowercase) for _ in range(12))
        st0, _, base, _ = fetch(self.origin + f"/seatbelt-check-{rand}")
        for path, kind in PROBE_PATHS:
            st, headers, body, _ = fetch(self.origin + "/" + path, limit=200_000)
            if st != 200 or not body or (st0 == 200 and body == base):
                continue
            text = body.decode("utf-8", "ignore")
            if "<html" in text[:500].lower() or "<!doctype" in text[:200].lower():
                continue
            if kind == "env" and re.search(r"^\s*[A-Z][A-Z0-9_]{2,}\s*=", text, re.M):
                self.add("critical", "live-env-file", f"/{path}",
                         f"Your {path} file can be downloaded by anyone.",
                         "It usually holds your secret keys and passwords.",
                         "Remove it from the public folder or hosting now, then replace every key that was in it.")
            elif kind == "git" and text.startswith("ref:"):
                self.add("critical", "live-git-folder", f"/{path}",
                         "Your .git folder is public, so anyone can download your whole project history.",
                         "Old versions can contain keys and passwords even if you removed them later.",
                         "Stop deploying the .git folder (deploy the build output only), then replace any key that was ever committed.")
            elif kind == "gitconfig" and "[core]" in text:
                self.add("high", "live-git-folder", f"/{path}",
                         "Your .git folder is public.", "It exposes your project history.",
                         "Stop deploying the .git folder.")

    def check_headers(self):
        h = self.main_headers
        local = urllib.parse.urlsplit(self.final_url).hostname in ("localhost", "127.0.0.1", "::1")
        if self.final_url.startswith("http://") and not local:
            self.add("high", "no-https", self.final_url,
                     "The site does not use HTTPS (the padlock).",
                     "Logins and personal details can be read or changed on public Wi-Fi.",
                     "Turn on HTTPS in your hosting settings; most hosts do it free.")
        tips = []
        if self.final_url.startswith("https://") and "strict-transport-security" not in h:
            tips.append("Strict-Transport-Security (always use HTTPS)")
        if "content-security-policy" not in h:
            tips.append("Content-Security-Policy (limits which scripts can run)")
        if "x-content-type-options" not in h:
            tips.append("X-Content-Type-Options: nosniff")
        csp = h.get("content-security-policy", "")
        if "x-frame-options" not in h and "frame-ancestors" not in csp:
            tips.append("X-Frame-Options or frame-ancestors (stops other sites framing yours)")
        if "referrer-policy" not in h:
            tips.append("Referrer-Policy")
        if tips:
            self.add("low", "security-headers", self.short(self.final_url),
                     "Missing security headers: " + "; ".join(tips) + ".",
                     "They are extra layers that make some attacks harder. Not urgent for a simple site.",
                     "Ask your AI to add these headers in your hosting config (for example vercel.json, netlify.toml or _headers).")

    # ---------- database probes (only with --mine) ----------
    def supabase_config(self):
        url = key = None
        tables, buckets = set(), set()
        for text in self.texts.values():
            for m in CREATE_CLIENT_RE.finditer(text):
                url, key = url or m.group(1).rstrip("/"), key or m.group(2)
            if not url:
                m = SUPABASE_URL_RE.search(text)
                url = m.group(0) if m else url
            if not key:
                m = PUBLISHABLE_RE.search(text)
                if m:
                    key = m.group(0)
                else:
                    for j in cs.JWT_RE.finditer(text):
                        if cs.jwt_role(j.group(0)) == "anon":
                            key = j.group(0)
                            break
            for m in FROM_RE.finditer(text):
                (buckets if m.group(1) else tables).add(m.group(2))
        if key and (key.startswith("sb_secret_") or cs.jwt_role(key) == "service_role"):
            key = None  # never use a secret key, even if the site leaked one
        return url, key, sorted(tables)[:MAX_TABLES], sorted(buckets)

    def probe_supabase(self):
        url, key, tables, buckets = self.supabase_config()
        if not url:
            return
        if not key:
            self.notes.append("Found a Supabase address but no public key in the site, so the database was not tested.")
            return
        if not tables:
            self.notes.append("Found Supabase, but no table names in the site's code. Run the audit queries from the Supabase playbook instead.")
            return
        headers = {"apikey": key, "Prefer": "count=exact", "Accept": "application/json"}
        if key.startswith("eyJ"):
            headers["Authorization"] = "Bearer " + key
        for t in tables:
            time.sleep(0.2)
            st, h, body, _ = fetch(f"{url}/rest/v1/{urllib.parse.quote(t)}?select=*&limit=1", headers=headers, limit=500_000)
            if st in (200, 206):
                try:
                    rows = json.loads(body.decode("utf-8", "ignore"))
                except ValueError:
                    rows = None
                total = None
                cr = h.get("content-range", "")
                if "/" in cr and cr.split("/")[1].isdigit():
                    total = int(cr.split("/")[1])
                if isinstance(rows, list) and rows:
                    cols = sorted(rows[0].keys()) if isinstance(rows[0], dict) else []
                    sensitive = [c for c in cols if SENSITIVE_COLS.search(c)]
                    count = (f"{total} row" + ("" if total == 1 else "s")) if total is not None else "rows"
                    self.database.append(f"{t}: OPEN, {count} readable by anyone")
                    personal = re.search(r"profile|user|member|account|customer|message|chat|order|payment|invoice|booking|"
                                         r"journal|note|diary|patient|health|address|contact|document|upload|private|subscri|entitle", t, re.I)
                    sev = "critical" if sensitive else ("high" if personal else "medium")
                    self.add(sev, "live-table-open", f"table {t}",
                             f"Anyone can read the '{t}' table ({count}; columns: {', '.join(cols[:12])}{'...' if len(cols) > 12 else ''})."
                             + (f" It includes personal-looking columns: {', '.join(sensitive)}." if sensitive else ""),
                             "Your public key is in your website, so any stranger can download this table.",
                             f"If this table is not meant to be public, add Row Level Security and an owner-only policy to '{t}' now (see the Supabase playbook). If it is meant to be public (a menu, a price list), check every column is fine to share.")
                else:
                    self.database.append(f"{t}: answered with no rows (protected by rules, or empty)")
            elif st in (401, 403) or (st and b"permission denied" in body) or (st == 404 and b"PGRST" in body):
                self.database.append(f"{t}: refused (good)")
            else:
                self.database.append(f"{t}: could not test (status {st})")
        if buckets:
            self.notes.append("Storage buckets used by the site: " + ", ".join(buckets)
                              + ". Check in Supabase > Storage that private files are in private buckets.")
        if self.two_users:
            anon_open = {f["file"][len("table "):] for f in self.findings if f["check"] == "live-table-open"}
            self.probe_supabase_between(url, key, tables, buckets, anon_open)

    def probe_firebase(self):
        rtdb, project, apikey, cols, paths = None, None, None, set(), set()
        for text in self.texts.values():
            rtdb = rtdb or (RTDB_RE.search(text).group(0) if RTDB_RE.search(text) else None)
            if not project and FB_PROJECT_RE.search(text):
                project = FB_PROJECT_RE.search(text).group(1)
            if not apikey and FB_APIKEY_RE.search(text):
                apikey = FB_APIKEY_RE.search(text).group(1)
            cols.update(COLLECTION_RE.findall(text))
            paths.update(RTDB_REF_RE.findall(text))
        if rtdb:
            st, _, body, _ = fetch(rtdb.rstrip("/") + "/.json?shallow=true", limit=200_000)
            if st == 200 and body.strip() not in (b"null", b""):
                self.database.append("Realtime Database: OPEN to anyone")
                self.add("critical", "live-firebase-open", "Firebase Realtime Database",
                         "Anyone can read your Firebase Realtime Database.",
                         "Strangers can download everything stored in it.",
                         "Replace the rules with ones that check request.auth (see the Firebase playbook) and publish them now.")
            else:
                self.database.append("Realtime Database: refused or empty (good)")
        if project and cols:
            for c in sorted(cols)[:MAX_TABLES]:
                time.sleep(0.2)
                q = f"https://firestore.googleapis.com/v1/projects/{project}/databases/(default)/documents/{urllib.parse.quote(c)}?pageSize=1"
                if apikey:
                    q += "&key=" + apikey
                st, _, body, _ = fetch(q, limit=200_000)
                if st == 200 and b'"documents"' in body:
                    self.database.append(f"Firestore {c}: OPEN")
                    self.add("critical", "live-firestore-open", f"collection {c}",
                             f"Anyone can read the Firestore collection '{c}'.",
                             "Strangers can download documents from it without logging in.",
                             "Tighten the Firestore rules for this collection to check request.auth (see the Firebase playbook).")
                elif st in (401, 403):
                    self.database.append(f"Firestore {c}: refused (good)")
        if self.two_users and (rtdb or (project and cols)):
            self.probe_firebase_between(rtdb, project, apikey, cols, paths)

    # ---------- two-account test (only with --mine --two-users) ----------
    def say(self, line):
        self.between.append(line)

    def cross_finding(self, table, kind, viewer, owner, count, cols, anon_open, owner_col="user_id"):
        """kind: 'table', 'firestore', 'rtdb' or 'files'."""
        sensitive = [c for c in cols if SENSITIVE_COLS.search(c)]
        shared = bool(PUBLIC_LIKE.search(table)) and not PERSONAL_NAME.search(table) and not sensitive
        what_thing = {"table": f"the '{table}' table", "firestore": f"the Firestore collection '{table}'",
                      "rtdb": f"'{table}' in the Realtime Database", "files": f"the '{table}' storage bucket"}[kind]
        noun = {"files": "file", "table": "row"}.get(kind, "record") + ("" if count == 1 else "s")
        what = (f"Logged in as test account {viewer}, the check could read {count} {noun} that belong to "
                f"test account {owner} in {what_thing}.")
        if sensitive:
            what += f" They include personal-looking columns: {', '.join(sensitive)}."
        if shared:
            sev = "medium"
            why = ("This looks like content people are meant to share (posts, photos, reviews). If so, this is "
                   "fine. If any of it is private, every customer can read every other customer's copy.")
        else:
            sev = "critical" if (sensitive or PERSONAL_NAME.search(table) or kind == "files") else "high"
            why = ("Any customer can read other customers' private data. Anyone can make a free account, so "
                   "this is nearly as bad as a public table." if not anon_open else
                   "Strangers can already read this without logging in (see above), so fix that first.")
        if kind == "table":
            fix = (f"Change the read rule on '{table}' so it only returns the person's own rows, for example "
                   f"using ((select auth.uid()) = {owner_col}), not using (true). Then run this check again.")
        elif kind == "files":
            fix = ("Change the storage rule so people can only list and download files in their own folder "
                   "((storage.foldername(name))[1] = (select auth.uid())::text). See the Supabase playbook.")
        else:
            fix = ("Change the rule so a person can only read their own records, for example "
                   "allow read: if request.auth != null && request.auth.uid == resource.data.userId "
                   "(see the Firebase playbook), publish it, then run this check again.")
        if shared:
            fix = "If everything in it is meant to be shared, no change is needed. If not: " + fix[0].lower() + fix[1:]
        self.add(sev, "live-cross-user", f"{kind} {table}", what, why, fix)

    def supabase_login(self, url, key, who):
        acc = self.accounts.get(who) or {}
        if acc.get("token"):
            token = acc["token"]
        else:
            st, _, body, _ = fetch(f"{url}/auth/v1/token?grant_type=password", method="POST",
                                   headers={"apikey": key}, data={"email": acc.get("email"), "password": acc.get("password")},
                                   limit=200_000)
            try:
                token = json.loads(body.decode("utf-8", "ignore")).get("access_token") if st == 200 else None
            except ValueError:
                token = None
            if not token:
                self.say(f"Could not log in as test account {who} (status {st}). Check the email and password, "
                         "and that the account's email is confirmed.")
                return None, None
        uid = jwt_claims(token).get("sub")
        if not uid:
            self.say(f"Test account {who}'s token has no user id in it, so it cannot be used.")
            return None, None
        return token, uid

    def sb_rows(self, url, key, token, table, query):
        headers = {"apikey": key, "Authorization": "Bearer " + token, "Accept": "application/json", "Prefer": "count=exact"}
        st, h, body, _ = fetch(f"{url}/rest/v1/{urllib.parse.quote(table)}?{query}", headers=headers, limit=2_000_000)
        if st not in (200, 206):
            return st, None, None
        try:
            rows = json.loads(body.decode("utf-8", "ignore"))
        except ValueError:
            return st, None, None
        total = None
        cr = h.get("content-range", "")
        if "/" in cr and cr.split("/")[1].isdigit():
            total = int(cr.split("/")[1])
        return st, rows if isinstance(rows, list) else None, total

    def probe_supabase_between(self, url, key, tables, buckets, anon_open):
        tok, uid = {}, {}
        for who in ("A", "B"):
            tok[who], uid[who] = self.supabase_login(url, key, who)
            if not tok[who]:
                return
        if uid["A"] == uid["B"]:
            self.say("Accounts A and B are the same user. Make two different test accounts.")
            return
        self.say("Logged in as test accounts A and B.")
        untested, entitled = [], set()
        for t in tables:
            results = []
            for owner, viewer in (("B", "A"), ("A", "B")):
                time.sleep(0.1)
                st, rows, _ = self.sb_rows(url, key, tok[owner], t, f"select=*&limit={MAX_ROWS}")
                if rows is None:
                    results.append(("refused", owner, viewer, 0, [], None))
                    continue
                own_cols = set()
                own_ids = []
                for r in rows:
                    if not isinstance(r, dict):
                        continue
                    hit = [c for c, v in r.items() if isinstance(v, str) and v == uid[owner]]
                    if hit:
                        own_cols.update(hit)
                        if r.get("id") is not None and "id" not in hit:
                            own_ids.append(str(r["id"]))
                        entitled.update(c for c in r if ENTITLEMENT_COLS.match(c))
                if not own_cols:
                    results.append(("none", owner, viewer, 0, [], None))
                    continue
                cols = sorted(rows[0].keys()) if rows and isinstance(rows[0], dict) else []
                seen = 0
                for c in sorted(own_cols):
                    _, got, total = self.sb_rows(url, key, tok[viewer], t,
                                                 f"select=*&{urllib.parse.quote(c)}=eq.{uid[owner]}&limit=1")
                    if got:
                        seen = max(seen, total if total is not None else len(got))
                if own_ids and not seen:
                    ids = ",".join(urllib.parse.quote(i) for i in own_ids[:20])
                    _, got, total = self.sb_rows(url, key, tok[viewer], t, f"select=*&id=in.({ids})")
                    if got:
                        seen = total if total is not None else len(got)
                results.append(("leak" if seen else "ok", owner, viewer, seen, cols, sorted(own_cols)[0]))
            leaks = [r for r in results if r[0] == "leak"]
            if leaks:
                _, owner, viewer, seen, cols, col = max(leaks, key=lambda r: r[3])
                self.say(f"{t}: account {viewer} CAN read account {owner}'s rows ({seen})")
                self.cross_finding(t, "table", viewer, owner, seen, cols, t in anon_open, owner_col=col)
            elif any(r[0] == "ok" for r in results):
                self.say(f"{t}: each account saw only its own rows (good)")
            elif all(r[0] == "refused" for r in results):
                self.say(f"{t}: logged-in users cannot read it at all")
            else:
                untested.append(t)
        if untested:
            self.say("Not tested (no rows linked to account A or B yet): " + ", ".join(untested)
                     + ". Log in as B, add something private (a note, a booking), and run again.")
        if entitled:
            self.notes.append("Your users' own rows include " + ", ".join(sorted(entitled))
                              + ". This check only reads, so it cannot tell whether a customer can change these "
                                "to give themselves paid features. Run the Supabase playbook's audit queries to check.")
        for b in buckets:
            results = []
            for owner, viewer in (("B", "A"), ("A", "B")):
                st, _, body, _ = fetch(f"{url}/storage/v1/object/list/{urllib.parse.quote(b)}", method="POST",
                                       headers={"apikey": key, "Authorization": "Bearer " + tok[viewer]},
                                       data={"prefix": uid[owner], "limit": 20}, limit=500_000)
                try:
                    items = json.loads(body.decode("utf-8", "ignore")) if st == 200 else None
                except ValueError:
                    items = None
                own_st, _, own_body, _ = fetch(f"{url}/storage/v1/object/list/{urllib.parse.quote(b)}", method="POST",
                                               headers={"apikey": key, "Authorization": "Bearer " + tok[owner]},
                                               data={"prefix": uid[owner], "limit": 20}, limit=500_000)
                try:
                    own = json.loads(own_body.decode("utf-8", "ignore")) if own_st == 200 else None
                except ValueError:
                    own = None
                results.append((owner, viewer, len(items or []), len(own or [])))
            leak = [r for r in results if r[2]]
            if leak:
                owner, viewer, n, _ = leak[0]
                self.say(f"files in {b}: account {viewer} CAN list account {owner}'s files ({n})")
                self.cross_finding(b, "files", viewer, owner, n, [], False)
            elif any(r[3] for r in results):
                self.say(f"files in {b}: each account saw only its own folder (good)")
            else:
                self.say(f"files in {b}: not tested (no files in A's or B's folder yet)")
        self.notes.append("The two-account test only reads. Also check by hand that account A cannot change or "
                          "delete B's things: log in as A, open one of B's links, and try to edit it.")

    def firebase_login(self, apikey, who):
        acc = self.accounts.get(who) or {}
        if acc.get("token"):
            token = acc["token"]
        else:
            if not apikey:
                self.say("Found Firebase but no web key in the site, so the accounts could not log in.")
                return None, None
            st, _, body, _ = fetch(f"{IDENTITY_BASE}/v1/accounts:signInWithPassword?key={urllib.parse.quote(apikey)}",
                                   method="POST", data={"email": acc.get("email"), "password": acc.get("password"),
                                                        "returnSecureToken": True}, limit=200_000)
            try:
                token = json.loads(body.decode("utf-8", "ignore")).get("idToken") if st == 200 else None
            except ValueError:
                token = None
            if not token:
                self.say(f"Could not log in to Firebase as test account {who} (status {st}). Check the email and password.")
                return None, None
        claims = jwt_claims(token)
        uid = claims.get("user_id") or claims.get("sub")
        return (token, uid) if uid else (None, None)

    def probe_firebase_between(self, rtdb, project, apikey, cols, paths):
        tok, uid = {}, {}
        for who in ("A", "B"):
            tok[who], uid[who] = self.firebase_login(apikey, who)
            if not tok[who]:
                return
        if uid["A"] == uid["B"]:
            self.say("Accounts A and B are the same user. Make two different test accounts.")
            return
        self.say("Logged in to Firebase as test accounts A and B.")

        def contains(fields, value):
            for v in (fields or {}).values():
                if not isinstance(v, dict):
                    continue
                if v.get("stringValue") == value or v.get("referenceValue", "").endswith("/" + value):
                    return True
                if "mapValue" in v and contains(v["mapValue"].get("fields"), value):
                    return True
            return False

        if project:
            base = f"{FIRESTORE_BASE}/v1/projects/{project}/databases/(default)/documents"
            for c in sorted(cols)[:MAX_TABLES]:
                outcome = []
                for owner, viewer in (("B", "A"), ("A", "B")):
                    h = {"Authorization": "Bearer " + tok[viewer]}
                    seen, keys = 0, []
                    st, _, body, _ = fetch(f"{base}/{urllib.parse.quote(c)}/{urllib.parse.quote(uid[owner])}", headers=h, limit=500_000)
                    if st == 200 and b'"fields"' in body:
                        seen += 1
                        keys = sorted((json.loads(body).get("fields") or {}).keys())
                    st, _, body, _ = fetch(f"{base}/{urllib.parse.quote(c)}?pageSize={MAX_ROWS}", headers=h, limit=2_000_000)
                    owned_by_owner = 0
                    if st == 200:
                        try:
                            docs = json.loads(body.decode("utf-8", "ignore")).get("documents", [])
                        except ValueError:
                            docs = []
                        for d in docs:
                            if contains(d.get("fields"), uid[owner]) and not d.get("name", "").endswith("/" + uid[owner]):
                                owned_by_owner += 1
                                keys = keys or sorted((d.get("fields") or {}).keys())
                    seen += owned_by_owner
                    outcome.append((owner, viewer, seen, keys))
                leak = [o for o in outcome if o[2]]
                if leak:
                    owner, viewer, n, keys = leak[0]
                    self.say(f"Firestore {c}: account {viewer} CAN read account {owner}'s records ({n})")
                    self.cross_finding(c, "firestore", viewer, owner, n, keys, False)
                else:
                    self.say(f"Firestore {c}: neither account could read the other's records (or none exist yet)")
        if rtdb:
            for path in sorted(set(paths) | {"users"})[:MAX_TABLES]:
                for owner, viewer in (("B", "A"), ("A", "B")):
                    st, _, body, _ = fetch(f"{rtdb.rstrip('/')}/{urllib.parse.quote(path)}/{urllib.parse.quote(uid[owner])}.json"
                                           f"?shallow=true&auth={urllib.parse.quote(tok[viewer])}", limit=200_000)
                    if st == 200 and body.strip() not in (b"null", b""):
                        self.say(f"Realtime Database {path}: account {viewer} CAN read account {owner}'s data")
                        self.cross_finding(path, "rtdb", viewer, owner, 1, [], False)
                        break
                else:
                    self.say(f"Realtime Database {path}: neither account could read the other's data (or none exists)")

    # ---------- run ----------
    def short(self, url):
        return url.replace(self.origin, "") or "/"

    def run(self):
        self.gather()
        self.check_secrets()
        self.check_paths()
        self.check_headers()
        if self.mine:
            self.probe_supabase()
            self.probe_firebase()
            if self.two_users and not self.between:
                self.between.append("Two-account test not run: no Supabase or Firebase database was found in the site.")
        else:
            self.notes.append("Database not tested. If this is your site, run again with --mine to check whether strangers can read your tables.")
        scan = cs.Scanner.__new__(cs.Scanner)
        scan.findings = self.findings
        return scan.sorted_findings()


LIVE_MANUAL = [
    "Open the live site in a private window: can you reach private pages without logging in?",
    "Log in as a second test account: can you see, change or delete the first account's data? (--two-users tests reading automatically)",
    "Spending caps and alerts are set on every paid service",
    "Run the builder's own scan too (Lovable security scan, Replit Security Center, Supabase Security Advisor)",
]


def main(argv):
    args = [a for a in argv if not a.startswith("--")]
    flags = {a.split("=")[0] for a in argv if a.startswith("--")}
    report = None
    for i, a in enumerate(argv):
        if a == "--report" and i + 1 < len(argv):
            report = argv[i + 1]
            args = [x for x in args if x != report]
        elif a.startswith("--report="):
            report = a.split("=", 1)[1]
    if "--help" in flags or not args:
        print(__doc__)
        return 0 if "--help" in flags else 2
    two = "--two-users" in flags
    if two and "--mine" not in flags:
        print("--two-users needs --mine as well (it tests your own database). Only use it on your own site.", file=sys.stderr)
        return 2
    accounts = None
    if two:
        accounts, problem = load_accounts(ask=terminal_ask)
        if problem:
            print(problem, file=sys.stderr)
            return 2
    check = LiveCheck(args[0], mine="--mine" in flags, two_users=two, accounts=accounts)
    try:
        findings = check.run()
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        return 2
    blocking = any(f["severity"] in {"critical", "high"} for f in findings)
    if "--json" in flags:
        print(json.dumps({"url": check.url, "files_fetched": check.files_scanned, "ready": not blocking,
                          "database": check.database, "between_users": check.between, "notes": check.notes, "findings": findings}, indent=2))
    else:
        cs.print_report(check, findings, title="Seatbelt live check", subject=f"Site: {check.url}",
                        counted=f"Files fetched: {check.files_scanned}  |  database tested: {'yes' if check.mine else 'no'}",
                        sections=[("DATABASE: what a stranger can read", check.database),
                                  ("BETWEEN CUSTOMERS: can one account read another's data", check.between),
                                  ("NOTES", check.notes)])
    if report:
        cs.write_report(check, findings, report, title="Seatbelt live check", manual=LIVE_MANUAL,
                        extra=["Database: " + d for d in check.database] + ["Between accounts: " + b for b in check.between]
                        + ["Note: " + n for n in check.notes])
        if "--json" not in flags:
            print(f"Report saved to {report}")
    return 1 if blocking else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
