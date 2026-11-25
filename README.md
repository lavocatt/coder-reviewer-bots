# coder-reviewer-bots

Two AI bots that work on a GitHub repository's issues in CI: a **coder** (Claude Sonnet) opens a PR,
a **reviewer** (Claude Opus) reviews it, and they iterate under deterministic gates until they agree.
Then a human reviews and merges. Every round is priced, attributed and logged.

> **Bots iterate. Humans decide.** The bots never merge, and the reviewer never approves.

Piloted on [lavocatt/markdown-runner](https://github.com/lavocatt/markdown-runner) (a Go CLI): see
its `bot:*` PRs for real runs, and [`examples/markdown-runner/`](examples/markdown-runner) for its
settings.

## How it works

```
team vote ──> coder bot ──> gate ──> CI + CodeQL ──> reviewer bot ──> human
 (label,       (Sonnet,     (your     (your own       (Opus, own       reviews,
  👍 order)     no token)    checks)   pipeline)       account)         merges
                  ^            |          | red            | changes      | comment
                  └────────────┴──────────┴────────────────┴──────────────┘
```

- **A collaborator labels an issue `bot:todo`.** The queue is ordered by 👍 votes; two PRs at most
  are in flight.
- **The coder** (Claude Code headless) works in a throwaway worktree, as a separate Unix user, with an
  empty environment: no GitHub token. The harness commits and pushes for it.
- **The gate** runs your checks (`[[gate]]` in `project.toml`) and refuses protected files, binaries
  and diffs over 800 changed lines. A failure goes back to the same coder session.
- **CI and CodeQL** are your own workflows. New CodeQL alerts on the branch count as red.
- **The reviewer** is a second GitHub App and a different model, in a fresh session. It lists unhappy
  paths and *runs* the code (`[review] try_it`). The harness checks its review:
  - the PR's tests must fail on the base branch's code (`[[without_change]]`), or they prove nothing;
  - the outputs it quotes must appear in the commands it actually ran;
  - an unhandled unhappy path, or a wrong probe, forces "changes requested", except for notes left
    to the human: a problem the base branch already has, or a limitation the PR documents.
  It posts REQUEST_CHANGES or COMMENT, never APPROVE: an approval would count toward branch
  protection.
- **Pushback**: the coder may refuse a remark, with evidence. The reviewer sees its previous review
  and the coder's reply. A disputed remark blocks again only if the reviewer answers the argument
  with a probe from this round that shows it wrong. Otherwise it becomes a "Not for this PR" note
  for the human. Repeating the remark is not an answer.
- **Humans**: when the bots agree, the PR is labelled `bot:ready` and a review is requested from
  `BOT_HUMANS`. A collaborator's comment on the PR starts a new coder round.
- **It stops itself** (`bot:stuck`):
  - per PR: 3 bot reviews, 4 CI fixes, 5 answers to humans, or the same failing tests twice in a
    row (named per test with `[ci] failure_patterns`, else per job);
  - cost: $15 a round, $50 per PR.
  Remove the label to grant it the same budget again: that wakes the bot at once.

The harness ([`bot/bot.py`](bot/bot.py): ~1400 lines of stdlib Python driving the `gh`, `git`, `openssl` and
`claude` CLIs) is a stateless reconciler. Each
run reads GitHub's state (labels, the `bot/review` commit status, `<!-- bot {...} -->` markers in
its comments), does the next actions and exits. No database, no server. It runs on issue and PR
events, on comments, and hourly.

## How the reviewer is kept honest

A reviewer model can be lazy (it reads the diff and says "looks good"), or confidently wrong (it
quotes an output it never produced). The harness doesn't trust its words. It checks what a script
can check, and that overrides the model's verdict.

### Probes: run it, quote the output

The reviewer must *try* the change, not only read it. Each attempt is a **probe**, reported in its
structured verdict:

| Field | Meaning |
|---|---|
| `input` | what it ran: a command, a small input file, a throwaway test |
| `got` | the output, **copied verbatim** from a command it ran |
| `expected` | what the issue or the code's contract says should happen |
| `ok` | its judgment: does `got` match `expected`? |
| `case` | the unhappy path this probe demonstrates, if any (see below) |

How the harness checks the probes:

