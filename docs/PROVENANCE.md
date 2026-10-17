# Provenance

Small utilities in this repository are shared patterns across the portfolio repos: a cassette provider, invariant checks over a JSONL trace, structured JSON logging, bounded retries, and `secretscan.py`. They are maintained in parallel with the other portfolio repos and kept aligned by the contract those utilities share.

`secretscan.py` is vendored byte-for-byte. `secretscan.py sha256: 2cdf0339ef5a85d4f6439e94c973b5858375f9da0e2d38da9b503e06d0f6dff7`

What was adapted here is the interview-scheduling domain: the mock calendar, the two human gates, the tool registry with effect classes, the scripted conversation policy, and the synthetic FAQ. All people, mailboxes, and calendar rows are synthetic and belong to the fictional co-op Taller Aurora. Nothing in this repository is copied from any employer or client work.
