# Contributing to ParsRAG

Read `.agents/AGENTS.md` and the decisions in `.context/` before changing code.
Create work from `develop`, keep commits focused, and use Conventional Commits.
Never commit `.env`, API keys, indexed data, model weights, private documents, or
artifacts from `scratch/` and `testData/`.

## Local checks

```powershell
.\.venv\Scripts\python.exe -m ruff format --check backend backend/tests
.\.venv\Scripts\python.exe -m ruff check backend backend/tests
.\.venv\Scripts\python.exe -m mypy backend --strict
.\.venv\Scripts\python.exe -m pytest --cov=backend --cov-report=term-missing
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
