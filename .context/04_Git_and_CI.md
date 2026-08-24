# Git Workflow & CI/CD Strategy

## 1. Git Workflow Strategy
To maintain velocity while ensuring absolute stability for a production-grade system, ParsRAG follows a strict **GitHub Flow** strategy (a simplified, fast-paced alternative to traditional GitFlow).

- **`main` Branch:** The production branch. It is heavily protected and strictly deployable at any given moment. Direct commits to `main` are universally forbidden.
- **`staging` (or `uat`) Branch:** The pre-production testing branch. Merged from `develop` before a release.
- **`develop` Branch:** The active integration branch. All feature branches merge here first for continuous integration.
- **Feature Branches:** All work stems from `develop`. Branches must branch off and merge into `develop` using the following strict naming conventions:
  - `feat/issue-number-short-desc` (e.g., `feat/12-hybrid-rag-strategy`)
  - `fix/issue-number-short-desc` (e.g., `fix/34-ollama-timeout-error`)
  - `docs/short-desc`
  - `refactor/short-desc`
- **Pull Requests (PRs):** Merging into `main` requires a formal PR. 
  - The CI/CD pipeline must pass 100%.
  - The PR must receive at least one code review approval.
  - Squash and Merge is mandated to keep the `main` history strictly linear and readable.
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

# 6. Chainlit & UI
.chainlit/

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
An automated CI/CD pipeline (e.g., GitHub Actions) acts as the ultimate gatekeeper. The pipeline runs sequentially on every Push and PR to `main`.

1. **Linting Job:**
   - Runs `ruff format --check .` to guarantee formatting.
   - Runs `ruff check .` to catch unused imports and complexity violations.
2. **Type Checking Job:**
   - Runs `mypy backend/ --strict` to ensure 100% type safety on the API and core logic.
3. **Testing Job:**
   - Spins up Qdrant locally via GitHub Actions services.
   - Runs `pytest backend/tests/` to execute all unit and integration tests.
   - *Requirement:* Fails if code coverage drops below 85%.
4. **Docker Build Job (Dry Run):**
   - Runs `docker-compose build` to verify that the containerized microservices build without errors.

## 5. Release & Versioning Strategy
- **Versioning:** We strictly adhere to **Semantic Versioning (SemVer) 2.0.0** (`MAJOR.MINOR.PATCH`).
  - `MAJOR`: Breaking architectural changes (e.g., migrating from LlamaIndex to a new framework).
  - `MINOR`: New backwards-compatible features (e.g., adding GraphRAG).
  - `PATCH`: Backwards-compatible bug fixes (e.g., fixing a UI typo).
- **Tagging:** Releases are triggered automatically when a Git Tag (e.g., `v1.2.0`) is pushed to `main`. The CI pipeline detects the tag, generates a GitHub Release, builds the production Docker images, and publishes them to the container registry.
