Last Edit: Codex - 2026-10-25 - Motive: Record verified dependency security and compatibility constraints.

# Maintenance Report

## Dependency compatibility

Actual install requirements constrain filelock to 3.20.3. Fresh installation with the unchanged plugin-manager range reproduces 19 pre-existing Client.crypto_key failures. The same failures occur on pristine dev; the security metadata/lock regressions pass. Narrowing plugin-manager below 0.9 made standalone tests pass but would conflict with the quota plugin, so no such bound is included. A coordinated Client API migration is outside this dependency patch.

Verification: 153 passed, 1 skipped, 19 pre-existing failures with a normal fresh install; pristine dev has the same 19 failures (151 passed, 1 skipped). The two new dependency regressions pass. Wheel/sdist builds and exact built-metadata checks pass.
See [tests/test_dependency_security.py](tests/test_dependency_security.py).
No deployment, package publication, or vulnerability exception is performed.

## Transparency Report

- AI model: Codex, GPT-5-based coding agent; a more specific runtime ID is not exposed.
- Actions: inspected source/primary advisories, edited dependency constraints,
  added tests/documentation, ran tests and package checks.
- Oversight: owner-authorized remediation; changes remain subject to PR review
  and the coordinating agent's merge/release checks.

