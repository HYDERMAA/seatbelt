#!/usr/bin/env python3
"""Seatbelt change explainer: before a save point, explains in plain English what changed since
the last save point and whether any of it is risky. Python 3 and git only, nothing to install.
It only reads; it never changes files or git history.

Usage:
  python3 explain_changes.py [project_folder]
  python3 explain_changes.py . --check-packages     also checks new packages really exist (needs internet)
  python3 explain_changes.py . --since main          compare with a branch or older save point
  python3 explain_changes.py . --json

Exit code: 0 low or medium risk, 1 high risk, 2 could not run.
"""

import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check_secrets as cs  # noqa: E402

NPM_REGISTRY = os.environ.get("SEATBELT_NPM_REGISTRY", "https://registry.npmjs.org")
NPM_DOWNLOADS = os.environ.get("SEATBELT_NPM_DOWNLOADS", "https://api.npmjs.org/downloads/point/last-week")
PYPI = os.environ.get("SEATBELT_PYPI", "https://pypi.org/pypi")

AREAS = [
    ("database", re.compile(r"(\.sql$|migrations?/|supabase/|prisma/|schema\.prisma|firestore\.rules|database\.rules|drizzle)", re.I)),
    ("payments", re.compile(r"(stripe|payment|checkout|billing|webhook|subscription|paddle|lemon)", re.I)),
    ("logins", re.compile(r"(auth|login|signin|sign-in|signup|session|middleware\.)", re.I)),
    ("secrets and settings", re.compile(r"(^|/)\.env|config\.|\.toml$|vercel\.json|netlify|next\.config|vite\.config", re.I)),
    ("packages", re.compile(r"(^|/)(package\.json|requirements\.txt|pyproject\.toml)$", re.I)),
    ("server code", re.compile(r"(^|/)(api|server|functions|backend|routes?|actions?)/|route\.(js|ts)$|\.server\.", re.I)),
    ("tests", re.compile(r"(^|/)(tests?|__tests__|e2e)/|\.(test|spec)\.", re.I)),
    ("pages and design", re.compile(r"\.(tsx|jsx|vue|svelte|astro|html|css|scss)$", re.I)),
    ("app code", re.compile(r"\.(js|ts|mjs|cjs|py|rb|go|php|dart|kt|swift)$", re.I)),
    ("documents", re.compile(r"\.(md|txt)$", re.I)),
]
PAID_APIS = {
    "OpenAI": r"openai|api\.openai\.com", "Anthropic": r"anthropic|api\.anthropic\.com",
    "Google Gemini": r"generativelanguage|@google/genai|gemini", "Twilio (texts)": r"twilio",
    "Replicate": r"replicate\.com|from ['\"]replicate", "Resend or email sending": r"resend|sendgrid|postmark|mailgun",
    "Google Maps": r"maps\.googleapis|@googlemaps", "ElevenLabs": r"elevenlabs",
}
RISKY_ADDED = [
    (r"disable\s+row\s+level\s+security", "high", "turns OFF database rules (RLS) on a table, so the table may be open to anyone"),
    (r"using\s*\(\s*true\s*\)|with\s+check\s*\(\s*true\s*\)", "high", "adds a database rule that lets everyone through"),
    (r"grant\s+all[^;]*\bto\s+(?:anon|public)\b", "high", "gives logged-out visitors full access to a table"),
    (r"\bdrop\s+table\b|\btruncate\b", "high", "deletes a whole table or all its rows"),
    (r"\bdelete\s+from\s+[\w.\"]+\s*;", "high", "deletes every row in a table (no WHERE)"),
    (r"\.delete\(\)\s*\.(?:neq|not|gt|gte|lt|lte)\(", "high", "deletes rows with a 'not equal' style filter, which usually wipes almost the whole table"),
    (r"\.delete\(\)(?![^\n]*\.(?:eq|match|in|neq|not|gt|gte|lt|lte)\()", "medium", "deletes database rows: check the filter only removes what it should"),
    (r"dangerouslyAllowBrowser\s*:\s*true", "high", "lets an AI key be used from the browser, where anyone can copy it"),
    (r"allow\s+read\s*,\s*write\s*:\s*if\s+true", "high", "opens the Firebase database to everyone"),
    (r"cors\(\s*\)|origin\s*:\s*['\"]\*['\"]", "medium", "lets any website call this server"),
    (r"\b(alter|create)\s+table\b", "medium", "changes the database structure (back up the data first)"),
    (r"\bsetInterval\s*\(|cron|schedule", "medium", "adds something that runs on a timer (check it cannot run up costs)"),
]
RISKY_REMOVED = [
    (r"constructEvent|construct_event|verifyHeader", "high", "removes the Stripe signature check, so fake payment messages could be accepted"),
    (r"enable\s+row\s+level\s+security", "high", "removes a line that switches database rules on"),
    (r"auth\.uid\(\)|getUser\(|requireAuth|getSession\(|currentUser|isAuthenticated", "medium", "removes a login or ownership check"),
    (r"rateLimit|rate_limit|ratelimit", "medium", "removes a rate limit"),
]


