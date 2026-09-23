# Security policy

## Supported versions

| Version | Supported |
| --- | --- |
| 0.1.x | Yes |
| Earlier snapshots | No |

## Reporting a vulnerability

Please use GitHub's **Report a vulnerability** flow in the repository Security
tab. Do not open a public issue for credentials, data disclosure, path traversal,
prompt-context exposure, or another exploitable finding.

Include the affected revision, deployment mode, reproduction steps, impact, and
any suggested mitigation. Remove real API keys and confidential documents from
the report. Maintainers should acknowledge a report within seven days and share
the remediation plan after triage.

ParsRAG 0.x is designed for one user on a workstation. Exposing it to a shared or
untrusted network without an authenticated reverse proxy is outside the supported
security boundary.

## Documented transitive advisory

`llama-index-core` requires NLTK. ParsRAG pins NLTK 3.10.3 but does not call the
model import/export APIs affected by `PYSEC-2026-3740` / `CVE-2026-81726`, does
not use NLTK as a filesystem sandbox, and does not pass upload paths to those
APIs. CI therefore suppresses only this advisory while retaining all other
`pip-audit` findings as release blockers. The suppression must be removed when
NLTK publishes a patched version or if ParsRAG starts using an affected API.

The container scan blocks HIGH/CRITICAL findings with a published fix. Trivy
uploads SARIF for visibility into findings without a published fix; these are
not release blockers until an upgrade is possible. This includes the NLTK
advisory above and unfixed Debian packages in the base image. Review the
findings on every release and upgrade the base image when fixes are published.
