# Real-model evaluation

This folder holds a real-model test of the skill: real answers from a real language model, graded
blind. It is separate from the hand-graded rubric in `evals/rubric.md`.

## How it works

- **Model:** `gpt-oss-20b`, through the free anonymous Pollinations endpoint (no key, no cost).
  This is a small open model. It is not Claude or GPT-5, so absolute scores say little about how
  Seatbelt behaves in Claude.
- **Conditions:** `none` (a plain "you help people build apps" system prompt), `v2` (plus the
  v2.0.0 SKILL.md) and `v3` (plus the v3 SKILL.md). Only SKILL.md is given; the model cannot open
  the reference files, playbooks or scripts, and it answers in one turn with no tools.
- **Scenarios:** 34 messages from non-developers, each with 3 to 5 specific checks plus 3
  general checks (plain English, practical, honest). 2 answers per scenario per condition.
  - `R01` to `R24`: a **development set**. These were used while improving v3, so v3's score on
    them is optimistic.
  - `F01` to `F10`: a **fresh held-out set**, written after the last change to SKILL.md and never
    used for tuning. This is the fairer number.
- **Grading:** the same model acts as judge, twice per answer with different seeds. It sees the
  scenario, the checks and the answer, never which condition wrote it (ids are hashes; the key is
  in `judged/key.json`).

## Results (22 Nov 2026)

| Set | No skill | v2 | v3 |
| --- | --- | --- | --- |
| Fresh held-out (F01 to F10, 280 checks each) | 227 (81%) | 223 (80%) | **245 (88%)** |
| Development (R01 to R24, 676 checks each) | 451 (67%) | 482 (71%) | **511 (76%)** |
| General checks only, development set | 76% | 90% | 92% |

Per-scenario tables: `python3 harness.py report --conds none,v2,v3` (add `--only F` or `--only R`).

## What this does and does not show

- On the fresh set v3 beat no skill on 6 scenarios, lost on 3 and tied on 1. That is encouraging
  but not statistically strong with 10 scenarios and 2 answers each.
- The judge agreed with itself on 89% of individual checks across its two rounds. A hand check of
  6 random answers found the judge slightly lenient (it sometimes passed answers that put a key
  behind a public prefix). The leniency applies to every condition equally because grading is blind.
- The model sometimes refuses outright ("I'm sorry, but I can't help with that"), for example on
  scraping a competitor's prices, even with the skill's "never just refuse" rule. This varies
  between runs and looks like the model's own filter.
- v3 was tuned in three passes on the development set (first pass 72%, second 74%, final 76%).
- A real multi-turn test in Claude Code, where the agent can read the references and run the
  scripts, would be much more informative. It needs a signed-in Claude account.

## Re-running

```bash
python3 harness.py gen --cond v3 --skill ../../skills/seatbelt/SKILL.md --samples 2 --workers 4
python3 harness.py judge --conds none,v2,v3 --workers 4 --rounds 2
python3 harness.py report --conds none,v2,v3 --only F
```

The free endpoint changes over time, so new runs will not match these numbers exactly.
