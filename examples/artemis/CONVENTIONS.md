# Apache Artemis (fork) — conventions for the bots (coder and reviewer)

Apache Artemis is a multi-protocol message broker (Core, AMQP, MQTT, STOMP, OpenWire) in Java,
built with Maven. You work on a fork: PRs go to the fork, never to apache/artemis.

**Read `AGENTS.md` at the root first.** Its *Code Quality*, *Quality Expectations*, *Testing Best
Practices*, *Security Model* and *Git History Review* sections apply to you as written. Its
process rules (JIRA ownership, branches, PR descriptions, reviewers, PR volume) are the harness's
and the humans' job here: ignore them.

## Layout
- `artemis-server/`: the broker. `artemis-core-client/`: the Core client. `artemis-journal/`:
  persistence. `artemis-protocols/<protocol>/`: AMQP, MQTT, STOMP, OpenWire.
- `artemis-commons/`, `artemis-cli/`, `artemis-web/`, `artemis-jms-*`, `artemis-jakarta-*`.
- Unit tests in each module's `src/test/java`. `tests/integration-tests/`: broker-level tests
  (`ActiveMQTestBase`, see `SimpleTest`). `tests/smoke-tests/` and `tests/soak-tests/` start full
  distributions: CI runs them, you don't.
- `docs/user-manual/*.adoc`: the documentation.

## Rules
- **Read before you write.** `git log` and `git blame` the code you change: don't revert deliberate
  behaviour. Follow the module's existing patterns.
- **A test with every change** that FAILS without your change: a JUnit 5 test in the module, or an
  integration test extending `ActiveMQTestBase` when it needs a broker. The reviewer runs your test
  classes against main's code: if they pass there, they prove nothing and the PR goes back.
- **Tests**: never `Thread.sleep()` (use `Wait.assertTrue(...)`), no resource leaks (`createServer()`,
  `createInVMNonHALocator()`, `addServer()`...), `logger.debug()` only, never `System.out`.
- **Never weaken a test** (no deleted or loosened assertion, no `@Disabled`).
- **The Apache License header** on every new file (copy it from a neighbour). Checkstyle and the
  license check run with `-Pdev`.
- **Docs**: a new or changed configuration parameter or behaviour is documented in
  `docs/user-manual/`; a security default change also in the upgrade guide.
- **Checks to run before you finish**: `sh .bot/mvn-changed.sh tests` (the modules you touched,
  Checkstyle, your test classes). The harness runs it again and refuses the round if it fails. CI
  then runs the full fast test suite on three JDKs.
- **Off-limits** (refused by the harness): `.github/`, `.bot/`, every `pom.xml` (no new dependency,
  no build change), `LICENSE`, `NOTICE`, `AGENTS.md`, `etc/`.
- Commit messages are written by the harness: give a good subject.
- English everywhere.
