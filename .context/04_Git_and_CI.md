# Git Workflow & CI/CD Strategy

## 1. Git Workflow Strategy
ParsRAG uses a **GitFlow-style** model with two long-lived branches. There is no
`staging` branch: `develop` is the pre-release integration branch.

- **`main` Branch:** Released code only, one squash commit per release. Protected: required status checks (also for administrators) and resolved conversations; no direct pushes.
- **`develop` Branch:** The integration branch. Every change reaches it through a pull request whose checks pass, merged with a merge commit.
- **Work Branches:** Branch from `develop` as `feat/`, `fix/`, `docs/`, `refactor/`, `perf/`, `ci/`, or `chore/` plus a short description (for example `fix/answer-language`). Dependabot opens its own branches against `develop`; its Python updates also need the pin in `requirements.lock`.
- **Releases:** A `release/x.y.z` branch from `develop` bumps the version and the CHANGELOG, then a pull request to `main` is **squash-merged**. The `vX.Y.Z` tag on that commit runs the release workflow. Afterwards a `chore/sync-develop-x.y.z` branch merges `main` back into `develop`.
- **Granular Committing Rule:** Work must *always* start on the `develop` branch (or a feature branch branching from it). A commit MUST be made immediately after completing each section, phase, or after making significant changes to a file or directory. Large monolithic commits are forbidden.
- **Test-Driven Execution Rule:** After implementing any section or phase, you MUST write the related automated tests (e.g., unit tests). You must run the code (if possible) and execute the tests to guarantee correct functionality *before* making the granular commit.

## 2. Commit Message Convention
We enforce **Conventional Commits** (`type(scope): message`) to allow for automated changelog generation and semantic version bumping.
- **Allowed Types:** `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`.
- **Examples:**
  - `feat(core): implement Condense Question pipeline`
  - `fix(db): resolve Qdrant connection timeout`
  - `chore(deps): bump LlamaIndex to 0.10.x`

## 3. Comprehensive `.gitignore` Blueprint
To prevent bloat and security leaks, the `.gitignore` strictly blocks environment variables, massive vector databases, LLM weights, and Python caches.

```gitignore
# 1. Environment & Secrets
.env
.env.*
secrets.toml
credentials.json

# 2. Vector DB Storage (Qdrant)
qdrant_storage/
qdrant_snapshots/

# 3. LLM Weights & HuggingFace Caches
models/
.cache/
huggingface/
*.bin
*.gguf
*.pt
*.safetensors

# 4. Virtual Environments
.venv/
venv/
env/
ENV/

# 5. Python & Bytecode
__pycache__/
*.py[cod]
*$py.class
.pytest_cache/
.ruff_cache/
.mypy_cache/

# 6. Frontend build output
node_modules/
dist/

# 7. Raw Data & Uploads
data/
uploads/
documents/
*.pdf
*.txt
*.docx

# 8. OS & IDE
.DS_Store
.vscode/
.idea/
*.swp
```

## 4. CI/CD Pipeline Architecture
GitHub Actions runs on every push and pull request to `develop` and `main`.

1. **Quality workflow (`quality.yml`):**
   - `backend` on Ubuntu, macOS, and Windows: `ruff format --check`, `ruff check`, `mypy backend --strict`, and `pytest` with branch coverage (fails below 85%).
   - `frontend` on the same three systems: `npm ci`, `npm audit --audit-level=high`, unit tests, the production build, Playwright end-to-end tests, and the PWA test.
   - `end-to-end`: the `backend/tests/e2e` suite against a Qdrant service container.
   - `packaging`: `docker compose config`, `docker build`, and an import of the application inside the image.
2. **Supply-chain workflow (`supply-chain.yml`, also weekly):** dependency review on pull requests, `pip-audit` of `requirements.lock`, and a Trivy scan of the built image uploaded to code scanning.
3. **CodeQL** runs on pull requests to `main`.

## 5. Release & Versioning Strategy
- **Versioning:** We strictly adhere to **Semantic Versioning (SemVer) 2.0.0** (`MAJOR.MINOR.PATCH`).
  - `MAJOR`: Breaking architectural changes (e.g., migrating from LlamaIndex to a new framework).
  - `MINOR`: New backwards-compatible features (e.g., adding GraphRAG).
  - `PATCH`: Backwards-compatible bug fixes (e.g., fixing a UI typo).
- **Tagging:** Pushing a `vX.Y.Z` tag on `main` runs `release.yml`: it checks that the tag matches the project version, repeats the backend and frontend checks, builds the Docker image and imports the application in it, and creates the GitHub Release (its notes are then replaced with the CHANGELOG section). Images are built, not published: users build them with `docker compose`. Publishing to a registry is a later plan (roadmap Phase 19).
