#!/usr/bin/env python3
"""Mutation checks of the harness: each mutant breaks one rule on purpose, and the tests must FAIL.

A test suite that still passes with a rule broken doesn't guard that rule: the mutant « survived ».
Each mutant runs on a throwaway copy of bot.py; the working tree is never touched. A mutant whose
`old` text is no longer in bot.py is reported STALE (the code moved: update the list), not run.

Usage: python3 bot/mutants.py        (exit 1 if a mutant survived or went stale)
"""

import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))

# (the rule the mutant breaks, old, new): exact text of bot.py, replaced once
MUTANTS = [
    # the reviewer can't make things up
    (
        "an invented probe output is accepted",
        'unseen = [p for p in out["probes"] if _norm(p.get("got")) not in seen]',
        "unseen = []",
    ),
    (
        "a review with fewer than 3 real probes passes",
        'if code_changed and len([p for p in out["probes"] if p["verified"]]) < 3:',
        "if False:",
    ),
    (
        "colour codes make a real output look invented",
        'ANSI.sub("", str(s or ""))',
        'str(s or "")',
    ),
    # what the reviewer finds can't be talked away
    (
        "a wrong probe doesn't block",
        'if any(p.get("ok") is False and _case(p) not in noted for p in out["probes"]):',
        "if False:",
    ),
    (
        "an unhandled unhappy path doesn't block",
        'elif u.get("handled") is False:',
        "elif False:",
    ),
    (
        "a handled and tested case still becomes a note",
        "if open_ and why:",
        "if why:",
    ),
    (
        "a rebuttal needs no probe of this round on the disputed case",
        'p.get("ok") is False and p.get("verified") and _case(p) == _case(u)',
        'p.get("ok") is False',
    ),
    # CI failures named per test
    (
        "a failing test changes name when its line moves",
        'name = re.sub(r"\\s+", " ", VOLATILE.sub("", m.group(1))).strip(" ─-")',
        'name = re.sub(r"\\s+", " ", m.group(1)).strip(" ─-")',
    ),
    (
        "failures are named per job again (two different e2e failures look the same)",
        'return {f"{job}: {n}" for n in sorted(names)[:20]} if names else {job}',
        "return {job}",
    ),
    (
        "the old-code check is silent about what it didn't run",
        'line = f"Old-code check: not run ({wc.get(\'why\', \'?\')})."',
        'line = ""',
    ),
    (
        "a timed-out check leaves its processes running (a build's forked JVMs)",
        "            os.killpg(p.pid, 9)",
        "            p.kill()",
    ),
    # the PR's tests must prove something
    (
        "tests that pass on the old code are accepted",
        'if wc.get("checked") and not wc["fail_on_old_code"]:',
        "if False:",
    ),
    (
        "code changed without any test is accepted",
        'if rep["code_touched"] and not rep["tests_touched"]:',
        "if False:",
    ),
    # the bots can't touch their own judge
    (
        "protected paths (.github, .bot) can be changed",
        "return any(fnmatch.fnmatch(os.path.normpath(path), p) for p in PROTECTED)",
        "return False",
    ),
    # it stops itself
    (
        "the per-PR dollar cap is ignored",
        'f.get("usd", 0) >= PR_USD',
        "False",
    ),
    (
        "the same CI failure twice doesn't stop it",
        'if len(h) >= 2 and sorted(h[-1]) == sorted(h[-2]) == f["failing"]:',
        "if False:",
    ),
    (
        "the bot-review budget is never spent",
        "if f[\"review_rounds\"] >= REVIEW_ROUNDS:",
        "if False:",
    ),
    (
        "removing bot:stuck doesn't restore the budgets",
        "    ms = since_stuck(marks)\n",
        "    ms = marks\n",
    ),
    (
        "a human review doesn't start a new bot cycle",
        "cycle = since_handover(ms)",
        "cycle = ms",
    ),
    # humans first
    (
        "a human remark waits behind the bots",
        'if f["human"]:  # CI green: humans first',
        "if False:",
    ),
    (
        "the bots keep working on a PR handed over to humans",
        'if L_READY in f["labels"]:\n        return None',
        "if False:\n        return None",
    ),
]


def run(name: str, old: str, new: str, src: str) -> str:
    if src.count(old) != 1:
        return "STALE"
    with tempfile.TemporaryDirectory() as tmp:
        shutil.copytree(os.path.dirname(HERE), tmp, dirs_exist_ok=True, ignore=shutil.ignore_patterns(".git"))
        with open(os.path.join(tmp, "bot", "bot.py"), "w", encoding="utf-8") as f:
            f.write(src.replace(old, new))
        p = subprocess.run(
            [sys.executable, os.path.join(tmp, "bot", "test_bot.py")], capture_output=True, text=True, check=False
        )
        return "killed" if p.returncode else "SURVIVED"


def main() -> int:
    with open(os.path.join(HERE, "bot.py"), encoding="utf-8") as f:
        src = f.read()
    bad = 0
    for name, old, new in MUTANTS:
        verdict = run(name, old, new, src)
        bad += verdict != "killed"
        print(f"{verdict:9} {name}")
    print(f"\n{len(MUTANTS) - bad}/{len(MUTANTS)} mutants killed")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