1. **Seen or invented.** Claude Code runs headless with `--output-format stream-json`, so the
   harness captures the output of every command the reviewer actually ran. A probe is *verified*
   only if its `got` appears in one of those outputs. Both sides are normalised first: colour codes
   (with or without the ESC byte, since models drop it when copying), whitespace and surrounding
   quotes are stripped. A `got` found nowhere makes the review **"unverifiable"**: changes requested.
2. **Enough evidence.** When the PR changes code, the review needs at least **3 verified probes**.
   The prompt asks for the issue's own case among them, but only the count is enforced. Otherwise it is an **"incomplete review"**: changes requested.
3. **A wrong output blocks.** A probe with `ok: false` forces changes requested, with the input, the
   output and the expected output, so the coder can fix it without guessing. The only exception is
   a probe on a case that is a note for the human (next section).

The review comment shows every probe in a table, with a "seen in output" column.

### Unhappy paths: hunt what the coder didn't test

A coder tests the happy path. The reviewer must list the **unhappy paths** of every changed
function: near-miss inputs, empty, huge or odd inputs, errors, timeouts, missing files. For each one
it says whether the case is `handled` and `tested`.
- An **unhandled** case forces changes requested.
- A handled but **untested** case gets a comment asking for the test.

Two kinds of case are **notes for the human**, not changes, so the coder isn't sent to rewrite code
outside the PR's scope:
- `pre_existing`: the base branch already has the problem, in code the PR neither adds nor changes;
- `limitation`: the PR deliberately leaves the case out of its own code and documents that (the
  reviewer quotes where), and the issue doesn't ask for it.

An undocumented gap is a real problem, not a limitation.

### Pushback: a remark must be argued, not repeated

The coder may refuse a remark with evidence: a run, a test, a line of code. The next review sees
its own previous review and the coder's replies. For each remark the coder disputes, the reviewer
has two options:
- **concede**: drop it, re-file it as a note, or mark it `disputed` with no answer, which makes it a
  "Not for this PR" note for the human;
- **answer**: write a `rebuttal` *and*, for an unhandled case, show a verified probe **from this
  round** that is wrong on that same case.

Repeating the remark, or a rebuttal backed by a probe on another case, isn't an answer: the remark
becomes a note. New problems block as usual. Without this rule, a reviewer can send the same
remark back every round until the review budget runs out.

### The PR's tests must fail without the PR

A test that passes on the old code proves nothing about the new code. Before every review the
harness builds a second worktree with the **PR's tests but the base branch's code**: every file
matching `[paths] code`, and not a test, is reverted. It then runs the `[[without_change]]`
commands there.
- **They must fail.** A failure to compile counts, since the tests use what the PR adds.
- If they all pass, that's a hard finding: *"The PR's tests also pass WITHOUT its code change"*.

Tests that need a running app (e2e, Playwright) can't run there. List them in
`[paths] ci_only_tests`: CI runs them, and the check covers the rest. Every bot review ends with one
line saying what the old-code check proved, or why it didn't run, so the human never has to assume.

This is mutation testing applied to the PR. The base branch's code is the mutant, and the PR's
tests must kill it.

The same automatic report also flags:
- protected files touched;
- code changed with no test changed;
- removed assertions (`[review] removed_check`);
- debug leftovers (`[review] debug`).

### What this doesn't prove

- A verified probe proves the reviewer **saw** that output, not that its `ok` judgment is right.
  That judgment is still the model's.
- Reviewer and coder are the same model family: correlated blind spots remain. A human still
  reviews before merging.
- The checks don't measure how deep the review went. Three trivial probes pass.

## Testing the harness

The harness is code that judges code, so it is tested like code.

```sh
python3 bot/test_bot.py    # offline checks of the pure logic, no GitHub, no model: < 1 s
python3 bot/mutants.py     # mutation checks of those tests: under a minute
```

CI runs both on every push and PR (Python 3.11 and 3.13), and installs the bots into a scratch
repository: the templates' TODOs must stop the bot, and the installed tests must pass.

`test_bot.py` covers the decisions (what to do next on each PR state), budgets, the queue, probe
verification, notes and pushback, the automatic report, and the settings loaded from
`project.toml`.

