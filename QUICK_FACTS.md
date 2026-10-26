Last Edit: Codex - 2026-10-26 - Motive: Record the legacy manager and test-harness compatibility boundaries.

# Quick Facts

| Field | Value |
| --- | --- |
| Package | hivemind-core |
| Version | 4.10.2a8 |
| Entry points | hivemind-core console script; hivemind.policy ACL/deny-all; hivemind.performance.metrics core |
| filelock | Exact 3.20.3 in real installation requirements |
| Legacy manager API | hivemind-plugin-manager >=0.8.0a1,<0.9; Client.crypto_key remains required |
| Test/integration harness | hivescope >=0.6.6a1,<0.7; isolated shim forwards its identity password |

Source: [ClientDatabase](hivemind_core/database.py); [dependency evidence](docs/dependency-security.md).

