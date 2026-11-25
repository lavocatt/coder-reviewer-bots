"""Offline checks of the bot's pure logic: python3 .bot/test_bot.py (exit 1 on failure)."""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
# installed: .bot/project.toml next to bot.py; in the bots' own repository: the pilot's example
if not os.path.exists(os.path.join(HERE, "project.toml")):
    os.environ.setdefault("BOT_PROJECT", os.path.join(HERE, "..", "examples", "markdown-runner", "project.toml"))
sys.path.insert(0, HERE)
import bot  # noqa: E402

FAILED = 0


def check(name, cond):
    global FAILED
    print(("ok   " if cond else "FAIL ") + name)
    FAILED += not cond


def pr(**kw):
    f = {
        "number": 5, "sha": "abc", "branch": "bot/issue-1", "issue": 1, "labels": set(), "ci": "success",
        "failing": [], "failed_runs": [], "alerts": [], "review": None, "human": [], "review_rounds": 0,
        "fix_rounds": 0, "human_rounds": 0, "fix_history": [],
    }
    f.update(kw)
    return f


k = lambda f: (bot.decide_pr(f) or {}).get("kind")  # noqa: E731
check("no CI yet -> dispatch", k(pr(ci="none")) == "dispatch_ci")
check("CI running -> wait", k(pr(ci="pending")) == "wait_ci")
check("CI red -> fix", k(pr(ci="failure", failing=["test"])) == "fix")
check("same failure after two fixes -> stuck",
      k(pr(ci="failure", failing=["test"], fix_history=[["test"], ["test"]], fix_rounds=2)) == "stuck")
check("fix budget -> stuck", k(pr(ci="failure", failing=["a"], fix_rounds=bot.FIX_ROUNDS)) == "stuck")
check("green, unreviewed -> review", k(pr()) == "review")
check("review budget -> stuck", k(pr(review_rounds=bot.REVIEW_ROUNDS)) == "stuck")
check("changes -> address", k(pr(review="changes")) == "address")
check("ready -> handover", k(pr(review="ready")) == "handover")
check("handed over -> nothing", k(pr(review="ready", labels={bot.L_READY})) is None)
check("human remark beats ready", k(pr(review="ready", labels={bot.L_READY}, human=[{"id": "c1"}])) == "address")
check("stuck -> nothing", k(pr(ci="failure", labels={bot.L_STUCK})) is None)

check("PR cost cap stops a review", k(pr(usd=bot.PR_USD)) == "stuck")
check("PR cost cap stops a fix", k(pr(ci="failure", failing=["a"], usd=bot.PR_USD + 1)) == "stuck")
check("PR cost cap doesn't block the handover", k(pr(review="ready", usd=bot.PR_USD + 1)) == "handover")
check("under the cap -> review", k(pr(usd=bot.PR_USD - 1)) == "review")
mk = lambda kind, usd=0: {"kind": kind, "stats": {"usd": usd}}  # noqa: E731
check("spend counted since the last stuck",
      bot.spent_since_stuck([mk("new", 30), mk("review", 25), mk("stuck"), mk("fix", 4)]) == 4)
b = bot.budgets([mk("review", 1), mk("review", 1), mk("review", 1), mk("stuck"), mk("review", 2)])
check("removing stuck restarts the review budget", b["review_rounds"] == 1 and b["usd"] == 2)
check("spend without stuck", bot.spent_since_stuck([mk("new", 30), mk("review", 25)]) == 55)

iss = lambda n, v=0, labels=(): {"number": n, "title": f"t{n}", "labels": [{"name": x} for x in labels],  # noqa: E731
                                 "reactions": {"+1": v}}
a = bot.decide([], [iss(3, 1), iss(7, 4), iss(2, 1)])
check("most voted first", a["kind"] == "new" and a["issue"] == 7)
a = bot.decide([], [iss(3, 1), iss(2, 1)])
check("tie -> oldest", a["issue"] == 2)
a = bot.decide([pr(ci="pending")], [iss(9)])
check("a PR waiting on CI doesn't block a new issue", a["kind"] == "new" and a["issue"] == 9)
a = bot.decide([pr(ci="pending"), pr(number=6, ci="pending", issue=2)], [iss(9)])
check("max PRs in flight -> wait instead", a["kind"] == "wait_ci")
a = bot.decide([pr(review="changes")], [iss(9, 10)])
check("finish started work before a new issue", a["kind"] == "address")