def git(root, *args):
    r = subprocess.run(["git", "-C", root, *args], capture_output=True, text=True, timeout=60)
    return r.returncode, r.stdout


def http_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Seatbelt-change-explainer/3", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, json.loads(r.read().decode("utf-8", "ignore"))
    except urllib.error.HTTPError as e:
        return e.code, None
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        return None, None


def check_npm(name):
    st, data = http_json(f"{NPM_REGISTRY}/{urllib.parse.quote(name, safe='@')}")
    if st == 404:
        return "high", f"the package '{name}' does not exist on npm. AI tools sometimes invent package names, and attackers register them. Do not install it; ask for a well-known alternative."
    if st != 200 or not data:
        return None, f"could not check '{name}' (no internet?). Check it on npmjs.com before installing."
    created = (data.get("time") or {}).get("created", "")
    st2, dl = http_json(f"{NPM_DOWNLOADS}/{urllib.parse.quote(name, safe='@')}")
    downloads = (dl or {}).get("downloads")
    notes = []
    if downloads is not None and downloads < 1000:
        notes.append(f"only {downloads} downloads last week")
    if created:
        import datetime
        try:
            age = (datetime.datetime.now(datetime.timezone.utc)
                   - datetime.datetime.fromisoformat(created.replace("Z", "+00:00"))).days
            if age < 60:
                notes.append(f"first published {age} days ago")
        except ValueError:
            pass
    if notes:
        return "medium", f"'{name}' exists but is little used or very new ({', '.join(notes)}). Make sure it is the package you meant, spelt exactly."
    return "ok", f"'{name}' exists and is widely used"


def check_pypi(name):
    st, _ = http_json(f"{PYPI}/{urllib.parse.quote(name)}/json")
    if st == 404:
        return "high", f"the Python package '{name}' does not exist on PyPI. Do not install it; it may be an invented name."
    if st != 200:
        return None, f"could not check '{name}'. Check it on pypi.org before installing."
    return "ok", f"'{name}' exists on PyPI"


