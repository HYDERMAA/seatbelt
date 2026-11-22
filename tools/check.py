#!/usr/bin/env python3
"""Repository checks for Seatbelt. Run: python3 tools/check.py

Checks the skill against the Agent Skills spec (agentskills.io/specification) plus the stricter
Claude.ai upload limit (description up to 200 characters), and checks the repo for broken links,
em or en dashes, and drop-in files that have drifted out of sync.
"""

import importlib.util
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL_DIR = os.path.join(ROOT, "skills", "seatbelt")
ALLOWED_KEYS = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
TEXT_EXTS = {".md", ".mdc", ".py", ".json", ".yaml", ".yml", ".txt", ""}
errors = []


def err(msg):
    errors.append(msg)


def parse_frontmatter(text):
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        err("SKILL.md: no YAML frontmatter")
        return {}
    try:
        import yaml  # optional
        data = yaml.safe_load(m.group(1))
    except ImportError:
        data, current = {}, None
        for line in m.group(1).splitlines():
            if re.match(r"^\S[^:]*:", line):
                k, v = line.split(":", 1)
                current = k.strip()
                data[current] = v.strip().strip('"') if v.strip() else {}
            elif current and isinstance(data[current], dict) and ":" in line:
                k, v = line.strip().split(":", 1)
                data[current][k.strip()] = v.strip().strip('"')
    return data or {}


def check_skill():
    path = os.path.join(SKILL_DIR, "SKILL.md")
    text = open(path, encoding="utf-8").read()
    fm = parse_frontmatter(text)
    extra = set(fm) - ALLOWED_KEYS
    if extra:
        err(f"SKILL.md: unexpected frontmatter keys {sorted(extra)}")
    name = fm.get("name", "")
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", str(name)) or len(name) > 64:
        err(f"SKILL.md: invalid name {name!r}")
    if name != os.path.basename(SKILL_DIR):
        err("SKILL.md: name does not match folder name")
    desc = str(fm.get("description", "")).strip()
    if not desc:
        err("SKILL.md: empty description")
    if len(desc) > 1024:
        err(f"SKILL.md: description {len(desc)} chars (spec max 1024)")
    if len(desc) > 200:
        err(f"SKILL.md: description {len(desc)} chars (Claude.ai upload max 200)")
    if "<" in desc or ">" in desc:
        err("SKILL.md: description contains angle brackets")
    meta = fm.get("metadata", {})
    if not isinstance(meta, dict) or not all(isinstance(v, str) for v in meta.values()):
        err("SKILL.md: metadata must map strings to strings")
    lines = text.count("\n") + 1
    if lines > 500:
        err(f"SKILL.md: {lines} lines (keep under 500)")
    print(f"SKILL.md: name={name} description={len(desc)} chars, {lines} lines")


def check_links():
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in {".git", "dist", "__pycache__"}]
        for name in filenames:
            if not name.endswith((".md", ".mdc")):
                continue
            full = os.path.join(dirpath, name)
            text = open(full, encoding="utf-8").read()
            for target in re.findall(r"\]\(([^)\s]+)\)", text):
                if target.startswith(("http://", "https://", "#", "mailto:")):
                    continue
                if not os.path.exists(os.path.normpath(os.path.join(dirpath, target.split("#")[0]))):
                    err(f"{os.path.relpath(full, ROOT)}: broken link {target}")


def check_dashes():
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in {".git", "dist", "__pycache__"}]
        for name in filenames:
            if os.path.splitext(name)[1] not in TEXT_EXTS:
                continue
            full = os.path.join(dirpath, name)
            try:
                text = open(full, encoding="utf-8").read()
            except UnicodeDecodeError:
                continue
            for n, line in enumerate(text.splitlines(), 1):
                if "\u2014" in line or "\u2013" in line:
                    err(f"{os.path.relpath(full, ROOT)}:{n}: em or en dash")


def check_sync():
    def block(path, after=None):
        text = open(path, encoding="utf-8").read()
        if after:
            text = text.split(after, 1)[1]
        return re.search(r"```\n(.*?)```", text, re.S).group(1)

    a = block(os.path.join(ROOT, "paste-into-app-builders.md"))
    b = block(os.path.join(SKILL_DIR, "references", "no-code-platforms.md"), "## 9.")
    if a != b:
        err("paste-into-app-builders.md and no-code-platforms.md section 9 differ")
    spec = importlib.util.spec_from_file_location("build", os.path.join(ROOT, "tools", "build.py"))
    build = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(build)
    agents = open(os.path.join(ROOT, "AGENTS.md"), encoding="utf-8").read()
    expected = build.MDC_HEADER + re.sub(
        r"(# Seatbelt rules for AI coding agents\n\n)(.*?\n)\n",
        lambda m: m.group(1) + build.MDC_INTRO + "\n", agents, count=1, flags=re.S)
    actual = open(os.path.join(ROOT, ".cursor", "rules", "seatbelt.mdc"), encoding="utf-8").read()
    if expected != actual:
        err(".cursor/rules/seatbelt.mdc is out of date: run python3 tools/build.py")


def check_manifests():
    plugin = json.load(open(os.path.join(ROOT, ".claude-plugin", "plugin.json")))
    market = json.load(open(os.path.join(ROOT, ".claude-plugin", "marketplace.json")))
    if plugin["name"] != market["plugins"][0]["name"]:
        err("plugin.json name differs from marketplace entry name")


if __name__ == "__main__":
    check_skill()
    check_links()
    check_dashes()
    check_sync()
    check_manifests()
    if errors:
        print("FAILED")
        for e in errors:
            print(" -", e)
        sys.exit(1)
    print("All checks passed.")