diff = """diff --git a/runner/runner.go b/runner/runner.go
--- a/runner/runner.go
+++ b/runner/runner.go
@@ -1 +1 @@
-x
+y // TODO later
diff --git a/runner/runner_test.go b/runner/runner_test.go
--- a/runner/runner_test.go
+++ b/runner/runner_test.go
@@ -1 +1 @@
-	assert.Equal(t, 1, f())
+	_ = f()
diff --git a/go.mod b/go.mod
"""
r = bot.report(diff)
check("report: protected go.mod", r["protected_touched"] == ["go.mod"])
check("report: removed assertion", len(r["removed_test_checks"]) == 1)
check("report: debug leftover", len(r["debug_leftovers"]) == 1)
r["without_change"] = {"checked": True, "pass_on_old_code": ["go test"], "fail_on_old_code": []}
hard = bot.hard_findings(r)
check("hard: tests that pass on old code", any("WITHOUT" in h for h in hard))

model = {"verdict": "ready", "summary": "fine", "unhappy": [{"case": "empty", "handled": True, "tested": True}],
         "probes": [{"input": "a", "got": "OK  one", "ok": True}, {"input": "b", "got": "two", "ok": True},
                    {"input": "c", "got": "invented", "ok": True}]}
out = bot.enforce(model, [], ["...OK one...", "two"], code_changed=True)
check("invented probe output -> changes", out["verdict"] == "changes")
check("verified flag", [p["verified"] for p in out["probes"]] == [True, True, False])
model["probes"] = model["probes"][:2] + [{"input": "c", "got": "three", "ok": True}]
out = bot.enforce(model, [], ["OK one", "two", "three"], code_changed=True)
check("all verified, all ok -> ready", out["verdict"] == "ready")
model["unhappy"].append({"case": "nil", "handled": False, "tested": False})
check("unhandled path -> changes", bot.enforce(model, [], ["OK one two three"], True)["verdict"] == "changes")

raw = "\x1b[30;46m\x1b[30;46m INFO \x1b[0m\x1b[0m \x1b[96m/tmp/p/md/demo.md:\x1b[0m\x1b[0m✅"
m2 = {"verdict": "ready", "summary": "ok", "unhappy": [], "probes": [{"input": "x", "got": "INFO /tmp/p/md/demo.md:✅", "ok": True}]}
check("probe output found through colour codes", bot.enforce(m2, [], [raw], code_changed=False)["probes"][0]["verified"])
m3 = {"verdict": "ready", "summary": "ok", "unhappy": [], "probes": [
    {"input": "x", "got": "[30;46m[30;46m INFO [0m[0m [96m[96m/tmp/rv1/d/a.md:[0m[0m✅", "ok": True},
    {"input": "y", "got": "[96m[96mecho other [95m[95m[Yes/no/continue/quit][0m[96m[0m[96m: [0m[0m", "ok": True}]}
raw3 = ["\x1b[30;46m\x1b[30;46m INFO \x1b[0m\x1b[0m \x1b[96m\x1b[96m/tmp/rv1/d/a.md:\x1b[0m\x1b[0m✅",
        "\x1b[96m\x1b[96mecho other \x1b[95m\x1b[95m[Yes/no/continue/quit]\x1b[0m\x1b[96m\x1b[0m\x1b[96m: \x1b[0m\x1b[0m"]
check("probe copied with bare colour codes is verified",
      all(p["verified"] for p in bot.enforce(m3, [], raw3, code_changed=False)["probes"]))
check("[Yes/no] is not a colour code", "[Yes/no/continue/quit]" in bot._norm("[95m[Yes/no/continue/quit][0m"))
# Notes for the human and the coder's pushback
RUNS = ["OK one", "two", "three", "-2"]
GOOD = [{"input": "a", "got": "OK one", "ok": True}, {"input": "b", "got": "two", "ok": True},
        {"input": "c", "got": "three", "ok": True}]


def rv(unhappy, probes=()):
    return bot.enforce({"verdict": "ready", "summary": "s", "unhappy": unhappy, "probes": GOOD + list(probes)},
                       [], RUNS, code_changed=True)


def wrong(case=""):
    return {"input": "-1", "got": "-2", "ok": False, "case": case}


def says(out, words):
    return any(words in c["body"] for c in out["comments"])


OLD = {"case": "Crash on  empty input", "handled": False, "tested": False, "pre_existing": True}
LIM = {"case": "huge files", "handled": False, "tested": False, "limitation": True, "note": "README: < 1 MB"}
out = rv([OLD], [wrong("  crash on empty INPUT ")])
check("pre-existing case and its wrong probe: a note, ready (case copied loosely)",
      out["verdict"] == "ready" and says(out, "Not for this PR (the base branch already has it)"))
out = rv([LIM], [wrong("huge files")])
check("documented limitation and its probe: a note, ready", out["verdict"] == "ready" and says(out, "deliberate limitation"))
check("a pre-existing case handled and tested is no note", not says(rv([{**OLD, "handled": True, "tested": True}]), "Not for this PR"))
check("a wrong probe naming no case still blocks", rv([OLD], [wrong()])["verdict"] == "changes")
check("a wrong probe on a case that is no note still blocks",
      rv([OLD, {"case": "nil", "handled": True, "tested": True}], [wrong("nil")])["verdict"] == "changes")
