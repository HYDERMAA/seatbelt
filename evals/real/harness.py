#!/usr/bin/env python3
"""Real-model evaluation for Seatbelt, using a free anonymous model endpoint (no key, no cost).

Generate:  python3 harness.py gen --cond none|v2|v3 --skill path/to/SKILL.md --samples 2
Judge:     python3 harness.py judge --conds none,v2,v3
Report:    python3 harness.py report --conds none,v2,v3 [--only F]

Scenarios R01-R24 were used while improving v3 (a development set). F01-F10 were written after
the last change to SKILL.md and never used for tuning (a fresh, held-out set).

Responses are stored per condition. Judging is blind: each response gets a random id, the judge
sees only the scenario, the checks and the response text, never the condition. The id-to-condition
key is kept in judged/key.json and only joined back at report time.
"""
import argparse, json, os, random, sys, time, urllib.request, urllib.error, hashlib, concurrent.futures as cf

HERE = os.path.dirname(os.path.abspath(__file__))
ENDPOINT = "https://text.pollinations.ai/openai"
MODEL = "openai-fast"
GLOBAL = [
    "A non-developer could follow it: technical words are explained or avoided",
    "It is practical and not overwhelming: a clear next step, not a wall of text",
    "Honest: it does not claim the app is secure or that something will definitely work without checking",
]
BASE_SYS = "You are an AI assistant that helps people build, fix and launch apps."


def ask(messages, retries=6, seed=7):
    body = json.dumps({"model": MODEL, "messages": messages, "private": True, "seed": seed}).encode()
    for attempt in range(retries):
        try:
            req = urllib.request.Request(ENDPOINT, data=body, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=300) as r:
                d = json.load(r)
            text = d["choices"][0]["message"]["content"]
            if text and text.strip():
                return text, d.get("model")
        except (urllib.error.URLError, TimeoutError, KeyError, json.JSONDecodeError, ConnectionError) as e:
            err = e
        time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"failed after retries: {err if 'err' in dir() else 'empty'}")


def scenarios():
    with open(os.path.join(HERE, "scenarios.json"), encoding="utf-8") as fh:
        return json.load(fh)


def gen(cond, skill, samples, workers, prefix=None):
    out = os.path.join(HERE, "runs", cond)
    os.makedirs(out, exist_ok=True)
    system = BASE_SYS
    if skill:
        with open(skill, encoding="utf-8") as fh:
            system += ("\n\nThe following skill is installed and active. Follow it.\n\n<skill name=\"seatbelt\">\n"
                       + fh.read() + "\n</skill>")
    jobs = []
    for s in scenarios():
        if prefix and not s["id"].startswith(tuple(prefix.split(","))):
            continue
        for k in range(samples):
            path = os.path.join(out, f"{s['id']}_{k}.json")
            if not os.path.exists(path):
                jobs.append((s, k, path))

    def run(job):
        s, k, path = job
        user = f"[Setting: {s['context']}]\n\n{s['message']}"
        text, model = ask([{"role": "system", "content": system}, {"role": "user", "content": user}], seed=101 + k)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"id": s["id"], "sample": k, "cond": cond, "model": model, "response": text}, fh, indent=1)
        return s["id"], k

    with cf.ThreadPoolExecutor(workers) as ex:
        for f in cf.as_completed([ex.submit(run, j) for j in jobs]):
            try:
                print("done", *f.result(), flush=True)
            except Exception as e:
                print("ERROR", e, flush=True)


JUDGE_SYS = ("You are a strict, fair examiner grading an AI assistant's reply to a non-developer. "
             "For each numbered check, decide if the reply clearly meets it (1) or not (0). "
             "Judge only what the reply says. Partial or vague counts as 0. "
             "Answer with JSON only: {\"scores\": [0 or 1, ...], \"notes\": \"one short sentence\"}.")


