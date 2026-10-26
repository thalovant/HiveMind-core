Last Edit: Codex - 2026-10-26 - Motive: Explain the legacy dependency and test-harness compatibility boundaries.

# FAQ

## Why is filelock pinned exactly?

3.20.3 contains the earlier fixes and predates the newer affected features.
A broad 3.x range can select an affected version. See the primary ranges and
verified limits in [dependency security](docs/dependency-security.md).

## Does this alter runtime behavior?

[ClientDatabase](hivemind_core/database.py) and the authentication/protocol code
are unchanged. The installer now explicitly requires the manager's 0.8 API:
this legacy fork still reads `Client.crypto_key`, which manager 0.9 removed.
Consumers requiring manager 0.9 or newer need a coordinated API migration;
they must not force an incompatible installation of this legacy fork.

## Why is the test harness bounded below 0.7?

Hivescope 0.7 changes its connection constructor to the newer Core API. The
compatible 0.6 line predates the bus client's `password` property. A test-only
adapter forwards the existing isolated identity credential, matching the newer
harness's implementation. It does not supply a password, set a handshake-success
flag or alter encryption. Replay tests capture the real binary WebSocket frame
instead of an obsolete internal encryption callback.

