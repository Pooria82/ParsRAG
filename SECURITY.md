# Security policy

## Supported versions

Security fixes are applied to the latest revision on `develop` until the first
tagged release. After releases begin, this table will identify supported tags.

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
