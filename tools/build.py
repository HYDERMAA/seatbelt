#!/usr/bin/env python3
"""Build helper for the Seatbelt repo.

1. Regenerates .cursor/rules/seatbelt.mdc from AGENTS.md (one source of truth).
2. Builds dist/seatbelt.zip for Claude.ai upload (zip root is the seatbelt/ folder).

Run from anywhere: python3 tools/build.py
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


def build_zip():
    dist = os.path.join(ROOT, "dist")
    os.makedirs(dist, exist_ok=True)
    out = os.path.join(dist, "seatbelt.zip")
    if os.path.exists(out):
        os.remove(out)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for dirpath, dirnames, filenames in os.walk(SKILL_DIR):
            dirnames[:] = sorted(d for d in dirnames if d not in {"__pycache__"})
            for name in sorted(filenames):
                if name.endswith(".pyc") or name == ".DS_Store":
                    continue
                full = os.path.join(dirpath, name)
                arc = os.path.join("seatbelt", os.path.relpath(full, SKILL_DIR)).replace(os.sep, "/")
                info = zipfile.ZipInfo(arc, date_time=(2026, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = (0o755 if name.endswith(".py") else 0o644) << 16
                with open(full, "rb") as fh:
                    z.writestr(info, fh.read())
    return out


if __name__ == "__main__":
    print("wrote", os.path.relpath(build_mdc(), ROOT))
    print("wrote", os.path.relpath(build_zip(), ROOT))
