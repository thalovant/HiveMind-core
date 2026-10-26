Last Edit: Codex - 2026-10-26 - Motive: Record remaining manager migration and harness maintenance work.

# Suggestions

| Problem | Proposal | Impact |
| --- | --- | --- |
| An exact compatibility pin can become stale | Recheck all filelock advisory ranges during consumer release scans | Prevent stale security assumptions |
| Dependency APIs can change independently of this package | Retain [installed metadata and behavior tests](tests/test_dependency_security.py); review bounds before widening | Catch fresh-install incompatibilities |
| This legacy fork still requires the manager 0.8 Client API | Migrate Client.crypto_key and dependent consumers together before removing the <0.9 bound | Prevent silently installing an incompatible manager |
| The legacy test harness does not follow newer Core constructor changes | Keep [shim contract tests](tests/e2e/test_harness_compat.py) and the real Noise/replay matrix; remove the adapter only after a compatible harness migration | Preserve security coverage without faking authentication |

Source boundary: [ClientDatabase](hivemind_core/database.py).

