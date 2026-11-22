#!/usr/bin/env python3
"""Seatbelt ship check: a no-install scanner for leaked keys and risky settings.

Usage:
    python3 check_secrets.py [project_folder] [--json] [--report FILE.md|FILE.html] [--audit]

    --report FILE   also write a plain-English report (Markdown or HTML) to keep
    --audit         also run "npm audit" when there is a package-lock.json (needs internet)
    --json          machine-readable output

Reads files only and never changes anything. Needs only Python 3.8 or newer.
Exit code 0: no critical or high findings. 1: something should be fixed first. 2: usage error.
It never uploads anything: every check runs on this computer (except --audit, which asks npm).

It is a quick safety net, not a full security audit. It cannot see your hosting dashboard,
your live database settings, or anything outside the folder you point it at.
Add the comment "seatbelt-ignore" on a line to silence a finding you have checked by hand.
"""

import base64
import json
import os
import re
import subprocess
import sys

SKIP_DIRS = {
    ".git", "node_modules", ".venv", "venv", "env", "__pycache__", ".cache", ".turbo",
    ".pnpm-store", ".yarn", "bower_components", "vendor", ".idea", ".vscode", "coverage",
    ".svelte-kit", ".vercel", ".netlify", ".expo", "Pods", ".gradle",
}
SKIP_EXTS = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".svg", ".pdf", ".zip", ".gz", ".tar",
    ".mp4", ".mov", ".mp3", ".wav", ".woff", ".woff2", ".ttf", ".otf", ".eot", ".lock",
    ".map", ".pyc", ".so", ".dll", ".exe", ".bin", ".sqlite", ".db",
}
SKIP_FILES = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml", "bun.lockb", "poetry.lock"}
MAX_BYTES = 2_000_000

SEVERITY_ORDER = ["critical", "high", "medium", "low"]
NO_FOLD = {"table-without-rls", "rls-before-create", "user-can-edit-entitlement", "rls-disabled", "definer-without-search-path"}

# (id, label, regex). Patterns are deliberately specific to keep false alarms low.
SECRET_PATTERNS = [
    ("anthropic-key", "Anthropic API key", r"sk-ant-[A-Za-z0-9_\-]{20,}"),
    ("openai-key", "OpenAI-style API key (OpenAI, DeepSeek and others)", r"sk-(?:proj-|svcacct-|admin-)?[A-Za-z0-9_\-]{32,}"),
    ("google-api-key", "Google API key (may unlock Gemini or Google Cloud)", r"AIza[0-9A-Za-z_\-]{35}"),
    ("stripe-live-secret", "Stripe live secret key", r"(?:sk|rk)_live_[0-9A-Za-z]{20,}"),
    ("stripe-test-secret", "Stripe test secret key", r"(?:sk|rk)_test_[0-9A-Za-z]{20,}"),
    ("stripe-webhook-secret", "Stripe webhook signing secret", r"whsec_[0-9A-Za-z]{20,}"),
    ("aws-access-key", "AWS access key", r"(?:AKIA|ASIA)[0-9A-Z]{16}"),
    ("github-token", "GitHub token", r"(?:ghp|gho|ghu|ghs|ghr)_[0-9A-Za-z]{36}|github_pat_[0-9A-Za-z_]{40,}"),
    ("slack-token", "Slack token", r"xox[baprs]-[0-9A-Za-z\-]{10,}"),
    ("supabase-secret", "Supabase secret key", r"sb_secret_[0-9A-Za-z_\-]{20,}"),
    ("groq-key", "Groq API key", r"gsk_[0-9A-Za-z]{40,}"),
    ("xai-key", "xAI API key", r"xai-[0-9A-Za-z]{40,}"),
    ("huggingface-token", "Hugging Face token", r"hf_[0-9A-Za-z]{30,}"),
    ("sendgrid-key", "SendGrid API key", r"SG\.[0-9A-Za-z_\-]{22}\.[0-9A-Za-z_\-]{43}"),
    ("resend-key", "Resend API key", r"re_[0-9A-Za-z]{8,}_[0-9A-Za-z]{16,}"),
    ("telegram-bot-token", "Telegram bot token", r"\b\d{8,10}:AA[0-9A-Za-z_\-]{33}\b"),
    ("google-oauth-secret", "Google OAuth client secret", r"GOCSPX-[0-9A-Za-z_\-]{20,}"),
    ("npm-token", "npm access token", r"npm_[0-9A-Za-z]{36}"),
    ("shopify-token", "Shopify access token", r"shp(?:at|ss|ca|pa)_[0-9a-fA-F]{32}"),
    ("digitalocean-token", "DigitalOcean token", r"dop_v1_[0-9a-f]{64}"),
    ("replicate-token", "Replicate API token", r"r8_[0-9A-Za-z]{30,}"),
    ("perplexity-key", "Perplexity API key", r"pplx-[0-9A-Za-z]{40,}"),
    ("twilio-api-key", "Twilio API key", r"\bSK[0-9a-f]{32}\b"),
    ("mailgun-key", "Mailgun API key", r"\bkey-[0-9a-f]{32}\b"),
    ("private-key", "Private key block", r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY(?: BLOCK)?-----"),
    ("db-url-password", "Database address with a password in it",
     r"\b(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis|rediss)://[^\s:/@'\"]+:[^\s@'\"]{3,}@[^\s'\"]+"),
]
COMPILED = [(i, label, re.compile(rx)) for i, label, rx in SECRET_PATTERNS]
JWT_RE = re.compile(r"eyJ[A-Za-z0-9_\-]{10,}\.eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}")

PUBLIC_PREFIX_RE = re.compile(
    r"\b((?:NEXT_PUBLIC_|VITE_|REACT_APP_|EXPO_PUBLIC_|NUXT_PUBLIC_|GATSBY_|PUBLIC_)[A-Z0-9_]+)"
)
RISKY_NAME_RE = re.compile(
    r"SECRET|SERVICE_ROLE|SERVICEROLE|PRIVATE|PASSWORD|OPENAI|ANTHROPIC|CLAUDE|GEMINI|GROQ|"
    r"DEEPSEEK|ELEVENLABS|XAI_|MISTRAL|REPLICATE|STRIPE_SK|STRIPE_SECRET|DATABASE_URL|DB_URL|"
    r"SENDGRID|RESEND|TWILIO_AUTH|AWS_SECRET|ADMIN_KEY"
)
PLACEHOLDER_RE = re.compile(r"your|xxxx|example|placeholder|changeme|dummy|fake|<|\.\.\.", re.I)

FRONTEND_EXTS = {".html", ".htm", ".jsx", ".tsx", ".vue", ".svelte", ".astro"}
FRONTEND_DIR_HINTS = {
    "src", "public", "static", "app", "pages", "components", "client", "frontend", "web",
    "dist", "build", "out", ".next", "www", "assets",
}
SERVER_DIR_HINTS = {
    "api", "server", "backend", "functions", "supabase", "netlify", "lambda", "edge",
    "serverless", "routes", "scripts",
}
PUBLIC_BUILD_DIRS = {"public", "static", "dist", "build", "out", "www"}
CODE_EXTS = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".vue", ".svelte", ".astro", ".py", ".rb", ".php", ".go"}
TEST_PATH_RE = re.compile(r"(^|/)(tests?|__tests__|spec|e2e|fixtures?|mocks?)(/|$)|\.(test|spec)\.", re.I)
I18N_PATH_RE = re.compile(r"i18n|l10n|locale|translation|lang", re.I)
SENSITIVE_COLUMNS = {
    "is_pro", "pro", "plan", "tier", "credits", "balance", "role", "is_admin", "admin",
    "subscription_status", "subscription_tier", "is_paid", "paid", "premium", "is_premium",
}
SERVER_FILE_HINTS = re.compile(r"(\.server\.|route\.(?:js|ts)$|middleware\.(?:js|ts)$|^server\.)")


