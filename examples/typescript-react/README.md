# React + TypeScript example — UNTESTED

A sketch of the bots' settings for a UI repository: Jest unit tests in the gate, Playwright e2e in
CI. Unlike `../markdown-runner/`, **no bot has run with it yet**. Treat it as a starting point for
a first pilot on a small repository, not as a known-good setup.

| File | Goes to |
|---|---|
| `project.toml` | `.bot/project.toml` |
| `CONVENTIONS.md` | `.bot/CONVENTIONS.md` (fill in the `<...>`) |
| `workflows/e2e.yml` | `.github/workflows/e2e.yml`, next to your `ci.yml` |

In `.github/workflows/bot.yml`, replace the toolchain step with:

```yaml
      - uses: actions/setup-node@v4
        with:
          node-version: '22'
```

In `codeql.yml`: `languages: javascript-typescript`, `build-mode: none`, and no Go setup.

## What to expect on a first pilot

- **Slow rounds**: every coder round, gate and old-code check starts from a fresh worktree and runs
  `yarn install` (from the shared cache in `/tmp/bot-cache`). Count from tens of seconds to minutes
  per install. Carrying `node_modules` between worktrees would be a harness change.
- **The reviewer tests through Jest**, not a browser: its probes are throwaway component tests,
  verified against their real output. Browser evidence comes from the e2e workflow in CI.
- **e2e tests aren't checked against the old code** (`ci_only_tests`): every review says so, and
  says what the old-code check did run.
- **Check the globs first**: `code` and `tests` decide what the old-code check reverts. Snapshots
  must be tests.
- **Check `failure_patterns` against a real failed log** of your CI: the bot uses them to tell two
  failures of the same job apart. If they match nothing, it falls back to job names, which is safe
  but stops sooner.
