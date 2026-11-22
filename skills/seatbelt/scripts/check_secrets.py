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


def looks_placeholder(value):
    """Documentation-style keys such as sk_live_XXXXXXXX or sk-proj-************."""
    return bool(re.search(r"[Xx*]{8,}|0{12,}|your[_-]?|placeholder|redacted", value, re.I))

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


PUBLIC_ENV_NAME = re.compile(r"^(?:(?:VITE|NEXT_PUBLIC|EXPO_PUBLIC|PUBLIC|REACT_APP|NUXT_PUBLIC)_)?"
                             r"(?:SUPABASE_(?:URL|PROJECT_ID|PUBLISHABLE_KEY|ANON_KEY|PROJECT_REF)|"
                             r"FIREBASE_(?:AUTH_DOMAIN|PROJECT_ID|STORAGE_BUCKET|MESSAGING_SENDER_ID|APP_ID|MEASUREMENT_ID)|"
                             r"STRIPE_PUBLISHABLE_KEY|SITE_URL|APP_URL|BASE_URL|APP_NAME)$")


def env_only_public(path):
    """True when every value in a .env file is something meant to be public."""
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    except OSError:
        return False
    names = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        name = name.replace("export ", "").strip()
        value = value.strip().strip("'\"")
        if any(rx.search(value) for _, _, rx in COMPILED) or jwt_role(value) == "service_role":
            return False
        if not PUBLIC_ENV_NAME.match(name):
            return False
        names.append(name)
    return bool(names)


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
        self.paid_services = {}
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
        self._firebase_config = "authDomain" in text and "projectId" in text
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
                         "Use only the publishable (or anon) key in the browser. Move admin work into a server or edge function.")
        ext = os.path.splitext(name)[1].lower()
        if ext in CODE_EXTS:
            self.scan_code(rel, lines, text, frontend)
            self.scan_costs(rel, lines, text, frontend)
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
                if cid == "db-url-password" and (PLACEHOLDER_RE.search(m.group(0).split("@")[0]) or re.search(
                        r":(?:password|pass|pwd|secret|\*+)@", m.group(0), re.I)):
                    continue
                if looks_placeholder(m.group(0)):
                    continue
                if cid == "openai-key" and m.group(0).startswith("sk-ant-"):
                    continue
                hits.append((cid, label, m.group(0)))
        for m in JWT_RE.finditer(line):
            if jwt_role(m.group(0)) == "service_role":
                hits.append(("supabase-service-role-jwt", "Supabase service_role key", m.group(0)))
        for cid, label, value in hits:
            shown = mask(value)
            if cid == "google-api-key" and ("FIREBASE" in line.upper() or getattr(self, "_firebase_config", False)):
                self.add("low", "firebase-web-key", rel, n,
                         f"A Firebase web key ({shown}) is in the project.",
                         "Firebase web keys are designed to be public, so this is not a leak by itself. But an unrestricted key can be reused for other Google services on your bill.",
                         "In Google Cloud > APIs & Services > Credentials, restrict the key to your website address and the Firebase APIs it needs. Your Firebase security rules are what protect the data.")
                continue
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
            if re.search(r"dangerouslyAllowBrowser\s*:\s*true", line):
                self.add("high", "ai-key-in-browser", rel, n,
                         "An AI library is set to run in the browser (dangerouslyAllowBrowser: true).",  # seatbelt-ignore
                         "Your AI key is sent to every visitor, who can copy it and run up your bill.",
                         "Call the AI from a server function instead, keep the key in Secrets, and cap use per person.")
        body_names = set()
        for m in re.finditer(r"(?:const|let|var)\s*\{([^}]*)\}\s*=\s*(?:await\s+)?(?:req|request)\.(?:json\(\)|body)", text):
            body_names |= {x.split(":")[-1].split("=")[0].strip() for x in m.group(1).split(",") if x.strip()}
        for n, line in enumerate(lines, 1):
            m = re.search(r"\b(?:unit_amount|amount)\s*:\s*(?:Number\()?\s*((?:req\.body|body|request\.body)\.\w+|\w+)", line)
            if m and not frontend and "seatbelt-ignore" not in line and not TEST_PATH_RE.search(rel) and re.search(r"stripe|checkout|paymentIntents", text, re.I) and (
                    m.group(1) in body_names or "." in m.group(1)):
                self.add("high", "price-from-browser", rel, n,
                         "The amount charged seems to come from what the browser sent.",
                         "Anyone can edit that request and pay 1p for anything.",
                         "Look the price up on the server (a Stripe Price ID or your own price list) from the item's ID, never from the request.")
        if "webhook" in lower_rel and re.search(r"stripe|checkout\.session\.|payment_intent\.|invoice\.paid|customer\.subscription\.", text, re.I) and not re.search(
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

    def scan_costs(self, rel, lines, text, frontend):
        """Cost-runaway guard: paid services, AI calls anyone can trigger, timers and loops."""
        if TEST_PATH_RE.search(rel):
            return
        for name, rx, _ in PAID_SERVICES:
            if re.search(rx, text, re.M):
                self.paid_services.setdefault(name, []).append(rel)
        calls = [n for n, line in enumerate(lines, 1) if AI_CALL_RE.search(line)]
        if not calls:
            return
        first = calls[0]
        if not LIMIT_HINT_RE.search(text):
            open_to_all = not AUTH_HINT_RE.search(text)
            edge = rel.startswith("supabase/functions/")
            self.add("medium", "cost-ai-no-limit", rel, first,
                     "This code calls a paid AI service, and there is no sign of a per-person limit"
                     + (" or a login check." if open_to_all else "."),
                     ("Anyone who finds it could call it in a loop and run up your bill"
                      + (" (Supabase functions accept your public key, which is in your website)." if edge and open_to_all else ".")),
                     "Require a logged-in user, count requests per user per day in the database, and refuse politely over the limit (for example 30 a day). If a limit already lives elsewhere (for example in middleware), you can ignore this.")
        if not MAX_TOKENS_RE.search(text):
            self.add("low", "cost-no-max-tokens", rel, first,
                     "AI calls here do not set a maximum answer length.",
                     "Long answers cost more, and a bug or a trick prompt can make every answer very long.",
                     "Set max_tokens (or the provider's equivalent) to a sensible number for this feature.")
        indent = lambda l: len(l) - len(l.lstrip())
        loop_re = re.compile(r"\bfor\s*\(|\bwhile\s*\(|\.map\(\s*(?:async\s*)?\(?[\w,\s{}]*\)?\s*=>\s*\{?\s*$|\.forEach\(|^\s*for\s+\w+\s+in\b")
        for n in calls:
            call_indent = indent(lines[n - 1])
            near = [l for l in lines[max(0, n - 5):n - 1] if loop_re.search(l) and indent(l) < call_indent]
            if near:
                self.add("low", "cost-ai-in-loop", rel, n,
                         "An AI call sits inside a loop.",
                         "If the loop can run over a long list, one click could trigger many paid calls. A short, fixed list (such as trying two or three models) is fine.",
                         "Cap how many items are processed per request, or batch them into one call.")
                break
        if frontend and re.search(r"setInterval\s*\(", text):
            self.add("medium", "cost-timer", rel, first,
                     "This page code has a timer (setInterval) in a file that calls a paid AI service.",
                     "Every open browser tab could keep calling it and spending money.",
                     "Only call the AI when the person asks, or slow the timer right down and stop it when the tab is hidden.")

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
                start = clean.rfind(";", 0, m.start()) + 1
                stmt = clean[start:m.start()]
                pol = re.search(r"create\s+policy\s+(?:\"[^\"]*\"|\w+)\s+on\s+([\w\".]+)", stmt, re.I)
                if pol and re.search(r"\bto\s+service_role\b", stmt, re.I):
                    continue
                cmd = re.search(r"\bfor\s+(all|select|insert|update|delete)\b", stmt, re.I)
                cmd = cmd.group(1).lower() if cmd else "all"
                table = pol.group(1).replace('"', "") if pol else "a table"
                personal = re.search(r"profile|user|member|account|customer|message|chat|order|payment|invoice|booking|"
                                     r"journal|note|diary|patient|health|address|contact|document|upload|private", table, re.I)
                if cmd == "select":
                    self.add("medium" if personal else "low", "policy-allows-everyone", rel, line_of(m.start()),
                             f"Everyone can read '{table}' (a policy says '(true)').",
                             "Fine for truly public data like a list of products or a leaderboard, dangerous for anything personal.",
                             "If this table holds personal data, change it to something like using ((select auth.uid()) = user_id).")
                elif cmd == "insert":
                    self.add("medium", "policy-allows-everyone", rel, line_of(m.start()),
                             f"Anyone can add rows to '{table}' (a policy says '(true)').",
                             "Fine for a public contact form or waiting list, but bots can fill it with junk, and it is wrong for anything tied to a user.",
                             "If rows belong to a user, use with check ((select auth.uid()) = user_id). For public forms, add a rate limit or captcha.")
                else:
                    self.add("high", "policy-allows-everyone", rel, line_of(m.start()),
                             f"Anyone can {'change or delete' if cmd != 'delete' else 'delete'} rows in '{table}' (a '{cmd}' policy says '(true)').",
                             "Any visitor holding the public key could change or wipe this data.",
                             "Limit it to the owner, for example using ((select auth.uid()) = user_id), or to staff only.")
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
                         f"Users can {'change' if cmd != 'insert' else 'create'} their own row in '{shown}' (a '{cmd}' policy), and it has the column(s) {', '.join(sorted(cols))}.",
                         "If people can update their own row, they may be able to give themselves a paid plan, credits or admin rights from the browser.",
                         "Move plans, credits and roles into a separate table with only a read policy, changed by server code after a verified payment, or limit updates to safe columns (revoke update, then grant update on named columns).")

    def scan_firebase(self, rel, lines):
        for n, line in enumerate(lines, 1):
            if "seatbelt-ignore" in line:
                continue
            read_only = re.search(r"allow\s+(?:read|get|list)(?:\s*,\s*(?:read|get|list))*\s*:\s*if\s+true\s*;", line) \
                or re.search(r"\"\.read\"\s*:\s*(?:true|\"true\")", line)
            if read_only:
                self.add("low", "firebase-public-read", rel, n,
                         "A Firebase rule lets anyone read this data (but not change it).",
                         "Fine for public content like recipes or a blog, wrong for anything personal.",
                         "If this holds personal data, require sign-in and ownership: allow read: if request.auth != null && request.auth.uid == resource.data.owner;")
            elif re.search(r"if\s+true\s*;", line) or re.search(r"\"\.(?:read|write)\"\s*:\s*(?:true|\"true\")", line):
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
                if env_only_public(os.path.join(self.root, rel)):
                    self.add("low", "env-file-saved-public-only", rel, None,
                             "A .env file is saved in git, but it only holds public values (like the Supabase address and publishable key).",
                             "That is fine today (app builders such as Lovable do this). The risk is adding a real secret to this file later.",
                             "Never put a secret key in this file. Keep secrets in the platform's Secrets instead, or add .env to .gitignore.")
                    continue
                if not any(f["file"] == rel and f["check"] == "env-file-saved-in-git" for f in self.findings):
                    self.add("critical", "env-file-saved-in-git", rel, None,
                             "A .env file is being saved by git.",
                             "Secret files saved in git get uploaded with the project and stay in its history.",
                             "Run: git rm --cached " + rel + " , add .env to .gitignore, and replace any keys that were in it.")
        vercel = os.path.join(self.root, "vercel.json")
        if os.path.isfile(vercel):
            try:
                with open(vercel, encoding="utf-8") as fh:
                    crons = (json.load(fh) or {}).get("crons") or []
            except (ValueError, OSError, AttributeError):
                crons = []
            for c in crons if isinstance(crons, list) else []:
                sched = str((c or {}).get("schedule", "")).split()
                if sched and sched[0] in ("*", "*/1", "*/2", "*/5"):
                    self.add("medium", "cost-frequent-cron", "vercel.json", None,
                             f"A scheduled job runs very often ({' '.join(sched)} calls {c.get('path', 'a route')}).",
                             "Jobs that run every few minutes add up, especially if they call paid services.",
                             "Run it as rarely as the feature allows (for example hourly or daily) and check what it calls.")
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