EXAMPLE_SUFFIXES = (".example", ".sample", ".template", ".dist", ".defaults")


def is_example_env(name):
    return (name.startswith(".env") or name.endswith(".env")) and name.endswith(EXAMPLE_SUFFIXES)


def is_env_file(name):
    if is_example_env(name):
        return False
    return name == ".env" or name.startswith(".env.") or name.endswith(".env")


def in_public_build(rel):
    parts = rel.lower().split("/")
    if len(parts) > 2 and parts[0] == ".next" and parts[1] == "static":
        return True
    return bool(set(parts[:-1]) & PUBLIC_BUILD_DIRS) and "server" not in parts[:-1]


def looks_frontend(rel, head=""):
    parts = rel.replace("\\", "/").split("/")
    name = parts[-1]
    if re.search(r"^\s*['\"]use server['\"]", head, re.M):
        return False
    if re.search(r"^\s*['\"]use client['\"]", head, re.M):
        return True
    if SERVER_FILE_HINTS.search(name):
        return False
    dirs = {p.lower() for p in parts[:-1]}
    if dirs & SERVER_DIR_HINTS:
        return False
    ext = os.path.splitext(name)[1].lower()
    if ext in FRONTEND_EXTS:
        return True
    if ext in {".js", ".ts", ".mjs", ".cjs"} and dirs & FRONTEND_DIR_HINTS:
        return True
    return False


def mask(value):
    value = value.strip()
    if len(value) <= 8:
        return value[:2] + "****"
    return value[:6] + "****" + value[-2:]


def jwt_role(token):
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        data = json.loads(base64.urlsafe_b64decode(payload.encode()).decode("utf-8", "ignore"))
        return data.get("role") if isinstance(data, dict) else None
    except Exception:
        return None


