#!/usr/bin/env python3
"""Seatbelt live check: looks at your LIVE website the way a stranger would, and reports in plain
English. Python 3 only, nothing to install. It only reads (GET and HEAD requests); it never logs in,
never sends data, and never changes anything.

Use it only on a site you own or have permission to test.

What it checks:
  - secret keys inside the pages and JavaScript files the site sends to every visitor
  - files that should never be public: .env, .git, source maps
  - basic security headers and HTTPS
  - with --mine: whether your database answers strangers. It finds the Supabase address and
    PUBLIC key in your own site, then asks each table your code uses for one row, exactly as a
    stranger could. It reports how many rows are readable and which columns, never the data.
    Firebase Realtime Database and Firestore collections are checked the same way.

Usage:
  python3 check_live.py https://your-site.com
  python3 check_live.py https://your-site.com --mine --report live-report.md
  python3 check_live.py https://your-site.com --mine --json

Exit code: 0 no serious problems, 1 serious problems found, 2 could not run.
"""

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

UA = "Seatbelt-live-check/3 (+https://github.com/HYDERMAA/seatbelt)"
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
PROBE_PATHS = [
    (".env", "env"), (".env.local", "env"), (".env.production", "env"), (".env.development", "env"),
    (".git/HEAD", "git"), (".git/config", "gitconfig"),
]


def fetch(url, method="GET", headers=None, limit=MAX_BYTES):
    h = {"User-Agent": UA, "Accept": "*/*"}
    h.update(headers or {})
    req = urllib.request.Request(url, method=method, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            body = r.read(limit) if method == "GET" else b""
            return r.status, {k.lower(): v for k, v in r.headers.items()}, body, r.geturl()
    except urllib.error.HTTPError as e:
        body = e.read(200_000) if method == "GET" else b""
        return e.code, {k.lower(): v for k, v in (e.headers or {}).items()}, body, url
    except (urllib.error.URLError, TimeoutError, ConnectionError, ValueError, OSError) as e:
        return None, {}, str(e).encode(), url


class LiveCheck:
    def __init__(self, url, mine=False):
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

    def probe_firebase(self):
        rtdb, project, apikey, cols = None, None, None, set()
        for text in self.texts.values():
            rtdb = rtdb or (RTDB_RE.search(text).group(0) if RTDB_RE.search(text) else None)
            if not project and FB_PROJECT_RE.search(text):
                project = FB_PROJECT_RE.search(text).group(1)
            if not apikey and FB_APIKEY_RE.search(text):
                apikey = FB_APIKEY_RE.search(text).group(1)
            cols.update(COLLECTION_RE.findall(text))
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
        else:
            self.notes.append("Database not tested. If this is your site, run again with --mine to check whether strangers can read your tables.")
        scan = cs.Scanner.__new__(cs.Scanner)
        scan.findings = self.findings
        return scan.sorted_findings()


LIVE_MANUAL = [
    "Open the live site in a private window: can you reach private pages without logging in?",
    "Log in as a second test account: can you see the first account's data?",
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
    check = LiveCheck(args[0], mine="--mine" in flags)
    try:
        findings = check.run()
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        return 2
    blocking = any(f["severity"] in {"critical", "high"} for f in findings)
    if "--json" in flags:
        print(json.dumps({"url": check.url, "files_fetched": check.files_scanned, "ready": not blocking,
                          "database": check.database, "notes": check.notes, "findings": findings}, indent=2))
    else:
        cs.print_report(check, findings, title="Seatbelt live check", subject=f"Site: {check.url}",
                        counted=f"Files fetched: {check.files_scanned}  |  database tested: {'yes' if check.mine else 'no'}",
                        sections=[("DATABASE: what a stranger can read", check.database), ("NOTES", check.notes)])
    if report:
        cs.write_report(check, findings, report, title="Seatbelt live check", manual=LIVE_MANUAL,
                        extra=["Database: " + d for d in check.database] + ["Note: " + n for n in check.notes])
        if "--json" not in flags:
            print(f"Report saved to {report}")
    return 1 if blocking else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
