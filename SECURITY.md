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
and to the names `PARSRAG_ALLOWED_HOSTS` adds; loopback always stays allowed
(the container health check and the update script use it). This blocks DNS
rebinding, where a web page points its own domain at 127.0.0.1 to read
documents or replace the model endpoint. Browser requests that change state must also come from the
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

### Model API endpoints and keys

- **Address checks:**
  - An OpenAI-compatible API URL must be plain HTTP(S), without credentials,
    query, or fragment.
  - Public endpoints must use HTTPS.
  - Every request re-checks the host's addresses and refuses link-local
    (cloud metadata), multicast, and reserved targets.
  - Redirects are never followed, so neither a DNS change nor a redirect can
    send the prompt or the key elsewhere.
- **Keys:**
  - Each API key is held for one host (scheme, host, port) and is only ever
    sent to it. The key in `.env` (`MODEL_API_KEY`) belongs to
    `MODEL_API_BASE_URL`. A connection saved for another host, including at
    startup, gets no key rather than that one.
  - An external API cannot be saved without a key for its host.
  - Keys stay in process memory or the environment and are never written to
    browser storage, logs, API responses, or the saved model configuration.

### Update check and update scripts

- **The daily check:**
  - Once a day the server asks GitHub for the public release list
    (`api.github.com`) and the release notes of newer versions
    (`raw.githubusercontent.com`).
  - The requests carry nothing about the installation except the running
    version in the `User-Agent`; GitHub sees the address they come from.
  - Turn the check off in Settings or with `UPDATE_CHECK_ENABLED=0`.
  - `PARSRAG_UPDATE_REPOSITORY` points it at a fork; it only selects which
    public repository is read.
- **The scripts** (`scripts/update.ps1`, `scripts/update.sh`):
  - They run on the host with the user's own `git` and `docker`, refuse a copy
    with changed tracked files, and check out a release tag of the clone's
    `origin`.
  - Before changing anything they copy `.env` and the Qdrant and model-settings
    volumes to `backups/`. That copy of `.env` holds any API key it contains,
    so treat `backups/` as secret. It is excluded from git and from the Docker
    build context.

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