class Scanner:
    def __init__(self, root):
        self.root = os.path.abspath(root)
        self.findings = []
        self.files_scanned = 0
        self.git = self._is_git_repo()
        self.tracked = self._tracked_files() if self.git else set()
        self.sql_files = []
        self.sql_supabase = {}
        self.source_maps = []
        self.npm_audit = None

    # ---------- git helpers ----------
    def _run_git(self, *args):
        try:
            return subprocess.run(["git", "-C", self.root, *args], capture_output=True, text=True, timeout=20)
        except (OSError, subprocess.SubprocessError):
            return None

    def _is_git_repo(self):
        r = self._run_git("rev-parse", "--is-inside-work-tree")
        return bool(r and r.returncode == 0 and r.stdout.strip() == "true")

    def _tracked_files(self):
        r = self._run_git("ls-files", "-z")
        if not r or r.returncode != 0:
            return set()
        return {p for p in r.stdout.split("\0") if p}

    def _git_ignored(self, rel):
        r = self._run_git("check-ignore", "-q", "--no-index", rel)
        return bool(r and r.returncode == 0)

    def _gitignore_covers_env(self):
        path = os.path.join(self.root, ".gitignore")
        if not os.path.isfile(path):
            return False
        with open(path, encoding="utf-8", errors="ignore") as fh:
            lines = [l.strip() for l in fh if l.strip() and not l.strip().startswith("#")]
        return any(l.lstrip("/") in {".env", ".env*", ".env.*", "*.env", ".env.local", "**/.env"} for l in lines)

    # ---------- reporting ----------
    def add(self, severity, check, rel, line, what, why, fix):
        self.findings.append({
            "severity": severity, "check": check, "file": rel, "line": line,
            "what": what, "why": why, "fix": fix,
        })

    # ---------- walking ----------
    def walk(self):
        for dirpath, dirnames, filenames in os.walk(self.root):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for name in filenames:
                full = os.path.join(dirpath, name)
                rel = os.path.relpath(full, self.root).replace("\\", "/")
                if name.endswith(".map") and in_public_build(rel):
                    self.source_maps.append(rel)
                    continue
                if name in SKIP_FILES or os.path.splitext(name)[1].lower() in SKIP_EXTS:
                    continue
                try:
                    if os.path.getsize(full) > MAX_BYTES:
                        continue
                    with open(full, "rb") as fh:
                        raw = fh.read()
                except OSError:
                    continue
                if b"\0" in raw[:4096]:
                    continue
                self.files_scanned += 1
                text = raw.decode("utf-8", "ignore")
                self.scan_file(rel, name, text)
        self.check_project()

    def scan_file(self, rel, name, text):
        env_file = is_env_file(name)
        example = is_example_env(name)
        frontend = looks_frontend(rel, text[:400])
        lines = text.splitlines()
        if (env_file or example) and in_public_build(rel) and not example:
            self.add("critical", "env-file-public", rel, None,
                     "A .env file is inside a folder that gets published as part of the website.",
                     "Anyone could download it from your site by typing its address, along with every key in it.",
                     "Delete it from this folder, keep .env only in the project's main folder, and replace every key that was in it.")
        for n, line in enumerate(lines, 1):
            if "seatbelt-ignore" in line:
                continue
            self.scan_secrets(rel, n, line, env_file, example, frontend)
            self.scan_public_prefix(rel, n, line, env_file, frontend)
            if frontend and re.search(r"service_role|SERVICE_ROLE|serviceRole", line):
                strong = re.search(r"\w*SERVICE_ROLE\w*|serviceRole\w*|service_role_key|['\"]service_role['\"]", line)
                self.add("critical" if strong else "medium", "service-role-in-frontend", rel, n,
                         "The Supabase service_role (master) key is referenced in browser code.",
                         "That key ignores all database safety rules. Anyone could read or delete every row.",
                         "Use only the anon or publishable key in the browser. Move admin work into a server or edge function.")
            if frontend and "dangerouslyAllowBrowser" in line and re.search(r"dangerouslyAllowBrowser\s*:\s*true", line):
                self.add("high", "ai-client-in-browser", rel, n,
                         "An AI library is set to run in the browser (dangerouslyAllowBrowser: true).",
                         "That only works by sending your AI key to every visitor, who can then use it on your bill.",
                         "Call the AI from a server or edge function instead, and keep the key there.")
        ext = os.path.splitext(name)[1].lower()
        if ext in CODE_EXTS:
            self.scan_code(rel, lines, text, frontend)
        lower = name.lower()
        if lower.endswith(".sql"):
            self.sql_files.append((rel, text))
            self.sql_supabase[rel] = bool(re.search(r"supabase", rel, re.I) or re.search(r"auth\.uid\(\)|auth\.users|\bauthenticated\b|\banon\b|storage\.", text))
        if lower in {"firestore.rules", "storage.rules", "database.rules.json"} or lower.endswith(".rules"):
            self.scan_firebase(rel, lines)

    def scan_secrets(self, rel, n, line, env_file, example, frontend):
        hits = []
        for cid, label, rx in COMPILED:
            for m in rx.finditer(line):
                if cid == "db-url-password" and PLACEHOLDER_RE.search(m.group(0).split("@")[0]):
                    continue
                if cid == "openai-key" and m.group(0).startswith("sk-ant-"):
                    continue
                hits.append((cid, label, m.group(0)))
        for m in JWT_RE.finditer(line):
            if jwt_role(m.group(0)) == "service_role":
                hits.append(("supabase-service-role-jwt", "Supabase service_role key", m.group(0)))
        for cid, label, value in hits:
            shown = mask(value)
            if env_file:
                tracked = rel in self.tracked
                ignored = self._git_ignored(rel) if self.git else self._gitignore_covers_env()
                if tracked:
                    self.add("critical", "env-file-saved-in-git", rel, n,
                             f"{label} ({shown}) is in a .env file that git is saving.",
                             "If this project is ever uploaded to GitHub, the key goes with it, and stays in the history.",
                             "Run: git rm --cached " + rel + " , add .env to .gitignore, then replace the key in the provider's dashboard.")
                elif not ignored:
                    self.add("high", "env-file-not-ignored", rel, n,
                             f"{label} ({shown}) is in a .env file that .gitignore does not cover.",
                             "The next save point or upload could include it.",
                             "Add .env and .env.* to .gitignore before saving or uploading.")
                continue
            if example:
                self.add("high", "real-key-in-example", rel, n,
                         f"{label} ({shown}) looks real, but this example file is meant to be shared.",
                         "Example env files are usually uploaded to GitHub.",
                         "Replace it with a placeholder like your-key-here, and replace the real key in the provider's dashboard.")
                continue
            if cid == "stripe-test-secret":
                sev = "medium"
            elif frontend:
                sev = "critical"
            else:
                sev = "high"
            where = "browser code, so any visitor can read it" if frontend else "the code itself"
            self.add(sev, cid, rel, n,
                     f"{label} ({shown}) is written directly into {where}.",
                     "Anyone who sees this file or the live site can use the key, often to run up bills or read data.",
                     "Move it to .env or the platform's Secrets, read it on the server only, and replace the key because it may already be exposed.")

    def scan_public_prefix(self, rel, n, line, env_file, frontend):
        if not (env_file or frontend or rel.endswith((".js", ".ts", ".mjs", ".cjs", ".json", ".toml", ".yaml", ".yml"))):
            return
        for m in PUBLIC_PREFIX_RE.finditer(line):
            var = m.group(1)
            if "ANON" in var or "PUBLISHABLE" in var:
                continue
            if RISKY_NAME_RE.search(var.split("_", 1)[1] if "_" in var else var):
                self.add("high", "secret-behind-public-prefix", rel, n,
                         f"{var} has a public prefix but its name suggests a secret.",
                         "Variables starting NEXT_PUBLIC_, VITE_, REACT_APP_, EXPO_PUBLIC_ and similar are copied into the browser for anyone to read.",
                         "Rename it without the public prefix and use it only in server code (an API route or edge function).")

    def scan_code(self, rel, lines, text, frontend):
        is_test = bool(TEST_PATH_RE.search(rel))
        lower_rel = rel.lower()
        for n, line in enumerate(lines, 1):
            if "seatbelt-ignore" in line or is_test:
                continue
            if re.search(r"Access-Control-Allow-Origin['\"]?\s*[,:]\s*['\"]\*['\"]", line) or \
                    re.search(r"\borigin\s*:\s*['\"]\*['\"]", line) or re.search(r"\bcors\(\s*\)", line):
                creds = re.search(r"credentials\s*:\s*true|Allow-Credentials['\"]?\s*[,:]\s*['\"]?true", text)
                self.add("high" if creds else "medium", "cors-open", rel, n,
                         "This server accepts requests from any website (CORS set to everyone)." + (" It also allows logged-in requests." if creds else ""),
                         "Other websites could call your server from a visitor's browser, and with logins allowed they could act as that visitor.",
                         "List only your own site's address, for example origin: 'https://yourdomain.com'.")
            if re.search(r"\.run\([^)]*debug\s*=\s*True", line):
                self.add("high", "debug-mode", rel, n,
                         "The app is started with debug=True.",
                         "Debug mode can show your code and settings to visitors, and in Flask it lets anyone run commands on your server.",
                         "Turn debug off for the live site, for example read it from an environment variable that is off by default.")
            elif re.match(r"\s*DEBUG\s*=\s*True\b", line) and rel.endswith("settings.py"):
                self.add("medium", "debug-mode", rel, n,
                         "Django DEBUG is set to True.",
                         "Error pages would show your settings and code to anyone if this reaches the live site.",
                         "Use DEBUG = os.environ.get('DJANGO_DEBUG') == '1' and leave it unset on the live site.")
            m = re.search(r"(?i)\b\w*(?:password|passwd|pwd|secret)\w*['\"]?\s*[:=]\s*['\"]([^'\"\s]{8,})['\"]", line)
            if m and not PLACEHOLDER_RE.search(m.group(1)) and "env" not in m.group(1).lower() and "${" not in m.group(1) \
                    and not re.fullmatch(r"[A-Z0-9_]+|[a-z]+(?:[-_][a-z]+)+|https?://\S*", m.group(1)) \
                    and m.group(1).isascii() and re.search(r"[A-Za-z]", m.group(1)) \
                    and re.search(r"[0-9]|[^A-Za-z0-9]", m.group(1)) and not I18N_PATH_RE.search(rel):
                if not any(f["file"] == rel and f["line"] == n for f in self.findings):
                    self.add("high" if frontend else "medium", "hardcoded-password", rel, n,
                             "A password or secret seems to be written directly into the code (" + mask(m.group(1)) + ").",
                             "Anyone who can read this file can use it" + (", and this file is sent to visitors' browsers." if frontend else "."),
                             "Move it to .env or the platform's Secrets and read it on the server. If it is a real password, change it.")
        if "webhook" in lower_rel and re.search(r"stripe", text, re.I) and not re.search(
                r"constructEvent|constructEventAsync|construct_event|verifyHeader|verify_header|Webhook::constructEvent", text):
            self.add("high", "webhook-not-verified", rel, None,
                     "This Stripe webhook does not seem to check Stripe's signature.",
                     "Anyone could send a fake 'payment succeeded' message and get things for free.",
                     "Verify every webhook with stripe.webhooks.constructEvent(rawBody, signature, webhookSecret) before trusting it.")
        if re.search(r"(success|thank)", lower_rel) and re.search(r"\.(update|upsert|insert)\(", text) and \
                re.search(r"is_pro|isPro|['\"]pro['\"]|plan|credits|premium|['\"]paid['\"]", text):
            self.add("high", "success-page-grant", rel, None,
                     "This success or thank-you page seems to change a plan, credits or payment status.",
                     "Anyone can visit a success page without paying, so they could get paid features for free.",
                     "Only change plans or payment status in a verified payment webhook on the server. The success page should just show the result.")

    def analyse_sql(self):
        """Read every .sql file in path order (migration order) and check database rules."""
        position = 0
        created, enabled, tables_cols, risky_policies, guarded = {}, {}, {}, {}, set()
        for rel, text in sorted(self.sql_files):
            clean = re.sub(r"--[^\n]*", "", text)
            line_of = lambda i: clean[:i].count("\n") + 1
            events = []
            for m in re.finditer(r"create\s+table\s+(?:if\s+not\s+exists\s+)?([\w\".]+)\s*\((.*?)\);", clean, re.I | re.S):
                events.append((m.start(), "create", m.group(1), m.group(2)))
            for m in re.finditer(r"alter\s+table\s+(?:if\s+exists\s+)?(?:only\s+)?([\w\".]+)\s+enable\s+row\s+level\s+security", clean, re.I):
                events.append((m.start(), "enable", m.group(1), None))
            for m in re.finditer(r"create\s+policy\s+(?:\"[^\"]*\"|\w+)\s+on\s+([\w\".]+)(.*?);", clean, re.I | re.S):
                events.append((m.start(), "policy", m.group(1), m.group(2)))
            for m in re.finditer(r"revoke\s+(?:update|all)[^;]*\bon\s+(?:table\s+)?([\w\".]+)[^;]*\bfrom\b[^;]*authenticated", clean, re.I):
                events.append((m.start(), "revoke", m.group(1), None))
            for pos, kind, raw_name, body in sorted(events):
                name = raw_name.replace('"', "").lower()
                short = name.split(".")[-1]
                key = short if not name.startswith(("auth.", "storage.")) else name
                position += 1
                if kind == "create":
                    created.setdefault(key, (rel, line_of(pos), position, raw_name.replace('"', "")))
                    cols = {c.strip().split()[0].strip('"').lower() for c in re.split(r",(?![^(]*\))", body or "") if c.strip()}
                    tables_cols[key] = cols
                elif kind == "enable":
                    enabled.setdefault(key, []).append((rel, line_of(pos), position))
                elif kind == "policy":
                    cmd = re.search(r"\bfor\s+(all|select|insert|update|delete)\b", body, re.I)
                    cmd = cmd.group(1).lower() if cmd else "all"
                    if cmd in {"all", "update", "insert"} and not re.search(r"is_staff|is_admin\(|service_role", body, re.I):
                        risky_policies.setdefault(key, (rel, line_of(pos), cmd))
                elif kind == "revoke":
                    guarded.add(key)
            for m in re.finditer(r"alter\s+table\s+([\w\".]+)\s+disable\s+row\s+level\s+security", clean, re.I):
                self.add("high", "rls-disabled", rel, line_of(m.start()),
                         f"Row Level Security is switched off for '{m.group(1)}'.",
                         "That opens the whole table to anyone with the public key.",
                         "Turn it back on and write a policy for what is needed, instead of disabling it.")
            for m in re.finditer(r"using\s*\(\s*true\s*\)|with\s+check\s*\(\s*true\s*\)", clean, re.I):
                self.add("medium", "policy-allows-everyone", rel, line_of(m.start()),
                         "A database policy says '(true)', which means everyone.",
                         "Fine for truly public data like a list of products, dangerous for anything personal.",
                         "If this table holds personal data, change it to something like using ((select auth.uid()) = user_id).")
            for m in re.finditer(r"insert\s+into\s+storage\.buckets[^;]*\btrue\b[^;]*;", clean, re.I | re.S):
                self.add("medium", "public-bucket", rel, line_of(m.start()),
                         "A storage bucket is created as public.",
                         "Anyone with a file's address can download it. Fine for product photos, not for personal uploads.",
                         "Make the bucket private and share files with signed links that expire.")
            for m in re.finditer(r"create\s+(?:or\s+replace\s+)?function\s+([\w\".]+)(.*?)\$\$", clean, re.I | re.S):
                head = m.group(2)
                if re.search(r"security\s+definer", head, re.I) and not re.search(r"set\s+search_path", head, re.I):
                    self.add("medium", "definer-without-search-path", rel, line_of(m.start()),
                             f"Function '{m.group(1)}' runs with owner rights but does not fix its search_path.",
                             "Owner-rights functions skip the usual rules; without a fixed search_path they can be tricked into running the wrong code.",
                             "Add: set search_path = '' and use full names like public.my_table inside the function.")
        for key, (rel, line, pos, shown) in created.items():
            if key.startswith(("auth.", "storage.", "private.")):
                continue
            enables = enabled.get(key, [])
            if not enables:
                supa = self.sql_supabase.get(rel, False)
                self.add("high" if supa else "medium", "table-without-rls", rel, line,
                         f"Table '{shown}' is created without Row Level Security being switched on in any .sql file here.",
                         "On Supabase, a table without RLS can be read and changed by anyone holding the public key, which is in your website.",
                         f"Add straight after creating it: alter table {shown} enable row level security; then add policies so people only see their own rows. If you turned RLS on in the dashboard instead, check it there.")
            elif all(p < pos for _, _, p in enables):
                erel, eline, _ = enables[0]
                self.add("high", "rls-before-create", erel, eline,
                         f"Row Level Security for '{shown}' is switched on before the table is created.",
                         "On a fresh database that line does nothing, so the table ends up with no protection even though the file looks right.",
                         f"Move 'alter table {shown} enable row level security;' to straight after the create table statement.")
            cols = tables_cols.get(key, set()) & SENSITIVE_COLUMNS
            if not re.search(r"profile|user|member|account|customer|team|staff|org|subscri|entitle|wallet|billing", key):
                cols -= {"role", "admin", "paid", "plan", "tier"}
            if cols and key in risky_policies and key not in guarded:
                prel, pline, cmd = risky_policies[key]
                self.add("high" if cmd in {"update", "all"} else "medium", "user-can-edit-entitlement", prel, pline,
                         f"Users have a {cmd} policy on '{shown}', which has the column(s) {', '.join(sorted(cols))}.",
                         "If people can update their own row, they may be able to give themselves a paid plan, credits or admin rights from the browser.",
                         "Move plans, credits and roles into a separate table with only a read policy, changed by server code after a verified payment, or limit updates to safe columns (revoke update, then grant update on named columns).")

    def scan_firebase(self, rel, lines):
        for n, line in enumerate(lines, 1):
            if "seatbelt-ignore" in line:
                continue
            if re.search(r"if\s+true\s*;", line) or re.search(r"\"\.(?:read|write)\"\s*:\s*(?:true|\"true\")", line):
                self.add("high", "firebase-open-rules", rel, n,
                         "A Firebase security rule lets anyone read or write.",
                         "Anyone on the internet could read, change or delete this data.",
                         "Require sign-in and ownership, for example: allow read, write: if request.auth != null && request.auth.uid == userId;")
            elif re.search(r"request\.time\s*<\s*timestamp\.date\(", line):
                self.add("high", "firebase-test-mode", rel, n,
                         "These are Firebase 'test mode' rules: open to everyone until a date.",
                         "Until that date anyone can read and change all the data; after it, the app stops working.",
                         "Replace them with rules that check who is signed in and whose data it is (see the Firebase playbook).")

    def run_npm_audit(self):
        lock = os.path.join(self.root, "package-lock.json")
        if not os.path.isfile(lock):
            self.npm_audit = "skipped: no package-lock.json"
            return
        try:
            r = subprocess.run(["npm", "audit", "--json", "--omit=dev"], cwd=self.root,
                               capture_output=True, text=True, timeout=120)
            data = json.loads(r.stdout or "{}")
        except (OSError, subprocess.SubprocessError, ValueError) as exc:
            self.npm_audit = f"could not run npm audit ({exc.__class__.__name__})"
            return
        counts = (data.get("metadata") or {}).get("vulnerabilities") or {}
        if not counts:
            self.npm_audit = "could not read npm audit results (offline?)"
            return
        self.npm_audit = ", ".join(f"{k}: {v}" for k, v in counts.items() if k != "total")
        serious = counts.get("critical", 0) + counts.get("high", 0)
        if serious:
            self.add("high" if counts.get("critical", 0) else "medium", "vulnerable-packages", "package-lock.json", None,
                     f"npm audit found {serious} serious known problem(s) in packages this app uses ({self.npm_audit}).",
                     "Attackers look for apps using packages with known holes.",
                     "Run 'npm audit fix', make a save point first, then check the app still works. Ask before using --force, which can break things.")

    def check_git_history(self):
        if not self.git:
            return
        r = self._run_git("log", "--all", "--pretty=format:", "--name-only", "--diff-filter=A")
        if not r or r.returncode != 0:
            return
        names = sorted({l.strip() for l in r.stdout.splitlines() if l.strip() and is_env_file(os.path.basename(l.strip()))})
        for n in names:
            if n in self.tracked:
                continue
            self.add("critical", "env-file-in-git-history", n, None,
                     "A .env file was saved in this project's history in the past, even though it is not there now.",
                     "Anyone with a copy of the project (for example on GitHub) can still read the old version and every key in it.",
                     "Replace every key that was in that file. Removing it from history is optional once the keys are replaced.")

    def check_project(self):
        self.analyse_sql()
        self.check_git_history()
        if self.source_maps:
            self.add("low", "public-source-maps", self.source_maps[0], None,
                     f"{len(self.source_maps)} source map file(s) are in the published build.",
                     "Source maps let anyone read your original code. Usually fine, but it makes any secret or private logic in the code easy to find.",
                     "If the code should stay private, turn source maps off in the build settings for the live site.")
        env_files = []
        for dirpath, dirnames, filenames in os.walk(self.root):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for name in filenames:
                if is_env_file(name):
                    env_files.append(os.path.relpath(os.path.join(dirpath, name), self.root).replace("\\", "/"))
        for rel in env_files:
            if rel in self.tracked:
                if not any(f["file"] == rel and f["check"] == "env-file-saved-in-git" for f in self.findings):
                    self.add("critical", "env-file-saved-in-git", rel, None,
                             "A .env file is being saved by git.",
                             "Secret files saved in git get uploaded with the project and stay in its history.",
                             "Run: git rm --cached " + rel + " , add .env to .gitignore, and replace any keys that were in it.")
        has_ignore_rule = self._gitignore_covers_env()
        if self.git and not os.path.isfile(os.path.join(self.root, ".gitignore")):
            self.add("medium", "no-gitignore", ".gitignore", None,
                     "This project uses git but has no .gitignore file.",
                     "Without it, secret files and bulky folders can be saved and uploaded by accident.",
                     "Create .gitignore with at least: .env, .env.*, !.env.example, node_modules/")
        elif not has_ignore_rule and not env_files and os.path.isfile(os.path.join(self.root, ".gitignore")):
            self.add("low", "gitignore-missing-env", ".gitignore", None,
                     ".gitignore does not mention .env yet.",
                     "If you add secret keys later, they could be saved and uploaded by accident.",
                     "Add these lines to .gitignore: .env  .env.*  !.env.example")

    # ---------- output ----------
    def sorted_findings(self):
        """Sort worst first, drop exact repeats, and fold many hits of one check in one file."""
        seen, out, per_file = set(), [], {}
        for f in sorted(self.findings, key=lambda f: (SEVERITY_ORDER.index(f["severity"]), f["file"], f["line"] or 0)):
            key = (f["check"], f["file"], f["line"])
            if key in seen:
                continue
            seen.add(key)
            group = (f["check"], f["file"])
            if group in per_file and f["check"] not in NO_FOLD:
                per_file[group]["more"] = per_file[group].get("more", 0) + 1
                continue
            f = dict(f)
            per_file[group] = f
            out.append(f)
        for f in out:
            more = f.pop("more", 0)
            if more:
                f["what"] += f" (and {more} more line{'s' if more > 1 else ''} like this in the same file)"
        return out


