Last Edit: Claude Opus 5.5 - 2026-11-07 - Motive: Record removal of the unreachable relay-shape branch in the e2e helpers.

# Maintenance Report

## 2026-11-07: e2e relay helpers use one result shape

`tests/e2e/test_query_streaming_e2e.py` (`_relay_chain`, `_two_relay_chain`)
and `tests/e2e/test_relay_e2e.py` (`_relay_chain`) accepted both a
`RelayNode` and a legacy `(satellite, master)` tuple from
`hivescope.topology.TopologyBuilder.add_relay`. The test extra pins
`hivescope>=0.6.6a1,<0.7`, and the only release in that range (0.6.6a1)
returns a `RelayNode`, so the tuple branch could never run. It is removed;
the helpers now read `RelayNode.listener` and fail loudly if the shape ever
changes. Test-only change; no runtime code touched.

Verification: full suite on Python 3.12, 226 passed, three existing skips,
one existing XPASS (`test_fifo_order_relay_chain`).

- AI model: Claude Opus 5.5.
- Actions: removed the dead compatibility branch in three test helpers and
  corrected the helper docstring.
- Oversight: coordinating agent review plus CI before merge.

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

