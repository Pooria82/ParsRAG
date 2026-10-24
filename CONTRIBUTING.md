# Contributing to ParsRAG

Read [ARCHITECTURE.md](ARCHITECTURE.md), [DATA.md](DATA.md), and the decisions in
`.context/` before changing code.
Create work from `develop`, keep commits focused, and use Conventional Commits.
Never commit `.env`, API keys, indexed data, model weights, private documents, or
artifacts from `scratch/` and `testData/`.

Contributions must be proposed through a pull request to the official repository
at <https://github.com/Pooria82/ParsRAG>. By submitting a contribution, you
confirm that you own it and accept
[`CONTRIBUTOR_LICENSE_AGREEMENT.md`](CONTRIBUTOR_LICENSE_AGREEMENT.md). The
project owner must review every change. The repository license does not permit
publishing, deploying, or distributing a modified ParsRAG version while a pull
request is under review.

## Local checks

```powershell
.\.venv\Scripts\python.exe -m ruff format --check backend backend/tests
.\.venv\Scripts\python.exe -m ruff check backend backend/tests
.\.venv\Scripts\python.exe -m mypy backend --strict
.\.venv\Scripts\python.exe -m pytest --cov=backend --cov-report=term-missing
# Upload-to-answer pipeline with an in-memory Qdrant (CI runs it on a server);
# with PARSRAG_E2E set, a plain `pytest` runs every test with none skipped
$env:PARSRAG_E2E = "1"; .\.venv\Scripts\python.exe -m pytest backend/tests/e2e --no-cov
cd frontend
npm ci
npm test
npm run build
npm run test:e2e
```

Changes to behavior need deterministic tests. Live LLM evaluation belongs in a
separate, explicitly requested run and must identify the model, dataset snapshot,
configuration, and date. Pull requests should explain the user-visible result,
the trust-boundary impact, and the validation performed.

Dependabot proposes dependency updates. Rebuild `requirements.lock` from a clean
Python 3.12 environment, use `npm install` to update `package-lock.json`, review
upstream release and security notes, then run the complete local checks and image
scan. Container service images use explicit versions; update them in a dedicated
pull request and verify persistence compatibility before merging.

## Releases

The version is written once, in `VERSION`. To prepare release `x.y.z` on a
`release/x.y.z` branch:

1. Run `python scripts/set_version.py x.y.z` to update `VERSION` and its copies.
2. Write `release-notes/x.y.z.fa.md` and `release-notes/x.y.z.en.md`: a short,
   user-facing summary that the app shows after the update and in the update
   window. Keep the Persian and English notes saying the same thing.
3. Move the `Unreleased` CHANGELOG section under `x.y.z`.

After the squash merge to `main`, tag `vx.y.z`; the release workflow checks the
tag against `VERSION`. Installations find the release on their next daily check.
A release must keep data from any earlier version usable, because the update
script goes straight to the latest release.
