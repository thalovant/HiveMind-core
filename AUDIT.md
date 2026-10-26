Last Edit: Codex - 2026-10-26 - Motive: Replace reproduced incompatibility findings with tested boundaries and actual full-suite results.

# Audit

The security constraint is carried by the real installer, not solely by a
scanner input. [Dependency tests](tests/test_dependency_security.py) verify
exact filelock selection, lock behavior and the legacy manager API boundary.
The Python 3.10 full suite now passes: 226 passed, three existing skips and one
existing non-strict XPASS. The optional live-OVOS query test passed separately
with the integration extra installed. No skip/xfail marker was changed.

The previously reproduced 19 `Client.crypto_key` failures are prevented by the
real `hivemind-plugin-manager>=0.8.0a1,<0.9` constraint. This is an explicit legacy
compatibility boundary, not a claim of compatibility with consumers requiring
the newer manager API. The test-only hivescope 0.6 adapter forwards the isolated
identity password and leaves real authentication in place. All six Noise matrix
tests pass, including wrong-password, tampered-negotiation and replay rejection.
The replay probe captures the real WebSocket frame instead of a retired internal
encryption callback. Wheel-from-sdist metadata checks passed.

Remaining maintenance: `test_fifo_order_relay_chain` has an existing XPASS
marker that deserves separate feature-status review. The current proof does not
claim that the older manager/harness lines implement newer upstream APIs.

ClientDatabase in [the runtime source](hivemind_core/database.py) is not modified.
This is not a complete audit of that implementation. Future advisory checks
and consumer artifact tests remain required; [evidence](docs/dependency-security.md).