def print_report(scanner, findings):
    counts = {s: sum(1 for f in findings if f["severity"] == s) for s in SEVERITY_ORDER}
    print("Seatbelt ship check")
    print(f"Folder: {scanner.root}")
    print(f"Files checked: {scanner.files_scanned}  |  git: {'yes' if scanner.git else 'no'}")
    print("")
    if not findings:
        print("PASSED: no leaked keys or risky settings found in these files.")
        print("This is a quick check, not a full audit. Still do the manual ship check (logins, database")
        print("rules in the dashboard, rate limits, spending limits).")
        return
    labels = {"critical": "MUST FIX NOW", "high": "FIX BEFORE GOING LIVE", "medium": "WORTH A LOOK", "low": "TIP"}
    for sev in SEVERITY_ORDER:
        group = [f for f in findings if f["severity"] == sev]
        if not group:
            continue
        print(f"== {labels[sev]} ({sev}, {len(group)}) ==")
        for f in group:
            loc = f["file"] + (f":{f['line']}" if f["line"] else "")
            print(f"- {loc}")
            print(f"  What: {f['what']}")
            print(f"  Why it matters: {f['why']}")
            print(f"  Fix: {f['fix']}")
        print("")
    blocking = counts["critical"] + counts["high"]
    if blocking:
        print(f"NOT READY: {blocking} serious problem(s) to fix before going live.")
        print("If any key was exposed, replace it in the provider's dashboard. Deleting it from the code is not enough.")
    else:
        print("No serious problems found. Review the items above, then do the manual ship check.")


