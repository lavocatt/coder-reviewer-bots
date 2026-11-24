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
  - an unhandled unhappy path forces "changes requested".
  It posts REQUEST_CHANGES or COMMENT, never APPROVE: an approval would count toward branch
  protection.
- **Humans**: when the bots agree, the PR is labelled `bot:ready` and a review is requested from
  `BOT_HUMANS`. A collaborator's comment on the PR starts a new coder round.
- **It stops itself** (`bot:stuck`):
  - per PR: 3 bot reviews, 4 CI fixes, 5 answers to humans, or the same CI failure twice;
  - cost: $15 a round, $50 per PR.
  Remove the label to grant it the same budget again: that wakes the bot at once.

The harness ([`bot/bot.py`](bot/bot.py): ~1400 lines of stdlib Python driving the `gh`, `git`, `openssl` and
`claude` CLIs) is a stateless reconciler. Each
run reads GitHub's state (labels, the `bot/review` commit status, `<!-- bot {...} -->` markers in
its comments), does the next actions and exits. No database, no server. It runs on issue and PR
events, on comments, and hourly.

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

Run `./install.sh` again: it refreshes `bot.py` and its tests and keeps your settings. The copy in
your repository is the one that runs, and it changes only through a reviewed PR. Treat the harness
like product code: the team owns it.

## License

Apache-2.0
