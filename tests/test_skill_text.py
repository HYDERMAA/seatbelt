"""Guards against losing a rubric behaviour when SKILL.md or the drop-ins are edited."""
import os
import re
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL = os.path.join(ROOT, "skills", "seatbelt")


def read(*parts):
    with open(os.path.join(*parts), encoding="utf-8") as fh:
        return fh.read().lower()


# rubric id -> phrases that must appear (lower case)
SKILL_MUST = {
    "R1 asks before building": ["starter questions", "one-screen plan", "wait for"],
    "R2 plain english": ["plain", "glossary"],
    "R3 save points": ["save point", "git"],
    "R4 secrets": ["service_role", "next_public_", "replace"],
    "R5 rls and data": ["row level security", "webhook", "paid features"],
    "R6 stops fix loops": ["two strikes", "different approach"],
    "R7 explains errors": ["real error", "console"],
    "R8 ship check": ["ship check", "check_secrets.py", "stranger test"],
    "R9 costs": ["spending", "rate-limit", "alerts"],
    "R10 calls a human": ["real developer", "handoff"],
    "AI features": ["ai-features.md", "trick an ai", "waits for the person to confirm"],
    "v3 routing": ["question, fix or new build", "never just refuse", "no questions"],
    "v3 tools": ["check_live.py", "explain_changes.py", "paid service"],
    "v3 supabase grants": ["grant", "permission denied for table", "never turn rls off"],
}
AGENTS_MUST = ["project.md", "two strikes", "row level security", "webhook", "ship check",
               "only change what was asked", "honest"]


class SkillText(unittest.TestCase):
    def test_skill_house_style(self):
        text = read(SKILL, "SKILL.md")
        self.assertNotIn("\u2014", text, "no em dashes")
        self.assertNotIn("pro, if included", text)
        self.assertNotIn("within minutes", text)
        self.assertLess(text.count("\n"), 500)
        desc = re.search(r"^description: (.*)$", text, re.M).group(1)
        self.assertLessEqual(len(desc), 200)

    def test_skill_covers_rubric(self):
        text = read(SKILL, "SKILL.md")
        for rid, phrases in SKILL_MUST.items():
            for p in phrases:
                self.assertTrue(p in text, f"{rid}: missing '{p}'")

    def test_agents_md_covers_core(self):
        for name in ("AGENTS.md", os.path.join(".cursor", "rules", "seatbelt.mdc")):
            text = read(ROOT, name)
            for p in AGENTS_MUST:
                self.assertTrue(p in text, f"{name}: missing '{p}'")

    def test_paste_text_short(self):
        text = read(ROOT, "paste-into-app-builders.md")
        block = re.search(r"```\n(.*?)```", text, re.S).group(1)
        self.assertLess(len(block), 3000)
        self.assertIn("row level security", block)

    def test_zip_links_resolve(self):
        subprocess.run([sys.executable, os.path.join(ROOT, "tools", "build.py")], check=True,
                       capture_output=True)
        self.assertFalse(os.path.exists(os.path.join(ROOT, "dist", "seatbelt-pro.zip")))
        for zname in ("seatbelt.zip",):
            path = os.path.join(ROOT, "dist", zname)
            with tempfile.TemporaryDirectory() as tmp:
                with zipfile.ZipFile(path) as z:
                    z.extractall(tmp)
                base = os.path.join(tmp, "seatbelt")
                for dirpath, _, files in os.walk(base):
                    for f in files:
                        if not f.endswith(".md"):
                            continue
                        with open(os.path.join(dirpath, f), encoding="utf-8") as fh:
                            body = fh.read()
                        for target in re.findall(r"\]\(([^)\s]+)\)", body):
                            if target.startswith(("http", "#", "mailto:")):
                                continue
                            full = os.path.normpath(os.path.join(dirpath, target.split("#")[0]))
                            self.assertTrue(os.path.exists(full), f"{zname}:{f} -> {target}")
                for must in ("playbooks/supabase.md", "scripts/check_secrets.py", "scripts/check_live.py",
                             "scripts/explain_changes.py"):
                    self.assertTrue(os.path.exists(os.path.join(base, must)), must)


if __name__ == "__main__":
    unittest.main()
