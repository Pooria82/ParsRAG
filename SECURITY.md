# Security policy

## Supported versions

| Version | Supported |
| --- | --- |
| 1.1.x | Yes |
| 1.0.x | No |
| 0.2.x and earlier | No |

## Reporting a vulnerability

Please use GitHub's **Report a vulnerability** flow in the repository Security
tab. Do not open a public issue for credentials, data disclosure, path traversal,
prompt-context exposure, or another exploitable finding.

Include the affected revision, deployment mode, reproduction steps, impact, and
any suggested mitigation. Remove real API keys and confidential documents from
the report. Maintainers should acknowledge a report within seven days and share
the remediation plan after triage.

ParsRAG is designed for one user on a workstation. Exposing it to a shared or
untrusted network without an authenticated reverse proxy is outside the supported
security boundary.

The API answers only to loopback host names (`localhost`, `127.0.0.1`, `::1`)
unless `PARSRAG_ALLOWED_HOSTS` lists others. This blocks DNS rebinding, where a
web page points its own domain at 127.0.0.1 to read documents or replace the
model endpoint. Browser requests that change state must also come from the
application's own origin or from `PARSRAG_ALLOWED_ORIGINS`.

### Local model endpoints

The app accepts an Ollama URL only as plain `http://host:port`, without
credentials, path, query, or fragment, on one of these hosts:
- loopback
- the `ollama` Compose service
- `host.docker.internal` (Ollama installed on the Docker host)
- hosts the operator lists in `OLLAMA_ALLOWED_HOSTS`

The browser cannot widen this list, so a page cannot point the app at an
arbitrary internal service through the Ollama setting.

Ollama itself has no authentication. On Docker Desktop (Windows, macOS), the
host's Ollama stays on `127.0.0.1` and is reached through Docker's forwarding.
On Linux, the containers can reach it only if it listens on another address:
- Prefer the Docker bridge address (for example `OLLAMA_HOST=172.17.0.1:11434`).
- `OLLAMA_HOST=0.0.0.0` exposes Ollama to every network the computer is on.
  Anyone who reaches the port can run the models and use the GPU. If you use
  it, restrict port 11434 with a firewall to Docker's subnets and use it only
  on a trusted private network.

### Runtime settings

`PUT`/`DELETE /settings/runtime` change only the settings listed in
`backend/core/domain/runtime_settings.py`, within the same bounds as `.env`.
Like every state-changing request, they must come from the application's own
origin. Settings that guard the trust boundary cannot be changed this way:
ports, `PARSRAG_ALLOWED_HOSTS`/`PARSRAG_ALLOWED_ORIGINS`,
`OLLAMA_ALLOWED_HOSTS`, the request ceiling, memory limits, and model
downloads. Upload limits cannot exceed the request ceiling fixed at startup.

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

The CPU and NVIDIA application images use Debian Trixie and PyTorch 2.13. The
AMD/ROCm overlay remains on PyTorch 2.6 for hardware compatibility pending
validation of a newer ROCm stack. Its PyTorch advisories remain open and should
be reviewed before AMD deployments. Debian Trixie's `libxml2` remains necessary
for Tesseract OCR; `CVE-2026-6653` has no stable Trixie fix as of 2026-09-24.
Do not dismiss that finding merely because the application has no direct XML API.
