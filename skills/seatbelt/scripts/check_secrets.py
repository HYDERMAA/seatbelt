#!/usr/bin/env python3
"""Seatbelt ship check: a no-install scanner for leaked keys and risky settings.

Usage:
    python3 check_secrets.py [project_folder] [--json]

Reads files only and never changes anything. Needs only Python 3.8 or newer.
Exit code 0: no critical or high findings. 1: something should be fixed first. 2: usage error.

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

# (id, label, regex). Patterns are deliberately specific to keep false alarms low.
SECRET_PATTERNS = [
    ("anthropic-key", "Anthropic API key", r"sk-ant-[A-Za-z0-9_\-]{20,}"),
    ("openai-key", "OpenAI API key", r"sk-(?:proj-|svcacct-|admin-)?[A-Za-z0-9_\-]{32,}"),
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
SERVER_FILE_HINTS = re.compile(r"(\.server\.|route\.(?:js|ts)$|middleware\.(?:js|ts)$|^server\.)")


def is_env_file(name):
    return name == ".env" or (name.startswith(".env.") and name != ".env.example") or name.endswith(".env")


def is_example_env(name):
    return name in {".env.example", ".env.sample", ".env.template", ".env.dist"}


def looks_frontend(rel):
    parts = rel.replace("\\", "/").split("/")
    name = parts[-1]
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
        self.sql_created = []
        self.sql_enabled = set()

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
        frontend = looks_frontend(rel)
        lines = text.splitlines()
        for n, line in enumerate(lines, 1):
            if "seatbelt-ignore" in line:
                continue
            self.scan_secrets(rel, n, line, env_file, example, frontend)
            self.scan_public_prefix(rel, n, line, env_file, frontend)
            if frontend and re.search(r"service_role|SERVICE_ROLE", line):
                self.add("critical", "service-role-in-frontend", rel, n,
                         "The Supabase service_role (master) key is referenced in browser code.",
                         "That key ignores all database safety rules. Anyone could read or delete every row.",
                         "Use only the anon or publishable key in the browser. Move admin work into a server or edge function.")
            if frontend and "dangerouslyAllowBrowser" in line and re.search(r"dangerouslyAllowBrowser\s*:\s*true", line):
                self.add("high", "ai-client-in-browser", rel, n,
                         "An AI library is set to run in the browser (dangerouslyAllowBrowser: true).",
                         "That only works by sending your AI key to every visitor, who can then use it on your bill.",
                         "Call the AI from a server or edge function instead, and keep the key there.")
        lower = name.lower()
        if lower.endswith(".sql"):
            self.scan_sql(rel, text)
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

    def scan_sql(self, rel, text):
        clean = re.sub(r"--[^\n]*", "", text)
        for m in re.finditer(r"create\s+table\s+(?:if\s+not\s+exists\s+)?([\w\".]+)", clean, re.I):
            self.sql_created.append((m.group(1).replace('"', ""), rel, clean[: m.start()].count("\n") + 1))
        for m in re.finditer(r"alter\s+table\s+(?:if\s+exists\s+)?(?:only\s+)?([\w\".]+)\s+enable\s+row\s+level\s+security", clean, re.I):
            self.sql_enabled.add(m.group(1).replace('"', "").split(".")[-1].lower())
        for m in re.finditer(r"alter\s+table\s+([\w\".]+)\s+disable\s+row\s+level\s+security", clean, re.I):
            self.add("high", "rls-disabled", rel, clean[: m.start()].count("\n") + 1,
                     f"Row Level Security is switched off for '{m.group(1)}'.",
                     "That opens the whole table to anyone with the public key.",
                     "Turn it back on and write a policy for what is needed, instead of disabling it.")
        for m in re.finditer(r"using\s*\(\s*true\s*\)", clean, re.I):
            self.add("medium", "policy-allows-everyone", rel, clean[: m.start()].count("\n") + 1,
                     "A database policy says 'using (true)', which means everyone.",
                     "Fine for truly public data like a list of products, dangerous for anything personal.",
                     "If this table holds personal data, change it to something like using (auth.uid() = user_id).")

    def scan_firebase(self, rel, lines):
        for n, line in enumerate(lines, 1):
            if "seatbelt-ignore" in line:
                continue
            if re.search(r"if\s+true\s*;", line) or re.search(r"\"\.(?:read|write)\"\s*:\s*(?:true|\"true\")", line):
                self.add("high", "firebase-open-rules", rel, n,
                         "A Firebase security rule lets anyone read or write.",
                         "Anyone on the internet could read, change or delete this data.",
                         "Require sign-in and ownership, for example: allow read, write: if request.auth != null && request.auth.uid == userId;")

    def check_rls(self):
        for table, rel, line in self.sql_created:
            short = table.split(".")[-1].lower()
            if table.lower().startswith(("auth.", "storage.", "private.")):
                continue
            if short not in self.sql_enabled:
                self.add("high", "table-without-rls", rel, line,
                         f"Table '{table}' is created without Row Level Security being switched on in any .sql file here.",
                         "On Supabase, a table without RLS can be read and changed by anyone holding the public key, which is in your website.",
                         f"Add: alter table {table} enable row level security; then add policies so people only see their own rows. If you turned RLS on in the dashboard instead, check it there.")

    def check_project(self):
        self.check_rls()
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
        seen = set()
        out = []
        for f in sorted(self.findings, key=lambda f: (SEVERITY_ORDER.index(f["severity"]), f["file"], f["line"] or 0)):
            key = (f["check"], f["file"], f["line"])
            if key in seen:
                continue
            seen.add(key)
            out.append(f)
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


def main(argv):
    args = [a for a in argv if not a.startswith("--")]
    flags = {a for a in argv if a.startswith("--")}
    if "--help" in flags or "-h" in argv:
        print(__doc__)
        return 0
    unknown = flags - {"--json", "--help"}
    if unknown or len(args) > 1:
        print("Usage: python3 check_secrets.py [project_folder] [--json]", file=sys.stderr)
        return 2
    root = args[0] if args else "."
    if not os.path.isdir(root):
        print(f"Folder not found: {root}", file=sys.stderr)
        return 2
    scanner = Scanner(root)
    scanner.walk()
    findings = scanner.sorted_findings()
    blocking = any(f["severity"] in {"critical", "high"} for f in findings)
    if "--json" in flags:
        print(json.dumps({
            "root": scanner.root, "files_scanned": scanner.files_scanned, "git": scanner.git,
            "ready": not blocking, "findings": findings,
        }, indent=2))
    else:
        print_report(scanner, findings)
    return 1 if blocking else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