MANUAL_CHECKS = [
    "Logins are checked on the server for every private page and action",
    "Each user can only see and change their own data (tested with two accounts)",
    "Database rules (RLS) are on for every table in the live dashboard, not just in files",
    "Users cannot change their own plan, credits or role",
    "Payments are only confirmed by a verified webhook",
    "Spending caps and alerts are set on every paid service",
    "Rate limits on AI calls, sign-up and messages",
    "Environment variables are set on the host, and the site was redeployed",
    "Privacy notice, and terms if taking money",
    "Stranger test: private window, private pages, other users' data, page source",
]


def write_report(scanner, findings, path):
    import datetime
    import html as html_lib
    when = datetime.datetime.now().strftime("%d %b %Y, %H:%M")
    counts = {s: sum(1 for f in findings if f["severity"] == s) for s in SEVERITY_ORDER}
    blocking = counts["critical"] + counts["high"]
    verdict = (f"NOT READY: {blocking} serious problem(s) to fix before going live."
               if blocking else "No serious problems found in the files. Finish the manual checks below.")
    labels = {"critical": "Must fix now", "high": "Fix before going live", "medium": "Worth a look", "low": "Tip"}
    if path.lower().endswith((".html", ".htm")):
        e = html_lib.escape
        rows = []
        for f in findings:
            loc = f["file"] + (f":{f['line']}" if f["line"] else "")
            rows.append(f"<div class='f {f['severity']}'><p class='sev'>{e(labels[f['severity']])}</p>"
                        f"<p class='loc'>{e(loc)}</p><p><b>What:</b> {e(f['what'])}</p>"
                        f"<p><b>Why it matters:</b> {e(f['why'])}</p><p><b>Fix:</b> {e(f['fix'])}</p></div>")
        manual = "".join(f"<li><input type='checkbox'> {e(m)}</li>" for m in MANUAL_CHECKS)
        doc = f"""<!doctype html><html lang="en-GB"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Seatbelt ship check</title>
<style>body{{font-family:system-ui,sans-serif;max-width:760px;margin:2rem auto;padding:0 1rem;line-height:1.5;color:#1a1a1a}}
.verdict{{padding:1rem;border-radius:8px;font-weight:600;background:{'#fde8e8' if blocking else '#e6f6ea'}}}
.f{{border-left:6px solid #999;padding:.5rem 1rem;margin:1rem 0;background:#fafafa}}
.critical{{border-color:#b00020}}.high{{border-color:#e65100}}.medium{{border-color:#f9a825}}.low{{border-color:#1565c0}}
.sev{{font-weight:700;margin:0}}.loc{{font-family:monospace;margin:0 0 .5rem}}li{{margin:.3rem 0;list-style:none}}</style></head><body>
<h1>Seatbelt ship check</h1><p>{e(when)} | {e(scanner.root)} | {scanner.files_scanned} files checked</p>
<p class="verdict">{e(verdict)}</p>
<p>Critical {counts['critical']} | High {counts['high']} | Medium {counts['medium']} | Low {counts['low']}</p>
{''.join(rows) or '<p>No findings in the files.</p>'}
{f'<p><b>npm audit:</b> {e(scanner.npm_audit)}</p>' if scanner.npm_audit else ''}
<h2>Still to check by hand</h2><p>The scanner reads files only. It cannot see your live database settings or hosting dashboard.</p>
<ul>{manual}</ul>
<p>If any key was ever exposed, replace it in the provider's dashboard. Deleting it from the code is not enough.</p>
<p><small>Made with Seatbelt. A quick check, not a full security audit.</small></p></body></html>"""
    else:
        out = [f"# Seatbelt ship check", "", f"{when} | `{scanner.root}` | {scanner.files_scanned} files checked", "",
               f"**{verdict}**", "",
               f"Critical {counts['critical']} | High {counts['high']} | Medium {counts['medium']} | Low {counts['low']}", ""]
        for sev in SEVERITY_ORDER:
            group = [f for f in findings if f["severity"] == sev]
            if not group:
                continue
            out += [f"## {labels[sev]} ({len(group)})", ""]
            for f in group:
                loc = f["file"] + (f":{f['line']}" if f["line"] else "")
                out += [f"- [ ] `{loc}`", f"  - What: {f['what']}", f"  - Why it matters: {f['why']}", f"  - Fix: {f['fix']}"]
            out.append("")
        if scanner.npm_audit:
            out += [f"npm audit: {scanner.npm_audit}", ""]
        out += ["## Still to check by hand", "",
                "The scanner reads files only. It cannot see your live database settings or hosting dashboard.", ""]
        out += [f"- [ ] {m}" for m in MANUAL_CHECKS]
        out += ["", "If any key was ever exposed, replace it in the provider's dashboard. Deleting it from the code is not enough.",
                "", "_Made with Seatbelt. A quick check, not a full security audit._", ""]
        doc = "\n".join(out)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(doc)