class Explainer:
    def __init__(self, root, since="HEAD", check_packages=False):
        self.root, self.since, self.check_packages = os.path.abspath(root), since, check_packages
        self.files = {}        # path -> {"status", "added", "removed"}
        self.added, self.removed = {}, {}
        self.warnings = []     # (severity, text)
        self.facts = []
        self.packages = []

    def warn(self, severity, text):
        if (severity, text) not in self.warnings:
            self.warnings.append((severity, text))

    def collect(self):
        code, _ = git(self.root, "rev-parse", "--is-inside-work-tree")
        if code:
            raise RuntimeError("This folder is not using git save points yet, so there is nothing to compare. Make the first save point, then run this before the next one.")
        code, _ = git(self.root, "rev-parse", "--verify", self.since)
        base = self.since if code == 0 else None
        if base:
            _, numstat = git(self.root, "diff", "--numstat", base)
            _, names = git(self.root, "diff", "--name-status", base)
            _, patch = git(self.root, "diff", "-U0", base)
        else:  # no save point yet: everything is new
            numstat, names, patch = "", "", ""
        for line in names.splitlines():
            parts = line.split("\t")
            if len(parts) >= 2:
                self.files[parts[-1]] = {"status": parts[0][0], "added": 0, "removed": 0}
        for line in numstat.splitlines():
            parts = line.split("\t")
            if len(parts) == 3 and parts[2] in self.files:
                a, r = parts[0], parts[1]
                self.files[parts[2]]["added"] = int(a) if a.isdigit() else 0
                self.files[parts[2]]["removed"] = int(r) if r.isdigit() else 0
        current = None
        for line in patch.splitlines():
            if line.startswith("+++ "):
                current = line[6:] if line.startswith("+++ b/") else None
            elif current and line.startswith("+") and not line.startswith("+++"):
                self.added.setdefault(current, []).append(line[1:])
            elif line.startswith("--- "):
                current_removed = line[6:] if line.startswith("--- a/") else None
                self._cur_removed = current_removed
            elif line.startswith("-") and getattr(self, "_cur_removed", None):
                self.removed.setdefault(self._cur_removed, []).append(line[1:])
        _, untracked = git(self.root, "ls-files", "--others", "--exclude-standard")
        for path in untracked.splitlines():
            full = os.path.join(self.root, path)
            try:
                with open(full, encoding="utf-8", errors="ignore") as fh:
                    lines = fh.read(cs.MAX_BYTES).splitlines()
            except OSError:
                lines = []
            self.files[path] = {"status": "A", "added": len(lines), "removed": 0}
            self.added[path] = lines

    def area(self, path):
        for name, rx in AREAS:
            if rx.search(path):
                return name
        return "other files"

    def analyse(self):
        areas = {}
        for path, info in self.files.items():
            areas.setdefault(self.area(path), []).append(path)
        total_added = sum(f["added"] for f in self.files.values())
        total_removed = sum(f["removed"] for f in self.files.values())
        self.facts.append(f"{len(self.files)} file(s) changed: {total_added} line(s) added, {total_removed} removed.")
        for name, paths in sorted(areas.items(), key=lambda kv: -len(kv[1])):
            shown = ", ".join(sorted(paths)[:4]) + (f" and {len(paths) - 4} more" if len(paths) > 4 else "")
            self.facts.append(f"{name}: {shown}")
        self.areas = areas
        for path, info in self.files.items():
            name = os.path.basename(path)
            if info["status"] == "D":
                self.warn("high", f"{path} is deleted. Make sure that was intended.")
            elif info["removed"] >= 40 and info["removed"] > 2 * max(info["added"], 1):
                self.warn("medium", f"{path}: {info['removed']} lines removed and only {info['added']} added. Check no working feature was deleted.")
            if cs.is_env_file(name) and not cs.is_example_env(name):
                self.warn("high", f"{path} is a secrets file and is about to be saved. Add it to .gitignore first.")
        frontend = lambda p: cs.looks_frontend(p) or cs.in_public_build(p)
        for path, lines in self.added.items():
            joined = "\n".join(lines)
            for check_id, label, rx in cs.COMPILED:
                for m in rx.finditer(joined):
                    if not cs.PLACEHOLDER_RE.search(m.group(0)):
                        self.warn("high", f"{path}: a {label} was added ({cs.mask(m.group(0))}). Move it to .env or Secrets before saving.")
            if frontend(path) and re.search(r"service_role|sb_secret_|SERVICE_ROLE", joined):
                self.warn("high", f"{path}: Supabase secret or service role key used in code that runs in the browser.")
            if frontend(path) and cs.PUBLIC_PREFIX_RE.search(joined) and cs.RISKY_NAME_RE.search(joined):
                for line in lines:
                    m = cs.PUBLIC_PREFIX_RE.search(line)
                    if m and cs.RISKY_NAME_RE.search(line[m.start():m.start() + 80]):
                        self.warn("high", f"{path}: a secret-looking setting has a public prefix ({line.strip()[:70]}). Public prefixes are copied into the browser.")
                        break
            for rx, sev, text in RISKY_ADDED:
                if re.search(rx, joined, re.I):
                    self.warn(sev, f"{path}: {text}.")
            for api, rx in PAID_APIS.items():
                if re.search(rx, joined, re.I) and not cs.TEST_PATH_RE.search(path) and not path.endswith((".md", ".json", ".lock")):
                    self.warn("medium", f"{path}: uses {api}, which costs money per use. Make sure there is a per-user limit and a spending cap.")
        for path, lines in self.removed.items():
            joined = "\n".join(lines)
            for rx, sev, text in RISKY_REMOVED:
                if re.search(rx, joined, re.I) and not re.search(rx, "\n".join(self.added.get(path, [])), re.I):
                    self.warn(sev, f"{path}: {text}.")
        if "database" in self.areas:
            self.warn("medium", "Database files changed. Save points cover code, not the data: back up the data before running these changes on the live database.")
        if len(self.files) > 15 or sum(f["added"] + f["removed"] for f in self.files.values()) > 600:
            self.warn("medium", "This is a big change. Big changes are harder to undo and check; consider splitting it into smaller steps.")
        self.find_packages()

    def find_packages(self):
        for path, lines in self.added.items():
            base = os.path.basename(path)
            before = "\n".join(self.removed.get(path, []))
            if base == "package.json":
                for line in lines:
                    if line.strip().rstrip(",") and re.sub(r",\s*$", "", line.strip()) in before:
                        continue  # only reformatted (for example a comma added), not new
                    m = re.match(r'\s*"(@?[a-z0-9][\w.\-]*(?:/[\w.\-]+)?)"\s*:\s*"[\^~><=*\d.\w\-|: /]*"', line)
                    if m and m.group(1) not in {"name", "version", "private", "type", "main", "module", "scripts",
                                                 "description", "license", "author", "engines", "packageManager",
                                                 "dev", "build", "start", "lint", "test", "preview", "typecheck"}:
                        self.packages.append(("npm", m.group(1)))
            elif base == "requirements.txt":
                for line in lines:
                    m = re.match(r"\s*([A-Za-z0-9][A-Za-z0-9._\-]*)", line)
                    if m and not line.strip().startswith(("#", "-")) and line.strip() not in before:
                        self.packages.append(("pypi", m.group(1)))
        if self.packages:
            names = ", ".join(n for _, n in self.packages[:8])
            self.facts.append(f"new packages: {names}")
        if self.packages and self.check_packages:
            for eco, name in self.packages[:25]:
                sev, text = check_npm(name) if eco == "npm" else check_pypi(name)
                if sev in ("high", "medium"):
                    self.warn(sev, text)
                elif sev is None:
                    self.warn("low", text)
        elif self.packages:
            self.warn("low", "New packages were added. Run again with --check-packages to confirm they really exist and are widely used.")

    def risk(self):
        sevs = {s for s, _ in self.warnings}
        return "HIGH" if "high" in sevs else "MEDIUM" if "medium" in sevs else "LOW"

    def save_point_name(self):
        important = [a for a in ("payments", "database", "logins", "server code", "packages", "pages and design")
                     if a in getattr(self, "areas", {})]
        return (" and ".join(important[:3]) + " changes") if important else "small changes"

    def run(self):
        self.collect()
        if not self.files:
            return False
        self.analyse()
        return True


