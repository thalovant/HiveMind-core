Last Edit: Codex - 2026-10-25 - Motive: Record verified dependency security and compatibility constraints.

# FAQ

## Why is filelock pinned exactly?

3.20.3 contains the earlier fixes and predates the newer affected features.
A broad 3.x range can select an affected version. See the primary ranges and
verified limits in [dependency security](docs/dependency-security.md).

## Does this alter runtime behavior?

[ClientDatabase](hivemind_core/database.py) is unchanged. The regression tests exercise classic
lock contention and real dependency metadata. Fresh installation with the unchanged plugin-manager range reproduces 19 pre-existing Client.crypto_key failures. The same failures occur on pristine dev; the security metadata/lock regressions pass. Narrowing plugin-manager below 0.9 made standalone tests pass but would conflict with the quota plugin, so no such bound is included. A coordinated Client API migration is outside this dependency patch.

