Last Edit: Codex - 2026-10-26 - Motive: Record the tested legacy dependency boundary and real authentication harness repair.

# Maintenance Report

## Dependency compatibility

Actual install requirements constrain filelock to 3.20.3 and the legacy manager
API to >=0.8.0a1,<0.9. This fork requires `Client.crypto_key`; consumers requiring
the newer manager API need a coordinated migration, not a forced installation.
Test/integration extras retain the compatible hivescope 0.6 constructor API.
The test-only shim forwards its existing isolated identity password and replay
instrumentation captures real WebSocket frames. No authentication result is
faked, and no runtime protocol, credential, encryption or admission code changes.

Verification: Python 3.10 full suite 226 passed, three existing skips, one
existing XPASS; six protocol-matrix tests passed; separately installed optional
live-OVOS query test passed. Wheel-from-sdist build and actual metadata checks
passed. See [dependency tests](tests/test_dependency_security.py),
[harness tests](tests/e2e/test_harness_compat.py) and
[protocol matrix](tests/e2e/test_protocol_v3_matrix.py).
No deployment, package publication, or vulnerability exception is performed.

## Transparency Report

- AI model: Codex, GPT-5-based coding agent; a more specific runtime ID is not exposed.
- Actions: inspected source/primary advisories, edited dependency constraints,
  added tests/documentation, ran tests and package checks.
- Oversight: owner-authorized remediation; changes remain subject to PR review
  and the coordinating agent's merge/release checks.