KEYISH = re.compile(r"key|secret|token|env|jwt|password|service-role", re.I)


def print_report(scanner, findings, title="Seatbelt ship check", subject=None, counted=None, sections=()):
    counts = {s: sum(1 for f in findings if f["severity"] == s) for s in SEVERITY_ORDER}
    print(title)
    print(subject or f"Folder: {scanner.root}")
    print(counted or f"Files checked: {scanner.files_scanned}  |  git: {'yes' if scanner.git else 'no'}")
    print("")
    def show_sections():
        for heading, lines in sections:
            if lines:
                print(f"== {heading} ==")
                for line in lines:
                    print(f"- {line}")
                print("")
    if not findings:
        show_sections()
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
    paid = getattr(scanner, "paid_services", None)
    if paid:
        print("== PAID SERVICES FOUND: check each has a spending cap ==")
        for name, cap in paid_caps(paid):
            print(f"- {name}: {cap}")
        print("")
    show_sections()
    blocking = counts["critical"] + counts["high"]
    if blocking:
        print(f"NOT READY: {blocking} serious problem(s) to fix before going live.")
        if any(KEYISH.search(f["check"]) for f in findings if f["severity"] in ("critical", "high")):
            print("If any key was exposed, replace it in the provider's dashboard. Deleting it from the code is not enough.")
    else:
        print("No serious problems found. Review the items above, then do the manual ship check.")


