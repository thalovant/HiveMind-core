Last Edit: Codex - 2026-10-25 - Motive: Record verified dependency security and compatibility constraints.

# Audit

The security constraint is carried by the real installer, not solely by a
scanner input. [Dependency tests](tests/test_dependency_security.py) verify
exact filelock selection and lock behavior. 153 passed, 1 skipped, 19 pre-existing failures with a normal fresh install; pristine dev has the same 19 failures (151 passed, 1 skipped). The two new dependency regressions pass.

Fresh installation with the unchanged plugin-manager range reproduces 19 pre-existing Client.crypto_key failures. The same failures occur on pristine dev; the security metadata/lock regressions pass. Narrowing plugin-manager below 0.9 made standalone tests pass but would conflict with the quota plugin, so no such bound is included. A coordinated Client API migration is outside this dependency patch.

ClientDatabase in [the runtime source](hivemind_core/database.py) is not modified.
This is not a complete audit of that implementation. Future advisory checks
and consumer artifact tests remain required; [evidence](docs/dependency-security.md).

