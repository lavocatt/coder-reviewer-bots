# <name> — conventions for the bots (coder and reviewer)

UNTESTED SKETCH for a React + PatternFly UI in TypeScript: replace every <...> and check each rule
against the real repository.

<One paragraph: what the UI does, for whom, what backend it talks to.>

## Layout
- `src/components/`: <...>. `src/pages/`: <...>. `src/api/`: <the backend calls>.
- Unit tests next to the code: `Foo.tsx` -> `Foo.test.tsx` (Jest, React Testing Library).
- `e2e/*.spec.ts`: Playwright, run by CI only (it needs the running app).

## Rules
- **Read before you write.** Follow the existing components and hooks. PatternFly components, not
  hand-made HTML. No new dependency (`package.json` and `yarn.lock` are off-limits).
- **A test with every change** that FAILS without your change: a `*.test.tsx` with React Testing
  Library, querying by role and label as a user would (no test ids unless the code already uses them).
  A user-visible flow -> also a Playwright case in `e2e/` when it fits the existing ones.
- **Never weaken a test**; no `.only`, no `.skip`; update a snapshot only when the change is meant
  to alter it, and say so in the summary.
- **Strings** go through <the i18n helper>; no hard-coded user-facing text.
- **Checks to run before you finish**: `yarn lint`, `yarn tsc --noEmit`, `yarn jest --ci`. The
  harness runs them again and refuses the round if one fails. Playwright runs in CI.
- **Off-limits** (refused by the harness): `.github/`, `.bot/`, `package.json`, `yarn.lock`, `LICENSE`.
- English everywhere.