PAID_SERVICES = [
    # name, pattern in code, where the cap lives (plain English)
    ("OpenAI", r"from ['\"]openai['\"]|require\(['\"]openai['\"]\)|api\.openai\.com|^\s*(?:from|import) openai",
     "platform.openai.com: set a project budget and usage alerts; keep prepaid credit low with auto-recharge off"),
    ("Anthropic", r"@anthropic-ai/sdk|api\.anthropic\.com|^\s*(?:from|import) anthropic",
     "console.anthropic.com: set spend limits and keep prepaid credit low"),
    ("Google Gemini or Google Cloud", r"@google/genai|@google/generative-ai|generativelanguage\.googleapis|google\.generativeai|vertexai",
     "Google Cloud Billing: create a budget with alerts (alerts only, they do not stop spending) and restrict the key"),
    ("Replicate", r"replicate\.com/v1|from ['\"]replicate['\"]|^\s*import replicate", "replicate.com account billing: set a spend limit if offered and watch usage"),
    ("ElevenLabs", r"elevenlabs", "elevenlabs.io subscription: check the character quota and overage setting"),
    ("Twilio (texts and calls)", r"from ['\"]twilio['\"]|require\(['\"]twilio['\"]\)|api\.twilio\.com|^\s*from twilio",
     "Twilio console: usage triggers (alerts) and rate limits on any form that sends a text"),
    ("Email sending (Resend, SendGrid, Postmark, Mailgun)", r"from ['\"](?:resend|@sendgrid/mail|postmark|mailgun\.js)['\"]|api\.resend\.com|api\.sendgrid\.com",
     "the provider's usage page: set alerts, and rate-limit sign-up and contact forms"),
    ("Google Maps", r"maps\.googleapis\.com|@googlemaps|@vis\.gl/react-google-maps", "Google Cloud: budget alerts, per-API quotas and a key restricted to your website"),
    ("Mapbox", r"mapbox-gl|api\.mapbox\.com", "mapbox.com account: check the free tier and billing alerts"),
]
AI_CALL_RE = re.compile(r"chat\.completions\.create\(|\bresponses\.create\(|messages\.create\(|generateContent(?:Stream)?\(|"
                        r"generate_content\(|embeddings\.create\(|images\.generate\(|replicate\.run\(|predictions\.create\(|"
                        r"(?:fetch|axios(?:\.post)?|requests\.post|httpx\.post)\(\s*[\"'`]https://(?:api\.openai\.com|api\.anthropic\.com|generativelanguage\.googleapis\.com)")