def main(argv):
    args = [a for a in argv if not a.startswith("--")]
    since = "HEAD"
    for i, a in enumerate(argv):
        if a == "--since" and i + 1 < len(argv):
            since = argv[i + 1]
            args = [x for x in args if x != since]
        elif a.startswith("--since="):
            since = a.split("=", 1)[1]
    if "--help" in argv:
        print(__doc__)
        return 0
    root = args[0] if args else "."
    ex = Explainer(root, since=since, check_packages="--check-packages" in argv)
    try:
        changed = ex.run()
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        return 2
    order = {"high": 0, "medium": 1, "low": 2}
    warnings = sorted(ex.warnings, key=lambda w: order[w[0]])
    if "--json" in argv:
        print(json.dumps({"changed": changed, "risk": ex.risk() if changed else "NONE", "facts": ex.facts,
                          "warnings": [{"severity": s, "text": t} for s, t in warnings],
                          "suggested_name": ex.save_point_name() if changed else None}, indent=2))
    elif not changed:
        print("Nothing has changed since the last save point.")
    else:
        print(f"What changed since the last save point (risk: {ex.risk()})")
        for f in ex.facts:
            print(f"- {f}")
        if warnings:
            print("\nWatch out:")
            label = {"high": "STOP AND CHECK", "medium": "CHECK", "low": "TIP"}
            for s, t in warnings:
                print(f"- [{label[s]}] {t}")
        else:
            print("\nNothing risky spotted in these changes.")
        print(f"\nSuggested save point name: \"{ex.save_point_name()}\"")
    return 1 if changed and ex.risk() == "HIGH" else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