def main(argv):
    usage = "Usage: python3 check_secrets.py [project_folder] [--json] [--report FILE.md|FILE.html] [--audit]"
    args, flags, report = [], set(), None
    it = iter(argv)
    for a in it:
        if a == "--report":
            report = next(it, None)
            if not report:
                print(usage, file=sys.stderr)
                return 2
        elif a.startswith("--report="):
            report = a.split("=", 1)[1]
        elif a.startswith("-"):
            flags.add(a)
        else:
            args.append(a)
    if "--help" in flags or "-h" in flags:
        print(__doc__)
        return 0
    unknown = flags - {"--json", "--help", "--audit"}
    if unknown or len(args) > 1:
        print(usage, file=sys.stderr)
        return 2
    root = args[0] if args else "."
    if not os.path.isdir(root):
        print(f"Folder not found: {root}", file=sys.stderr)
        return 2
    scanner = Scanner(root)
    scanner.walk()
    if "--audit" in flags:
        scanner.run_npm_audit()
    findings = scanner.sorted_findings()
    blocking = any(f["severity"] in {"critical", "high"} for f in findings)
    if "--json" in flags:
        print(json.dumps({
            "root": scanner.root, "files_scanned": scanner.files_scanned, "git": scanner.git,
            "ready": not blocking, "findings": findings,
        }, indent=2))
    else:
        print_report(scanner, findings)
    if report:
        write_report(scanner, findings, report)
        if "--json" not in flags:
            print(f"Report saved to {report}")
    return 1 if blocking else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
