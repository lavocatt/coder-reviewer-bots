# TODO project name — conventions for the bots (coder and reviewer)

Both bots read this file in every round. Write it for a new colleague who must deliver a good PR
without asking anything. Example: examples/markdown-runner/CONVENTIONS.md in the bots' repository.

TODO: one paragraph on what the project is and does.

## Layout
- TODO: the main directories, one line each: where the entry point, the domain logic and the
  tests live.

## Rules
- **Read before you write.** Find the existing pattern and follow it. No new dependency, no
  reformatting of code you didn't change, no drive-by refactors: change what the issue needs.
- **A test with every change** that FAILS without your change. TODO: where tests go, which
  framework. The reviewer runs your tests against the base branch's code: if they pass there, they
  prove nothing and the PR goes back.
- **Never weaken a test** (no deleted or loosened assertion). If behaviour was MEANT to change, say
  so in the summary.
- **Docs**: TODO: what must be documented where (README, help text, changelog...).
- **Checks to run before you finish**: TODO (the same as `[[gate]]` in project.toml). The harness
  runs them again and refuses the round if one fails.
- **Off-limits** (refused by the harness): `.github/`, `.bot/`, TODO (the `protected` paths).
- Commit messages are written by the harness as `[#<issue>] <subject>`: give a good subject.
- English everywhere.
