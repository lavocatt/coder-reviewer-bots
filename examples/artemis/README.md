# Apache Artemis example (fork)

The bots' settings for a fork of [Apache Artemis](https://github.com/apache/artemis): Java, Maven,
about 40 modules, JDK 25 to build. The bots work the **fork's** GitHub issues and open PRs on the
**fork**. Upstreaming a result (JIRA, `ARTEMIS-NNNN` commit, upstream PR) stays a human's job.

## What was tested, and what wasn't

| | Status |
|---|---|
| `mvn-changed.sh`: module and test detection | ran on a real Artemis checkout |
| `mvn-changed.sh tests`, change in `artemis-commons` | 17 s, Checkstyle + only the changed test class |
| `mvn-changed.sh tests`, change in an integration test | 73 s: 29 modules built, Checkstyle, the one test class (warm local Maven repository; a cold CI cache adds the downloads) |
| `failure_patterns` | matched surefire 3's real failure line on a deliberately failing test |
| The bots end to end on Artemis | **not run yet** |
| The bot dispatching the fork's `build.yml` (it has required inputs, with defaults) | **not verified** |

## Files

| File | Goes to |
|---|---|
| `project.toml` | `.bot/project.toml` |
| `CONVENTIONS.md` | `.bot/CONVENTIONS.md` |
| `mvn-changed.sh` | `.bot/mvn-changed.sh` (protected: the bots run it, can't edit it) |
| `workflows/codeql.yml` | `.github/workflows/codeql.yml` (Java, `build-mode: none`) |

Artemis's own `build.yml` already has `workflow_dispatch`, so the bot can dispatch it.

## Why a script instead of `mvn install`

A full Artemis build with the fast tests takes up to an hour per JDK. The gate runs after every
coder round, so it must be minutes. `mvn-changed.sh`:
- finds the Maven modules the change touches (the nearest `pom.xml` above each changed file);
- builds them and what they need (`-pl … -am`) with `-Pdev`: Checkstyle and license headers;
- runs only the test classes the change adds or edits (`-Dtest=…`).

The old-code check runs the same script on the base branch's code: the PR's test classes must
fail there. CI, the fork's `build.yml`, then runs the full fast suite on three JDKs.

## `bot.yml`: the toolchain step

Replace the Go setup with JDK 25 and a cache for the bots' Maven repository:

```yaml
      # >>> YOUR TOOLCHAIN
      - uses: actions/setup-java@v5
        with:
          java-version: '25'
          distribution: temurin
      - uses: actions/cache@v4
        with:
          path: /tmp/bot-cache/m2
          key: bot-m2-${{ hashFiles('**/pom.xml') }}
          restore-keys: bot-m2-
      # <<<
```

The sandbox user must be able to write to the restored cache. In the *Sandbox user* step, after
`sudo mkdir -p /tmp/bot-cache ...`, add:

```sh
sudo chmod -R a+rwX /tmp/bot-cache
```

## Repository variables

| Variable | Value | Why |
|---|---|---|
| `BOT_CI_WAIT_MIN` | `75` | `build.yml` runs up to 60 min per job |
| `BOT_MAX_DIFF_LINES` | `800` (default) | Artemis changes are often small; lower it if PRs sprawl |

Each bot push runs the fork's whole `build.yml`: 3 JDKs × (tests + checks). That's free on a
public fork, but it's the slowest part of a round, and each fix or review round waits for it.

## Where it conflicts with Artemis's `AGENTS.md`

`CONVENTIONS.md` tells the bots to follow `AGENTS.md`'s code and test rules and to ignore its
process rules. Those process rules assume an agent working upstream:

| `AGENTS.md` asks | Here |
|---|---|
| attribution "Claude Code on behalf of …" | bot commits and reviews are signed by the two Apps, each naming its model; add the operator's name before upstreaming |
| JIRA ticket ownership | the fork's GitHub issues; a human links JIRA when upstreaming |
| `ARTEMIS-NNNN` commit messages | the harness writes `[#<issue>] <subject>`; rewrite when upstreaming |
| request 2 committers' reviews | `BOT_HUMANS` gets the review request on the fork |
| max 10 PRs a day | 2 PRs in flight at most |
| never approve own PRs | the reviewer never approves anything |