DIS = {"case": "a 20k-char line", "handled": False, "tested": False, "disputed": True}
out = rv([DIS], [wrong(DIS["case"])])
check("disputed and not answered: a note for the human, its probe too",
      out["verdict"] == "ready" and says(out, "the coder disputed it, the review doesn't answer"))
SAID = {**DIS, "rebuttal": "still wrong, as I said"}
check("repeating the remark is no answer", rv([SAID])["verdict"] == "ready")
out = rv([SAID], [wrong(SAID["case"])])
check("a rebuttal with this round's wrong probe: changes, the answer shown",
      out["verdict"] == "changes" and says(out, "Unhandled unhappy path: a 20k-char line")
      and says(out, "the review answers: still wrong"))
out = rv([SAID], [{**wrong(SAID["case"]), "got": "trust me, it breaks"}])
check("a paraphrased probe is no answer (and voids the review as before)",
      says(out, "the review doesn't answer") and says(out, "Unverifiable review"))
out = rv([SAID], [wrong("another case")])
check("a rebuttal backed by a wrong probe on ANOTHER case is no answer to this one",
      says(out, "the review doesn't answer") and not says(out, "Unhandled unhappy path: a 20k-char line"))
check("a new unhandled case still blocks", rv([{"case": "nil", "handled": False, "tested": False}])["verdict"] == "changes")

prev = bot.previous_round(
    [{"user": {"login": "rev[bot]"}, "state": "CHANGES_REQUESTED", "submitted_at": "2026-11-25T10:00:00Z", "body": "OLD"},
     {"user": {"login": "rev[bot]"}, "state": "DISMISSED", "submitted_at": "2026-11-25T11:00:00Z", "body": "BODY-42"},
     {"user": {"login": "alice"}, "state": "COMMENTED", "submitted_at": "2026-11-25T13:00:00Z", "body": "HUMAN"}],
    [{"user": {"login": "cod[bot]"}, "created_at": "2026-11-25T10:30:00Z", "body": "BEFORE"},
     {"user": {"login": "cod[bot]"}, "created_at": "2026-11-25T12:00:00Z", "body": "I disagree: run 3 <!-- bot {\"kind\": \"address\"} -->"}], reviewer="rev[bot]", coder="cod[bot]")
check("previous round: the reviewer's last review and the coder's replies since, markers stripped",
      "BODY-42" in prev and "I disagree: run 3" in prev and "OLD" not in prev and "BEFORE" not in prev
      and "HUMAN" not in prev and "<!--" not in prev)
check("no previous review, no previous round", bot.previous_round([], [], "rev[bot]", "cod[bot]") == "")
check("the reviewer is told about pushback, the coder that it may push back",
      "`rebuttal`" in bot.REVIEWER_SYSTEM and "push back" in open(bot.__file__).read())

s, m = bot.parse_final("blah\nSUBJECT: warn on unreachable breakpoint\nSUMMARY: did it.\nmore")
check("parse_final", s == "warn on unreachable breakpoint" and m.startswith("did it."))
check("legacy and current markers", bot.MARK.search('<!-- mr-bot {"kind": "a"} -->') and bot.MARK.search('<!-- bot {"kind": "b"} -->'))
check("config: tests vs code", bot.is_test("runner/x_test.go") and bot.is_test("test/run.sh") and bot.is_code("runner/x.go") and not bot.is_code("runner/x_test.go"))
check("config: gate from project.toml", [n for n, _ in bot.GATE][:3] == ["gofmt", "go vet", "go test"])
check("config: agent env expands {home}", bot.agent_env("/h")["GOPATH"] == "/h/go")
check("config: allowed commands added", "Bash(go:*)" in bot.CODER_TOOLS and "Bash(go:*)" in bot.REVIEWER_TOOLS)
check("config: prompts name the project", "markdown-runner" in bot.CODER_SYSTEM and "mr-probe" in bot.REVIEWER_SYSTEM)
_ms = [{"kind": "review"}] * 3 + [{"kind": "fix", "failing": ["x"]}] * 2 + [{"kind": "handover"}, {"kind": "address", "source": "human"}]
check("a human review starts a new bot cycle", bot.budgets(_ms)["review_rounds"] == 0 and bot.budgets(_ms)["fix_rounds"] == 0
      and bot.budgets(_ms)["human_rounds"] == 1)
check("reviews still count within a cycle", bot.budgets(_ms + [{"kind": "review"}] * 2)["review_rounds"] == 2)
check("protected glob", bot.protected(".github/workflows/x.yml") and not bot.protected("runner/x.go"))
sys.exit(1 if FAILED else 0)