**Mutants prove the tests guard the rules.** A passing test suite says nothing about whether it
would catch a broken rule. `mutants.py` breaks one rule at a time on purpose, in a throwaway copy of
`bot.py`, and runs the tests:

| Verdict | Meaning |
|---|---|
| **killed** | the tests fail: the rule is guarded |
| **SURVIVED** | the tests still pass with the rule broken: a missing test |
| **STALE** | the code the mutant targets moved: update the mutant |

The 21 mutants cover:
- the reviewer: an invented output accepted, fewer than 3 probes, colour codes breaking the match,
  wrong probes or unhandled cases not blocking, a rebuttal without evidence;
- the PR's tests: tests passing on the old code, code changed without tests;
- a timed-out check leaving its processes running;
- CI failures: a test renamed when its line moves, failures named per job again, the old-code
  check silent about what it didn't run;
- the bots' limits: protected paths, the dollar cap, the same failure twice, the review budget,
  budgets after `bot:stuck` and after a human review;
- the human's priority: a human remark first, no bot work on a PR handed over.

When the mutants were first added, two of them survived: nothing tested the 3-probe minimum or the
code-without-tests rule. The tests were added before the mutants were committed.

**When you change a rule, add its mutant.** One line of `bot.py` and a broken version of it, plus a
test that kills it. A rule with no mutant is a rule nobody has proven the tests guard.

Not covered (they call GitHub): that the reviewer never APPROVES, label changes, and pushes. Those are
checked on real runs.

## What it costs

Every coder round and review posts its cost on the PR. `bot:ready` comes with a ledger: rounds,
dollars, agent time. `python3 .bot/bot.py ledger` prints the table for every bot PR.

The pilot's first issue: 12 coder rounds, 12 reviews, 35 min of agent time, **$7.62**, at API
prices. Several of those rounds were lost to harness bugs that are fixed since.

## Security model, honestly

- **What protects you**: the agent runs as an unprivileged user in a disposable CI VM, without any
  GitHub token. The bots' Apps lack the `workflows` permission, so they can't edit the pipeline
  that judges them, and the harness refuses changes to `.github/` and `.bot/`. Only collaborators
  can queue an issue or wake the bot with a comment.
- **What doesn't**: the allowed-commands list (`[agent] allow`) is not a boundary, since a test can
  run anything. The agent holds the model key and has network access: a malicious issue could try
  to exfiltrate that key (prompt injection). Use a dedicated key with a spending limit.

## Install it on a repository

**1. Files.** Run `./install.sh /path/to/your/repo`. It copies `bot.py` and its tests into `.bot/`,
plus templates it never overwrites:

| File | What to do |
|---|---|
| `.bot/project.toml` | Fill in every TODO: project description, code/test paths, gate commands, allowed commands, how the reviewer tries a change. The bot refuses to start while a TODO is left. |
| `.bot/CONVENTIONS.md` | The rules both bots read every round: layout, where tests go, docs. The better this is, the fewer rounds. |
| `.github/workflows/bot.yml` | Replace the toolchain step (marked `>>> YOUR TOOLCHAIN`). |
| `.github/workflows/codeql.yml` | Set your language(s), or drop it and remove it from `[ci] workflows`. |

Add `workflow_dispatch:` to every workflow listed in `[ci] workflows`: the bot dispatches CI itself
when its push didn't trigger it.

Check the install with `python3 .bot/test_bot.py`.

**Other languages.** Only the settings change, never `bot.py`:
- `project.toml`: globs, gate and old-code commands, allowed commands, caches, `try_it`, the
  failure patterns;
- `CONVENTIONS.md`;
- the toolchain step of `bot.yml`;
- CodeQL's `languages`.

| Example | Status |
|---|---|
| [`examples/markdown-runner/`](examples/markdown-runner) | Go CLI, **run for real** (the pilot) |
| [`examples/typescript-react/`](examples/typescript-react) | React + TypeScript, Jest in the gate, Playwright e2e in CI: **untested sketch** |
| [`examples/artemis/`](examples/artemis) | Apache Artemis fork (Java, Maven, ~40 modules): builds only the changed modules; **script and patterns tested on a real checkout, no bot run yet** |