LIMIT_HINT_RE = re.compile(r"rate.?limit|ratelimit|limiter|quota|daily.?limit|usage.?limit|max_?requests|throttle|upstash", re.I)
AUTH_HINT_RE = re.compile(r"getUser\(|auth\.getUser|getSession|currentUser|requireAuth|verifyIdToken|auth\(\)|"
                          r"getServerSession|clerk|withAuth|req\.user|request\.auth|Authorization", re.I)
MAX_TOKENS_RE = re.compile(r"max_tokens|max_output_tokens|maxOutputTokens|maxTokens|max_completion_tokens")


MANUAL_CHECKS = [
    "Logins are checked on the server for every private page and action",
    "Each user can only see and change their own data (tested with two accounts)",
    "Database rules (RLS) are on for every table in the live dashboard, not just in files",
    "Users cannot change their own plan, credits or role",
    "Payments are only confirmed by a verified webhook",
    "Spending caps and alerts are set on every paid service",
    "Rate limits on AI calls, sign-up and messages",
    "AI features only reach data the current user may see, and AI answers are shown as text",
    "Environment variables are set on the host, and the site was redeployed",
    "Privacy notice, and terms if taking money",
    "Stranger test: private window, private pages, other users' data, page source",
]


def paid_caps(paid):
    caps = {n: c for n, _, c in PAID_SERVICES}
    return [(n, caps.get(n, "check its billing settings")) for n in sorted(paid)]