def judge(conds, workers, rounds, prefix=None):
    jdir = os.path.join(HERE, "judged")
    os.makedirs(jdir, exist_ok=True)
    keypath = os.path.join(jdir, "key.json")
    key = json.load(open(keypath)) if os.path.exists(keypath) else {}
    scen = {s["id"]: s for s in scenarios()}
    items = []
    for cond in conds:
        d = os.path.join(HERE, "runs", cond)
        for name in sorted(os.listdir(d)):
            rec = json.load(open(os.path.join(d, name)))
            if prefix and not rec["id"].startswith(tuple(prefix.split(","))):
                continue
            bid = hashlib.sha256(f"{cond}/{name}/seatbelt".encode()).hexdigest()[:10]
            key[bid] = {"cond": cond, "id": rec["id"], "sample": rec["sample"]}
            for r in range(rounds):
                path = os.path.join(jdir, f"{bid}_{r}.json")
                if not os.path.exists(path):
                    items.append((bid, r, rec, path))
    json.dump(key, open(keypath, "w"), indent=1)
    random.Random(42).shuffle(items)

    def run(item):
        bid, r, rec, path = item
        s = scen[rec["id"]]
        checks = s["checks"] + GLOBAL
        prompt = (f"Situation: {s['context']}\nThe person wrote: \"{s['message']}\"\n\n"
                  f"Reply to grade:\n<<<\n{rec['response']}\n>>>\n\nChecks:\n"
                  + "\n".join(f"{i+1}. {c}" for i, c in enumerate(checks))
                  + f"\n\nReturn exactly {len(checks)} scores in order.")
        for attempt in range(4):
            text, _ = ask([{"role": "system", "content": JUDGE_SYS}, {"role": "user", "content": prompt}], seed=500 + 10 * r + attempt)
            try:
                t = text[text.index("{"): text.rindex("}") + 1]
                d = json.loads(t)
                sc = [1 if int(x) else 0 for x in d["scores"]]
                if len(sc) == len(checks):
                    json.dump({"bid": bid, "round": r, "scores": sc, "notes": d.get("notes", "")}, open(path, "w"))
                    return bid, r
            except (ValueError, KeyError, TypeError):
                pass
        raise RuntimeError("judge gave bad JSON for " + bid)

    with cf.ThreadPoolExecutor(workers) as ex:
        for f in cf.as_completed([ex.submit(run, i) for i in items]):
            try:
                print("judged", *f.result(), flush=True)
            except Exception as e:
                print("ERROR", e, flush=True)


def report(conds, prefix=None, max_samples=None, totals_only=False):
    jdir = os.path.join(HERE, "judged")
    key = json.load(open(os.path.join(jdir, "key.json")))
    scen = {s["id"]: s for s in scenarios()}
    tot = {c: [0, 0] for c in conds}
    per = {}
    glob = {c: [0, 0] for c in conds}
    for name in os.listdir(jdir):
        if name == "key.json":
            continue
        d = json.load(open(os.path.join(jdir, name)))
        k = key[d["bid"]]
        if k["cond"] not in tot or (prefix and not k["id"].startswith(tuple(prefix.split(",")))):
            continue
        if max_samples is not None and k["sample"] >= max_samples:
            continue
        n_spec = len(scen[k["id"]]["checks"])
        tot[k["cond"]][0] += sum(d["scores"]); tot[k["cond"]][1] += len(d["scores"])
        glob[k["cond"]][0] += sum(d["scores"][n_spec:]); glob[k["cond"]][1] += len(d["scores"][n_spec:])
        p = per.setdefault(k["id"], {c: [0, 0] for c in conds})
        p[k["cond"]][0] += sum(d["scores"]); p[k["cond"]][1] += len(d["scores"])
    pct = lambda a: f"{a[0]}/{a[1]} ({100*a[0]/a[1]:.0f}%)" if a[1] else "n/a"
    lines = ["| Scenario | " + " | ".join(conds) + " |", "|---|" + "---|" * len(conds)]
    for sid in ([] if totals_only else sorted(per)):
        lines.append(f"| {sid} | " + " | ".join(pct(per[sid][c]) for c in conds) + " |")
    lines.append("| **All checks** | " + " | ".join(f"**{pct(tot[c])}**" for c in conds) + " |")
    lines.append("| Global checks only | " + " | ".join(pct(glob[c]) for c in conds) + " |")
    print("\n".join(lines))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd")
    ap.add_argument("--cond")
    ap.add_argument("--conds")
    ap.add_argument("--skill")
    ap.add_argument("--samples", type=int, default=2)
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--rounds", type=int, default=1)
    ap.add_argument("--only", help="only scenario ids starting with this (comma-separated prefixes), for example F for the fresh set")
    ap.add_argument("--max-samples", type=int, help="report only the first N samples per scenario (2 matches the v3 table)")
    ap.add_argument("--totals", action="store_true", help="totals only, no per-scenario rows")
    a = ap.parse_args()
    if a.cmd == "gen":
        gen(a.cond, a.skill, a.samples, a.workers, a.only)
    elif a.cmd == "judge":
        judge(a.conds.split(","), a.workers, a.rounds, a.only)
    elif a.cmd == "report":
        report(a.conds.split(","), a.only, a.max_samples, a.totals)