The template's comments give `failure_patterns` for Go, Jest, Playwright and pytest. For a
compiled language, point its package cache at `/tmp/bot-cache` in `[agent.env]`, for example
`GOMODCACHE` or `-Dmaven.repo.local` in `MAVEN_OPTS`. Every round starts from a fresh worktree.

**Browsers and clusters.** The bots run in a plain CI VM: no browser session of their own, and no
cluster. UI behaviour is checked in two places:
- the reviewer's component-test probes;
- your e2e workflow in CI (Playwright), which the bots wait for and fix like any other check.

E2e against a cluster (an OpenShift console plugin on CRC, say) runs only where your CI already
provides one. Giving the bots a cluster of their own is possible, but heavy in resources: weigh it
only once the cheaper layers have shown what they miss.

**2. Two GitHub Apps** (Settings → Developer settings → GitHub Apps → New). No webhook, no callback
URL. Generate a private key for each, and install each on the repository.

| App | Read and write | Read |
|---|---|---|
| Coder (e.g. `myrepo-coder`) | Contents, Pull requests, Issues, Actions | Checks, Commit statuses, Code scanning alerts |
| Reviewer (e.g. `myrepo-reviewer`) | Pull requests, Issues, Commit statuses | Contents, Checks |

Give neither App the *Workflows* permission.

Without the Apps, both bots fall back to the workflow token (`github-actions[bot]`). It works, but
the reviewer can only comment, since an identity can't request changes on its own PR, and nothing
tells the two bots apart.

**3. Secrets and variables** (repository settings, or `gh`):

```sh
R=owner/repo
gh variable set BOT_CODER_APP_ID    -R $R -b <coder app id>
gh secret   set BOT_CODER_APP_KEY   -R $R < coder.private-key.pem
gh variable set BOT_REVIEWER_APP_ID -R $R -b <reviewer app id>
gh secret   set BOT_REVIEWER_APP_KEY -R $R < reviewer.private-key.pem
gh secret   set ANTHROPIC_API_KEY   -R $R    # or CLAUDE_CODE_OAUTH_TOKEN from `claude setup-token`
gh variable set BOT_HUMANS          -R $R -b "alice,bob"   # who gets the review requests
```

**4. Try it.** Run the *bot* workflow manually with *dry run* to check both identities and print
what it would do. Then label an issue `bot:todo`.

## Settings

Repository variables, all optional:

| Variable | Default | |
|---|---|---|
| `BOT_MODEL` | `sonnet` | the coder's model |
| `BOT_REVIEW_MODEL` | `opus` | the reviewer's model: keep it different from the coder's |
| `BOT_MAX_USD_PER_ROUND` | `15` | one coder round or review |
| `BOT_MAX_USD_PER_PR` | `50` | then `bot:stuck`; counted since the last stuck |
| `BOT_MAX_DIFF_LINES` | `800` | added + deleted lines vs the base branch; for reference, Google's [Small CLs](https://google.github.io/eng-practices/review/developer/small-cls.html) calls ~100 reasonable, 1000 too large |
| `BOT_HUMANS` | repo owner | comma-separated logins asked to review |
| `BOT_CI_WAIT_MIN` | `30` | how long one wait for CI lasts; raise it for a slow CI (Maven, e2e) |

The round budgets (3 reviews, 4 CI fixes, 5 human rounds, 2 PRs in flight) are constants at the top
of `bot.py`.

## Day to day

| Label | Meaning | You |
|---|---|---|
| `bot:todo` | queued; 👍 on the issue moves it up | label an issue to queue it |
| `bot:doing` | the bots are iterating | nothing |
| `bot:ready` | the bots agree, CI is green | review; comment to send it back to the coder; merge |
| `bot:stuck` | a budget or the no-progress rule stopped it | read why (last bot comment), fix the issue or the harness, remove the label (the bot goes on at once) |

The transcripts of every agent session are uploaded as a workflow artifact
(`bot-transcripts-<run id>`).

## Updating

Run `./install.sh` again: it refreshes `bot.py` and its tests and keeps your settings. Before you
change the harness, run `python3 bot/test_bot.py` and `python3 bot/mutants.py` in this repository. The copy in
your repository is the one that runs, and it changes only through a reviewed PR. Treat the harness
like product code: the team owns it.

## License

Apache-2.0