def write_report(scanner, findings, path, title="Seatbelt ship check", manual=None, extra=None):
    manual_checks = manual or MANUAL_CHECKS
    extra = extra or []
    intro = ("The scanner reads files only. It cannot see your live database settings or hosting dashboard."
             if manual is None else "These need a person to check.")
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
            rows.append(f"<section class='f {f['severity']}'><div class='top'><span class='tag'>{e(labels[f['severity']])}</span>"
                        f"<code>{e(loc)}</code><label class='done'><input type='checkbox'> fixed</label></div>"
                        f"<p class='what'>{e(f['what'])}</p>"
                        f"<p><b>Why it matters:</b> {e(f['why'])}</p><p class='fix'><b>Fix:</b> {e(f['fix'])}</p></section>")
        manual = "".join(f"<li><label><input type='checkbox'> {e(m)}</label></li>" for m in manual_checks)
        extra_html = ("<h2>Results</h2><ul class='plain'>" + "".join(f"<li>{e(x)}</li>" for x in extra) + "</ul>") if extra else ""
        paid = getattr(scanner, "paid_services", None)
        if paid:
            extra_html += "<h2>Paid services found</h2><p>Check each one has a spending cap or alerts:</p><ul class='plain'>" + "".join(
                f"<li><label><input type='checkbox'> <b>{e(n)}</b>: {e(c)}</label></li>" for n, c in paid_caps(paid)) + "</ul>"
        pills = "".join(f"<span class='pill {sv}'>{counts[sv]} {e(labels[sv].lower())}</span>" for sv in SEVERITY_ORDER)
        doc = f"""<!doctype html><html lang="en-GB"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>{e(title)}</title>
<style>
*{{box-sizing:border-box}}
body{{font-family:-apple-system,'Segoe UI',Helvetica,Arial,sans-serif;margin:0;background:#f4f6fb;color:#1b1f2a;line-height:1.55}}
header{{background:linear-gradient(120deg,#0b1026,#1a1554 55%,#0d3b4f);color:#fff;padding:2.2rem 1rem 3.6rem}}
.wrap{{max-width:820px;margin:0 auto;padding:0 1rem}}
header h1{{margin:0 0 .3rem;font-size:1.9rem;letter-spacing:-.5px}}
header p{{margin:0;color:#b8c4ec;font-size:.95rem}}
main{{margin-top:-2.4rem}}
.card{{background:#fff;border-radius:14px;box-shadow:0 6px 24px rgba(20,30,70,.08);padding:1.2rem 1.4rem;margin-bottom:1rem}}
.verdict{{font-weight:700;font-size:1.1rem;color:{'#b00020' if blocking else '#1b7f3b'}}}
.pills{{display:flex;flex-wrap:wrap;gap:.5rem;margin-top:.8rem}}
.pill{{border-radius:999px;padding:.2rem .75rem;font-size:.85rem;font-weight:600}}
.pill.critical,.critical .tag{{background:#fde2e4;color:#a1001c}}.pill.high,.high .tag{{background:#ffe8d6;color:#b34700}}
.pill.medium,.medium .tag{{background:#fff4c2;color:#7a5b00}}.pill.low,.low .tag{{background:#e3efff;color:#1450a3}}
.f{{background:#fff;border-radius:12px;padding:1rem 1.2rem;margin:.8rem 0;border-left:6px solid #ccc;box-shadow:0 2px 10px rgba(20,30,70,.05)}}
.f.critical{{border-color:#d0021b}}.f.high{{border-color:#f76707}}.f.medium{{border-color:#f2c200}}.f.low{{border-color:#3b82f6}}
.top{{display:flex;align-items:center;gap:.6rem;flex-wrap:wrap}}
.tag{{border-radius:6px;padding:.1rem .5rem;font-size:.78rem;font-weight:700;text-transform:uppercase;letter-spacing:.3px}}
code{{font-family:Menlo,Consolas,monospace;font-size:.85rem;color:#4a5068}}
.done{{margin-left:auto;font-size:.85rem;color:#6b7280}}
.what{{font-weight:600;margin:.6rem 0 .3rem}}.f p{{margin:.3rem 0}}.fix{{color:#14532d}}
h2{{font-size:1.15rem;margin:1.6rem 0 .6rem}}ul.plain,ul.manual{{padding:0}}li{{list-style:none;margin:.35rem 0}}
footer{{color:#6b7280;font-size:.85rem;padding:1rem 0 2.5rem}}
@media print{{header{{background:#1a1554;-webkit-print-color-adjust:exact;print-color-adjust:exact}}}}
</style></head><body>
<header><div class="wrap"><h1>{e(title)}</h1><p>{e(when)} &middot; {e(scanner.root)} &middot; {scanner.files_scanned} files checked</p></div></header>
<main class="wrap">
<div class="card"><div class="verdict">{e(verdict)}</div><div class="pills">{pills}</div></div>
{''.join(rows) or '<div class="card">No findings in the files.</div>'}
{f'<p><b>npm audit:</b> {e(scanner.npm_audit)}</p>' if scanner.npm_audit else ''}
{extra_html}
<h2>Still to check by hand</h2><p>{e(intro)}</p>
<ul class="manual">{manual}</ul>
<p>If any key was ever exposed, replace it in the provider's dashboard. Deleting it from the code is not enough.</p>
<footer>Made with Seatbelt (github.com/HYDERMAA/seatbelt). A quick check, not a full security audit.</footer>
</main></body></html>"""
    else:
        out = [f"# {title}", "", f"{when} | `{scanner.root}` | {scanner.files_scanned} files checked", "",
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
        if extra:
            out += [f"- {x}" for x in extra] + [""]
        paid = getattr(scanner, "paid_services", None)
        if paid:
            out += ["## Paid services found", "", "Check each one has a spending cap or alerts:", ""]
            out += [f"- [ ] **{n}**: {c}" for n, c in paid_caps(paid)] + [""]
        out += ["## Still to check by hand", "",
                intro, ""]
        out += [f"- [ ] {m}" for m in manual_checks]
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
            "ready": not blocking, "findings": findings, "paid_services": scanner.paid_services,
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
