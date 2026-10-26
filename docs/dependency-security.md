Last Edit: Codex - 2026-10-26 - Motive: Record actual passing legacy compatibility and authenticated harness checks.

# Dependency Security

The real installation source, `pyproject.toml`, pins `filelock==3.20.3`.
This maintains the classic FileLock interface accepted by upstream combo-lock's
`filelock~=3.0` requirement and Python 3.10. No direct URL or scanner exception
is used, and no claim is made that future advisories cannot affect this version.

## Evidence

The GitHub Advisory Database lists older affected ranges `<3.20.1`
([GHSA-w853-jp5j-5j7f](https://github.com/advisories/GHSA-w853-jp5j-5j7f)) and
`<3.20.3` ([GHSA-qmgc-5h2g-mvrw](https://github.com/advisories/GHSA-qmgc-5h2g-mvrw)).
The newer HIGH [GHSA-v4x8-3wr5-3wq8](https://github.com/advisories/GHSA-v4x8-3wr5-3wq8)
affects `>=3.20.4,<=4.2.0`. The additional
[GHSA-2g95-wg33-c5x2](https://github.com/advisories/GHSA-2g95-wg33-c5x2)
affects `>=4.1.0,<=4.2.0` and is fixed in 4.2.1. Exact 3.20.3 is outside the
reviewed affected ranges; this is not an exhaustive or permanent security
guarantee. Fresh consumer vulnerability scans remain required.

## Legacy API Boundary

This fork still reads `Client.crypto_key`. The real runtime requirement is now
`hivemind-plugin-manager>=0.8.0a1,<0.9`, explicitly rejecting the 0.9 API that
removed that field. Consumers requiring manager 0.9 or newer need a coordinated
Core/client API migration rather than a resolver override. Runtime source is
unchanged; the maintained consumer's separate graph is not modified here.

The test and integration extras use `hivescope>=0.6.6a1,<0.7`: 0.7 introduces
the newer Core connection constructor. A test-only adapter in
[e2e conftest](../tests/e2e/conftest.py) forwards the shim's existing per-test
identity password, matching the modern bus-client property. It neither invents
credentials nor changes handshake/Noise success. The replay test now captures
the real binary WebSocket frame because current clients send through
`NoiseTransport.send_message`, not the former `encrypt_frame` interception.
Verbatim replay must still reset the session and must not deliver twice.

## Verification

- Python 3.10 full `tests/`: 226 passed, three existing skips, one existing
  non-strict XPASS (`test_fifo_order_relay_chain`), no failures. No skip or xfail
  marker was added or changed.
- The six real protocol-matrix tests passed, including wrong-password rejection,
  tampered-negotiation rejection and replay teardown/no duplicate delivery.
- The separately installed `test,integration` extra passed the real OVOS query
  test (one passed); the ordinary test extra does not install that optional stack.
- [Regression tests](../tests/test_dependency_security.py) check the installed
  dependency, legacy manager boundary and real classic-lock contention/release.
- [Harness regressions](../tests/e2e/test_harness_compat.py) verify credential
  forwarding without caching or fabrication and the actual extra metadata.
- Fresh wheel-from-sdist build passed; metadata confirms exact filelock==3.20.3,
  manager >=0.8.0a1,<0.9, test-only harness bounds and no direct-URL dependency.
- [ClientDatabase](../hivemind_core/database.py) remains unchanged.

A passing library test does not approve a production rollout. The consuming
application's normal build and vulnerability gates remain required.

