#!/usr/bin/env python3
"""Build helper for the Seatbelt repo.

1. Regenerates .cursor/rules/seatbelt.mdc from AGENTS.md (one source of truth).
2. Builds dist/seatbelt.zip (free: core skill and scanner, playbooks replaced by a short note)
   and dist/seatbelt-pro.zip (everything) for Claude.ai upload. Zip root is the seatbelt/ folder.

Run from anywhere: python3 tools/build.py
For a public free repo: python3 tools/build.py --strip-pro (replaces skills/seatbelt/playbooks
with the short free note; keep the full playbooks in a private repo).
"""

import os
import re
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL_DIR = os.path.join(ROOT, "skills", "seatbelt")

MDC_HEADER = (
    "---\n"
    'description: "Seatbelt: plain-English guard rails for non-developers who vibe code. Plan first, '
    'save points, secret keys kept safe, two-strikes bug fixing and a ship check."\n'
    "globs:\n"
    "alwaysApply: true\n"
    "---\n\n"
)
MDC_INTRO = (
    "These rules come from the Seatbelt skill (https://github.com/HYDERMAA/seatbelt). Keep this file\n"
    "at `.cursor/rules/seatbelt.mdc` in your project so Cursor applies it to every chat.\n"
)


def build_mdc():
    with open(os.path.join(ROOT, "AGENTS.md"), encoding="utf-8") as fh:
        text = fh.read()
    # swap the first paragraph after the title for a Cursor-specific one
    text = re.sub(r"(# Seatbelt rules for AI coding agents\n\n)(.*?\n)\n", lambda m: m.group(1) + MDC_INTRO + "\n", text, count=1, flags=re.S)
    out = os.path.join(ROOT, ".cursor", "rules", "seatbelt.mdc")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(MDC_HEADER + text)
    return out


FREE_PLAYBOOK_NOTE = """# Playbooks (not included in this copy)

This is the free edition of Seatbelt. Everything in SKILL.md, the references and the scanner
works without the playbooks. When a step mentions a playbook, use the matching reference file
instead (security-checklist.md, going-live.md, fixing-bugs.md) and check the provider's current
official documentation.

Seatbelt Pro adds tested, copy-paste playbooks for Supabase, Stripe, logins, Firebase, hosting,
costs and UK and EU privacy. See the Seatbelt README for details.
"""


def _add(z, arc, data, mode=0o644):
    info = zipfile.ZipInfo(arc, date_time=(2026, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = mode << 16
    z.writestr(info, data)


def build_zip(pro=False):
    dist = os.path.join(ROOT, "dist")
    os.makedirs(dist, exist_ok=True)
    out = os.path.join(dist, "seatbelt-pro.zip" if pro else "seatbelt.zip")
    if os.path.exists(out):
        os.remove(out)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for dirpath, dirnames, filenames in os.walk(SKILL_DIR):
            skip = {"__pycache__"} if pro or dirpath != SKILL_DIR else {"__pycache__", "playbooks"}
            dirnames[:] = sorted(d for d in dirnames if d not in skip)
            for name in sorted(filenames):
                if name.endswith(".pyc") or name == ".DS_Store":
                    continue
                full = os.path.join(dirpath, name)
                arc = os.path.join("seatbelt", os.path.relpath(full, SKILL_DIR)).replace(os.sep, "/")
                with open(full, "rb") as fh:
                    _add(z, arc, fh.read(), 0o755 if name.endswith(".py") else 0o644)
        if not pro:
            _add(z, "seatbelt/playbooks/README.md", FREE_PLAYBOOK_NOTE.encode("utf-8"))
    return out


def strip_pro():
    import shutil
    pb = os.path.join(SKILL_DIR, "playbooks")
    if os.path.isdir(pb):
        shutil.rmtree(pb)
    os.makedirs(pb)
    with open(os.path.join(pb, "README.md"), "w", encoding="utf-8") as fh:
        fh.write(FREE_PLAYBOOK_NOTE)
    print("replaced skills/seatbelt/playbooks with the free note")


if __name__ == "__main__":
    import sys
    if "--strip-pro" in sys.argv:
        strip_pro()
    print("wrote", os.path.relpath(build_mdc(), ROOT))
    print("wrote", os.path.relpath(build_zip(), ROOT))
    if os.path.isdir(os.path.join(SKILL_DIR, "playbooks")) and os.path.exists(
            os.path.join(SKILL_DIR, "playbooks", "supabase.md")):
        print("wrote", os.path.relpath(build_zip(pro=True), ROOT))
