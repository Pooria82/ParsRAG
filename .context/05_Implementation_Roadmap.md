# 05. Implementation Roadmap: ParsRAG

## Overview
This document serves as the self-executable, atomic roadmap for building the ParsRAG system from scratch. It strictly adheres to the architectural boundaries defined in the `.context/` ADRs. The tasks are sequenced using Domain-Driven Design (DDD) principles: foundation first, interfaces second, concrete implementations third, API fourth, and UI/Docker last.

---

## Phase 1: Project Initialization & Configuration

### Task 1.1: Dependency & Environment Setup
**Description:** Initialize the Python environment and install core dependencies.
**Actionable Steps:**
- [x] Initialize the project (e.g., using `poetry init` or `requirements.txt`).
- [x] Install core backend libraries: `fastapi`, `uvicorn`, `llama-index`, `qdrant-client`, `pymupdf`.
- [x] Install the React 18, TypeScript, and Vite frontend toolchain.
- [x] Install dev dependencies: `ruff`, `mypy`, `pytest`, `pytest-asyncio`.
- [x] Create `.env.example` defining required environment variables (e.g., `QDRANT_HOST`, `OLLAMA_BASE_URL`).

### Task 1.2: Directory Structure & Git Ignore
**Description:** Scaffold the exact directory tree defined in `03_Tech_Standards.md`.
**Actionable Steps:**
- [x] Create the `.gitignore` file exactly as specified in `04_Git_and_CI.md`.
- [x] Create `backend/api/`, `backend/core/models/`, `backend/core/strategies/`, `backend/core/interfaces/`.
- [x] Create `backend/infrastructure/database/`, `backend/infrastructure/llm/`, `backend/infrastructure/parsers/`.
- [x] Create the `frontend/src/`, `frontend/public/`, and `frontend/tests/` directories.
- [x] Add `__init__.py` files where necessary to define backend Python modules.

### Checkpoint: Phase 1
- [x] Run `ruff check .` to ensure zero errors in the empty structure.
- [x] Confirm `.gitignore` protects against accidental large file commits and raw user data leaks (e.g. PDFs).

---

## Phase 2: Core Domain Models & Interfaces

### Task 2.1: Domain Models (Pydantic)
**Description:** Define the strict data contracts that cross system boundaries.
**Actionable Steps:**
- [x] Create `backend/core/models/domain.py`.
- [x] Implement `DocumentIngestionRequest` (file data, session ID).
- [x] Implement `QueryRequest` (prompt, chat history via `ChatMessage`, mode).
- [x] Implement `ExtractedNode` (text, metadata, score) and strict `QueryResponse`.

### Task 2.2: Abstract Base Classes (ABCs)
**Description:** Define the interfaces to adhere to the Open-Closed Principle.
**Actionable Steps:**
- [x] Create `backend/core/interfaces/repository.py` and define `AbstractDocumentRepository` with `save_nodes`, `similarity_search`, `delete_session`.
- [x] Create `backend/core/interfaces/strategy.py` and define `AbstractQueryStrategy` with an `execute(request: QueryRequest)` method.

### Checkpoint: Phase 2
- [x] Run `mypy backend/` to ensure the base schemas and interfaces are 100% type-safe.

---

## Phase 3: Infrastructure Implementations (Data & Logic Layers)

### Task 3.1: Qdrant Repository Implementation
**Description:** Implement the concrete database layer.
**Actionable Steps:**
- [x] Create `backend/infrastructure/database/qdrant_repo.py`.
- [x] Implement `QdrantRepository` inheriting from `AbstractDocumentRepository`.
- [x] Add logic to filter by global vs. session-scoped namespaces using Qdrant's payload filtering.

### Task 3.2: Document Parsing & Chunking
**Description:** Build the ingestion pipeline for Persian RTL text (handling `.docx` and `.pptx` files).
**Actionable Steps:**
- [x] Create `backend/infrastructure/parsers/document_parser.py` using `python-docx` and `python-pptx`.
- [x] Implement logic to extract text accurately from Word documents and PowerPoint slides.
- [x] Create `backend/infrastructure/parsers/chunker.py` using LlamaIndex `SentenceSplitter` configured for Persian (500-1000 char size, 150 overlap).

### Task 3.3: LLM & Embeddings Factory
**Description:** Configure global Settings for Ollama and the multilingual embedding model (keeping prompt templates encapsulated in strategies).
**Actionable Steps:**
- [x] Create `backend/infrastructure/llm/factory.py`.
- [x] Instantiate the LlamaIndex `Settings.llm` pointing to the local Ollama instance.
- [x] Instantiate `Settings.embed_model` pointing to a local multilingual embedding model.

### Checkpoint: Phase 3
- [x] Write a basic unit test in `tests/` to mock Qdrant and verify the chunking logic outputs valid `ExtractedNode` models.

---

## Phase 4: Query Routing & Strategies

### Task 4.1: Condense Question Pipeline
**Description:** Build the conversational memory logic.
**Actionable Steps:**
- [x] Create `backend/core/condenser.py`.
- [x] Implement logic to inject chat history and the current query into a LlamaIndex prompt to rewrite pronouns into a standalone question.

### Task 4.2: Concrete RAG Strategies
**Description:** Implement the three distinct execution modes, encapsulating their specific prompt templates and returning strict `QueryResponse` objects.
**Actionable Steps:**
- [x] Create `backend/core/strategies/strict_rag.py`. Implement logic to halt if retrieval similarity is too low (0% hallucination target).
- [x] Create `backend/core/strategies/llm_only.py`. Bypass Qdrant entirely.
- [x] Create `backend/core/strategies/hybrid_rag.py`. Retrieve from Qdrant, pass to FlashRank reranker, then to LLM.

---

## Phase 5: FastAPI Backend & Endpoints

### Task 5.1: Dependency Injection Setup
**Description:** Wire up the interfaces to concrete implementations for FastAPI.
**Actionable Steps:**
- [x] Create `backend/api/dependencies.py`.
- [x] Provide functions `get_document_repository()` and `get_query_strategy(mode)`.

### Task 5.2: API Routes & Exception Handling
**Description:** Expose the REST API and handle errors gracefully at the application boundary.
**Actionable Steps:**
- [x] Create `backend/api/routes.py` with `/ingest` and `/query` endpoints.
- [x] Create `backend/main.py` initializing the FastAPI app.
- [x] Add a global exception handler in `main.py` to intercept `ParsRAGError` domain exceptions (timeouts, empty docs), returning a clean 500 JSON response.

### Checkpoint: Phase 5
- [x] Run `pytest` to ensure all backend routing logic passes.
- [x] Spin up `uvicorn backend.main:app` locally and hit `/docs` to verify OpenAPI schema.

---

## Phase 6: Improvement and Refinement (99.99% Confidence Sign-off)

This phase serves as the critical validation gate before any UI or orchestration is introduced. It strictly audits the previous 5 phases for edge cases, performance bottlenecks, language-specific nuances (Persian), and architectural compliance.

### Task 6.1: Infrastructure & Resource Validation (Data Layer)
**Description:** Stress-test Qdrant and Ollama to ensure they behave predictably under load and within hardware constraints (6GB VRAM limit).
**Actionable Steps:**
- [x] **VRAM Profiling:** Spin up `qwen2.5:7b` via Ollama and monitor VRAM usage during peak inference. Ensure it stays within the 6GB limit without swapping to CPU RAM. (Verified on RTX 3060: baseline 4692 MiB, peak 4756 MiB / 6144 MiB, headroom 1388 MiB, zero CPU swapping).
- [x] **Qdrant Indexing Audit:** Verify that Qdrant collections are created with the exact correct vector dimensions (from the HuggingFace embedding model) and that the `session_id` payload index is successfully created for O(1) filtering. (Verified on live Docker Qdrant: 768 dimensions, Cosine distance, session_id indexed as KEYWORD, session isolation validated).
- [x] **Connection Resilience:** Simulate a database timeout or Ollama crash during a request and verify the backend fails gracefully (intercepted by `ParsRAGError`). (Verified: caught `VectorDBConnectionError`, returned sterile HTTP 500 without stack trace leaks).

### Task 6.2: Persian Data Ingestion Rigor (Parsing & Chunking)
**Description:** Ensure the ingestion pipeline handles complex Persian (RTL) text flawlessly.
**Actionable Steps:**
- [x] **Encoding & RTL Validation:** Upload a `.docx` or `.pptx` file with complex Persian text (containing Zero-Width Non-Joiners / نیم‌فاصله) and extract the exact chunks to verify encoding isn't mangled. (Successfully verified using DOCX/PPTX parsers).
- [x] **Chunk Boundary Inspection:** Extract overlapping chunks and manually inspect them to guarantee the LlamaIndex `SentenceSplitter` is respecting Persian sentence boundaries (periods, question marks) rather than slicing mid-word. (Verified across 31 extracted chunks).
- [x] **Malformed Payloads:** Send corrupted or unsupported files and verify the exact HTTP 400/413 behavior and error messaging. (Tested with corrupted docx, unsupported .exe, and >50MB files).

### Task 6.3: Retrieval & Re-ranking Precision (RAG Core)
**Description:** Validate the mathematical boundaries of the RAG strategies.
**Actionable Steps:**
- [x] **FlashRank Validation:** In `HYBRID` mode, track the node scores before and after FlashRank. Confirm that FlashRank correctly elevates the most semantically relevant Persian nodes to the top. (Elevated top nodes with 0.9999 and 0.9997 confidence).
- [x] **Strict Mode Thresholding:** In `STRICT` mode, deliberately ask an out-of-domain question. Verify the vector similarity score falls below the accepted threshold and the pipeline short-circuits to prevent hallucination. (Verified zero hallucination with exact refusal behavior).
- [x] **Conversational Memory (Anaphora):** Test the `CondenseQuestionPipeline` with a 4-turn conversation containing complex Persian pronouns (e.g., "او چه گفت؟", "آن کجا بود؟"). Verify the LLM successfully rewrites the prompt into a standalone question. (Verified 100% resolution with Gemma 26B).

### Task 6.4: API Security, Concurrency, and Load
**Description:** Guarantee the FastAPI layer acts as an impenetrable shield.
**Actionable Steps:**
- [x] **Zero-Leakage Audit:** Deliberately trigger internal `KeyError`s and division-by-zero exceptions inside the strategy layers. Assert that the `POST /query` endpoint returns a sterile HTTP 500 JSON without leaking a single line of stack trace. (Verified sterile HTTP 500 responses).
- [x] **Input Sanitization:** Attempt Path Traversal or NoSQL injection payloads inside the `session_id` parameter to ensure Pydantic V2 rigorously sanitizes inputs. (Verified HTTP 422 / 400 rejections).
- [x] **Concurrency Test:** Send 10 simultaneous asynchronous requests to `/query` to observe how the FastAPI threadpool and Qdrant/Ollama handle concurrent locks. (Verified with asyncio.gather without race conditions).

### Checkpoint: Phase 6 (Final Sign-off)
- [x] **Test Coverage:** All 46 tests pass consistently without race conditions.
- [x] **Architectural Compliance:** 100% adherence to DDD, with no leakage of Qdrant logic into the API routes (Dependency Injection successfully applied to Strategies).
- [x] **Sign-off:** Achieving 99.99% confidence across reliability, speed, and accuracy. System is declared production-ready for UI integration.

---

## Phase 7: Comprehensive Multi-Document Evaluation & Verification (All Modes)

This phase conducts exhaustive, systematic validation across all document files in `testData/` before frontend integration. For each file, ground-truth questions and answers are extracted directly from the text, and rigorously evaluated across Document Knowledge Only (`STRICT`), Hybrid Mode (`HYBRID`), and Model Knowledge Only (`LLM_ONLY`), with rate-limiting pacing to prevent quota exhaustion.

### Task 7.1: Ground Truth Dataset Extraction
**Description:** Inspect each of the 10 Persian documents (.docx and .pptx) in `testData/` and formulate ground-truth Q&A pairs (factual extraction, multi-hop reasoning, and out-of-domain negative controls).
**Actionable Steps:**
- [x] Parse and inspect text from all 10 files in `testData/`.
- [x] Formulate multiple positive factual questions per document with direct text citations.
- [x] Formulate out-of-domain negative control questions per document to test strict rejection.

### Task 7.2: Rigorous Multi-Document Testing across All Modes
**Description:** Ingest each document under an isolated session in Qdrant and execute tests across all three operational modes.
**Actionable Steps:**
- [x] **Document Knowledge Only (Strict RAG):** Highest priority. Verify 100% factual accuracy against document ground truth and 0% hallucination on out-of-domain questions. (Verified 10/10 out-of-domain refusals with 0.0% hallucination, and factual extraction across all 10 documents).
- [x] **Hybrid Mode:** Verify intelligent fusion of retrieved document context and model reasoning, prioritizing retrieved ground truth. (Verified grounded synthesis across all 10 documents).
- [x] **Model Knowledge Only:** Verify the model generates coherent answers based solely on parametric knowledge without accessing vector documents. (Verified on general knowledge questions).
- [x] **Rate Limiting & Pacing:** Implement automatic backoff and request throttling to remain strictly within API RPM/RPD quotas. (Verified with 4.5s pacing with 0 HTTP 429 errors across 50 requests).

### Checkpoint: Phase 7 (Multi-Document Verification Report)
- [x] Generate comprehensive evaluation report detailing accuracy, precision, refusal behavior, and latency across all 10 documents and 3 modes. (Generated `Phase7_Evaluation_Report.md` and `phase7_evaluation_results.json`).
- [x] Ensure 0 leakage between sessions during multi-document evaluations. (Verified session isolation across all 10 sessions).

---

## Phase 8: Frontend Integration (React)

### Task 8.1: React Application
**Description:** Build the bilingual user-facing chat workspace.
**Actionable Steps:**
- [x] Create the React 18 and TypeScript application under `frontend/src`.
- [x] Implement accessible controls for the three RAG modes.
- [x] Implement session-scoped document upload and selection.
- [x] Connect the workspace to the FastAPI query and model-configuration endpoints.

---

## Phase 9: Production Packaging, Orchestration & OCR

The active UI is a Vite-built React application served by FastAPI. Production
therefore uses one immutable application image rather than separate UI and API
containers. Qdrant and Ollama remain infrastructure adapters behind the existing
repository and model-provider boundaries. API-backed models remain configurable,
but credentials are supplied only at runtime and are never baked into an image.

### Task 9.1: Reproducible Application Image
**Description:** Package the React build, FastAPI runtime, document parsers, and OCR tools in one production image.
**Actionable Steps:**
- [x] Add a root multi-stage `Dockerfile`: Node builds `frontend/dist`; a slim Python stage installs declared runtime dependencies and copies only application artifacts.
- [x] Install Tesseract with Persian and English language data in the runtime stage.
- [x] Run the application as an unprivileged user and expose only port 8000.
- [x] Add `.dockerignore` rules for secrets, local environments, caches, test data, generated builds, and vector/model storage.
- [x] Add an image-level health check against FastAPI `/health`.

### Task 9.2: Local Service Orchestration
**Description:** Run the application with persistent Qdrant and Ollama services on an isolated Compose network.
**Actionable Steps:**
- [x] Add `compose.yaml` with `app`, `qdrant`, `ollama`, and one-shot `ollama-init` services.
- [x] Configure named volumes for Qdrant collections, Ollama models, and the Hugging Face embedding cache.
- [x] Pass `QDRANT_HOST=qdrant` and `OLLAMA_BASE_URL=http://ollama:11434` through environment configuration without weakening public URL validation.
- [x] Gate app startup on healthy Qdrant and gate optional model provisioning on healthy Ollama; API-provider deployments do not require Ollama.
- [x] Keep Ollama reachable only through the application network; publish only the application port by default.
- [x] Make the initial Ollama model configurable with `OLLAMA_MODEL`, while preserving API-provider deployments through `.env`.

### Task 9.3: Scanned PDF OCR Adapter
**Description:** Extend PDF parsing with bounded, traceable OCR while preserving native text extraction as the fast path.
**Actionable Steps:**
- [x] Add a Tesseract infrastructure adapter with environment-controlled enablement, languages, DPI, timeout, and maximum page count.
- [x] OCR only PDF pages that contain no selectable text; keep native and OCR pages in original order.
- [x] Preserve page metadata for citations and normalize OCR output before chunking.
- [x] Return specific, localized-safe validation errors when OCR is disabled, unavailable, times out, or exceeds configured limits.
- [x] Add unit tests for native PDFs, fully scanned PDFs, mixed native/scanned PDFs, disabled OCR, missing OCR runtime, and page limits.

### Task 9.4: Runtime Configuration & Operations
**Description:** Make local and container startup explicit, safe, and maintainable.
**Actionable Steps:**
- [x] Replace example credentials with placeholders and document every Docker/OCR environment variable.
- [x] Allow only loopback or the explicit internal Ollama service hostname for Ollama configuration.
- [x] Remove obsolete Windows launcher scripts superseded by documented Vite, Uvicorn, and Compose commands.
- [x] Update `README.md` with local development, Docker startup, model provisioning, persistence, health checks, and shutdown instructions.
- [x] Add deterministic tests for Compose configuration, Docker build inputs, environment defaults, and internal Ollama URL validation.

### Checkpoint: Phase 9
- [x] Run backend tests, Ruff, strict mypy, frontend tests, and the Vite production build.
- [x] Validate `docker compose config` without exposing secrets.
- [x] Build the production application image and verify its non-root user and health check.
- [x] Start the app and Qdrant, verify `/health`, and confirm indexed data survives a Qdrant restart through the named volume.
- [x] Upload native and scanned Persian documents and confirm the scanned chunk retains page metadata for citations.
- [x] Verify live local inference through the production Ollama adapter. On September 18, the native Ollama service completed configuration validation with the installed `qwen2.5:7b` model and returned the exact `LOCAL_OK` probe response.
- [x] Start the optional Compose Ollama profile, pull `qwen2.5:7b` into the persistent model volume, verify it with `ollama list`, and complete an in-container generation probe returning the exact `LOCAL_OK` response.

---

## Phase 10: Offline-First Public Release Hardening

ParsRAG is a single-user, offline-first application for personal and corporate
workstations. Local Ollama remains the privacy-preserving default. Users without
suitable hardware may explicitly connect to either an OpenAI-compatible service
inside their own network or an external model API. The interface and runtime must
make the selected trust boundary visible: document context leaves the workstation
only when the user enables a remote API endpoint.

### Task 10.1: Product Boundary & Safe Network Defaults
**Description:** Make the supported deployment model explicit and safe by default without removing corporate or external model APIs.
**Actionable Steps:**
- [x] Document local Ollama, private/corporate API, and external API as three explicit trust modes.
- [x] Bind the Compose application port to loopback by default and require an explicit host override for LAN exposure.
- [x] Replace wildcard CORS with configurable same-origin/local-development origins and reject untrusted browser origins on state-changing requests.
- [x] Validate model API URLs: allow HTTP for loopback/private-network endpoints, require HTTPS for public endpoints, and reject credentials, query strings, fragments, metadata/link-local, multicast, and unspecified addresses.
- [x] Add a visible disclosure before enabling a non-local model API because prompts and retrieved document context can leave the workstation.
- [x] Remove absolute privacy and hallucination claims; scope evaluation statements to the tested dataset, model, and date.

### Task 10.2: Model Connection Lifecycle
**Description:** Make runtime model selection reliable across local Ollama, corporate OpenAI-compatible services, and external APIs.
**Actionable Steps:**
- [x] Preserve separate model names and base URLs when switching providers, including the internal Compose Ollama hostname.
- [x] Allow API services with optional credentials so trusted corporate endpoints without API keys remain supported.
- [x] Verify `/models` for OpenAI-compatible APIs and `/api/tags` for Ollama before reporting a successful connection.
- [x] Persist non-secret active model settings atomically; load secrets only from the environment or current process memory.
- [x] Explain restart behavior for runtime-only API keys and never persist an API key in browser storage, logs, responses, or committed files.
- [x] Report whether an API credential exists in service memory even while Ollama is active, without returning the credential itself.
- [x] Align model, retrieval-threshold, and OCR defaults across code, `.env.example`, Compose, frontend state, and documentation.

### Task 10.3: Session Isolation & Data Lifecycle
**Description:** Ensure a single workstation user can understand, enumerate, and completely remove locally indexed data.
**Actionable Steps:**
- [x] Require session IDs for ingestion and document-backed queries; remove implicit globally shared uploads.
- [x] Make “clear all data” delete every known backend session before clearing browser state, and report partial failures.
- [x] Add Qdrant pagination so file discovery is correct beyond the first 1,000 points.
- [x] Derive and validate vector dimensions from the configured embedding model instead of hard-coding 768.
- [x] Version Qdrant collections by embedding configuration and document the migration/reset path when embeddings change.
- [x] Document localStorage and Qdrant retention, backup, restore, and secure deletion behavior.

### Task 10.4: Resource & Input Hardening
**Description:** Bound memory, CPU, parser, and inference work on personal workstations.
**Actionable Steps:**
- [x] Enforce request-body and aggregate batch limits before unbounded reads; stream uploads into bounded buffers.
- [x] Validate file signatures in addition to extensions and reject oversized or suspicious DOCX/PPTX archives before parsing.
- [x] Bound prompt length, history count, history message length, filename length, and allowed chat roles with Pydantic.
- [x] Add configurable concurrency limits for ingestion and query work and return explicit overload responses.
- [x] Add deterministic tests for oversized bodies, archive expansion, forged extensions, large histories, and concurrent saturation.

### Task 10.5: Runtime Health, Cancellation & Progress
**Description:** Report the real service state and avoid misleading controls.
**Actionable Steps:**
- [x] Split liveness and readiness endpoints; readiness must verify model initialization and Qdrant access.
- [x] Keep the UI available while large local embedding assets initialize and expose a clear preparing state.
- [x] Distinguish byte upload progress from server-side parsing, OCR, embedding, and indexing progress.
- [x] Expose short-lived, non-sensitive query progress identifiers and show understanding, retrieval, and generation as real pipeline stages.
- [x] Propagate cancellation where the active model adapter supports it; otherwise label the action as stopping local display and prevent stale responses.
- [x] Add structured request logging with correlation IDs while redacting prompts, document text, and credentials.

### Task 10.6: Architecture & Maintainability
**Description:** Remove duplicate contracts and align the implementation with repository coding rules.
**Actionable Steps:**
- [x] Consolidate the duplicate async/sync query strategy interfaces into one contract and remove unused domain types.
- [x] Split oversized frontend orchestration/state modules where responsibilities can be isolated without prop proliferation.
- [x] Render assistant Markdown mathematics with KaTeX, reveal completed answers progressively with reduced-motion support, and keep direction based on response content.
- [x] Preserve prompt edits as navigable conversation branches and generate a concise model-backed title after the first successful turn.
- [x] Replace the generic sidebar storage card with the active provider/model and localize technical-field placeholders without changing their input direction.
- [x] Enforce Google-style public docstrings in Ruff and resolve the existing docstring findings.
- [x] Add canonical `pyproject.toml` configuration for Ruff, mypy, pytest, coverage, and project metadata.
- [x] Add collection/schema versioning notes and architecture decisions for single-user scope and remote-model trust boundaries.

### Task 10.7: Automated Quality & Supply-Chain Controls
**Description:** Make the checks described by the repository enforceable on every public contribution.
**Actionable Steps:**
- [x] Add GitHub Actions for backend tests, Ruff, strict mypy, frontend tests/build, coverage, Compose validation, and Docker build.
- [x] Enforce an achievable coverage baseline, publish coverage output, and add end-to-end browser smoke tests for core workflows.
- [x] Pin the tested Python dependency set with a lock/constraints artifact and keep the npm lockfile authoritative with `npm ci`.
- [x] Add Dependabot configuration, dependency review, secret scanning guidance, SBOM generation, and container vulnerability scanning.
- [x] Pin release container inputs by immutable version/digest where practical and document the update process.

### Task 10.8: Public Repository & Release Readiness
**Description:** Publish a credible, legally usable, and maintainable first release.
**Actionable Steps:**
- [x] Replace the permissive development license with an owner-controlled source-available license, contributor agreement, copyright notice, citation metadata, CODEOWNERS rule, security policy, contribution guide, code of conduct, changelog, PR template, and issue templates.
- [x] Replace documentation promises that are not implemented and provide a reproducible evaluation harness for quantitative claims. The September 18 benchmark records model, retrieval, latency, scoring, OCR, and regression evidence only in ignored local artifacts; no private fixtures or generated evaluation reports are committed.
- [x] Document hardware, storage, first-start downloads, offline provisioning, API data flow, and source-only versus container installation.
- [x] Merge `develop` into protected `main` through CI, configure the GitHub remote, and create the first pre-1.0 semantic version tag after the release checks pass.

### Task 10.9: Multi-Format Ingestion & Hardware-Aware Runtime
**Description:** Expand safe document ingestion while keeping CPU-only machines usable and accelerating model workloads on supported GPUs.
**Actionable Steps:**
- [x] Replace duplicated upload constants with one bounded backend policy and expose the effective limits and extensions through `/capabilities`.
- [x] Raise the default capacity to 10 documents per session, 100 MiB per file, and 500 MiB per batch while preserving request-body, archive, duplicate-name, and session-total validation.
- [x] Add structured parsing for Markdown, JSON, CSV, HTML/XML, YAML, configuration, log, and common source-code files.
- [x] Add bounded OCR for standalone images and images embedded in DOCX/PPTX while retaining native text extraction as the preferred path.
- [x] Stream ingestion into bounded Qdrant upsert batches and configure embedding batches, CPU threads, OCR dimensions, and container memory ceilings through `.env`.
- [x] Add CPU, NVIDIA CUDA, and Linux AMD ROCm Compose paths; accelerate both local embeddings and Ollama when the selected overlay exposes a supported GPU.
- [x] Add a low-VRAM NVIDIA overlay that prioritizes full GPU generation by running embeddings on CPU and reducing the default Ollama context.
- [x] Synchronize `.env.example`, Compose defaults, backend capabilities, frontend validation, and localized upload guidance.
- [x] Add complete English and Persian deployment documentation covering API, CPU, NVIDIA, AMD, Ollama provisioning, resource tuning, persistence, and verification.
- [x] Add deterministic parser, OCR, upload-policy, batching, device-selection, Compose-overlay, and development-proxy tests.

### Checkpoint: Phase 10
- [x] Run all backend, frontend, coverage, browser, Compose, container, and documentation checks from a clean working tree.
- [x] Verify live local Ollama inference through the application model configuration and generation path with native Ollama `qwen2.5:7b`; the exact probe response was `LOCAL_OK`.
- [x] Verify a keyless mock private OpenAI-compatible endpoint without sending project data to the public internet.
- [x] Evaluate all seven private PDF fixtures in Strict, Hybrid, and LLM-only modes with `google/gemma-4-26b-a4b-it`, including a real 14-page scanned-PDF OCR path and a post-fix Persian Hybrid regression.
- [x] Verify remote API disclosure, optional-key behavior, validated connection failure, and configuration restart behavior.
- [x] Verify forged and oversized uploads, saturation controls, complete data deletion, Qdrant pagination, and embedding-schema mismatch handling.
- [x] Confirm no secrets or private test documents exist in the tracked tree or Git history before creating the public remote.
- [x] Verify 10-file session limits, 100 MiB file limits, broad text/image parsing, embedded Office OCR, bounded vector upserts, and runtime capability discovery.
- [x] Validate base, NVIDIA, low-VRAM NVIDIA, and AMD Compose configurations; verify the CUDA app detects the RTX 3060 and `qwen2.5:7b` returns `GPU_OK` at 100% GPU with the 6 GB low-VRAM overlay.

## Phase 11: Workspace Productivity and Portable Release Checks

- [x] Add explicit per-document `@` mentions with same-session validation and
  per-segment retrieval. Prevent mentions from bypassing an active file filter.
- [x] Reuse indexed files across local conversations by copying bounded Qdrant
  vector pages, avoiding another upload, OCR pass, and embedding run.
- [x] Add discoverable `/` prompt and mode actions, a first-run tour with skip
  and replay, and four persistent light/dark-compatible color palettes.
- [x] Fix the development proxy's IPv4/IPv6 ambiguity and add Windows, macOS,
  and Linux test jobs for backend and frontend checks.
- [x] Refresh bilingual setup and discoverability documentation.
- [x] Confirm the new cross-platform CI jobs on the GitHub remote after the
  local commits are authorized for push.

## Phase 12: Installable Local Workspace

- [x] Add a stable web manifest, project-owned install icons, and standalone
  presentation for the production workspace.
- [x] Generate a versioned service worker from build assets and cache only the
  public application shell; keep all API traffic on the network.
- [x] Provide an install action where the browser supports it and an explicit
  update action that waits for active work to finish.
- [x] Document offline limits and HTTPS requirements in both READMEs, and
  refresh repository-discovery guidance against the public repository metadata.
- [x] Test installability, offline shell loading, and API non-caching against
  both the production preview and the running Docker app.

## Phase 13: Workspace Guidance and Interaction Polish

- [x] Replace the PWA's opaque tile with a transparent, mask-safe version of
  the welcome emblem and test alpha transparency in the install icon.
- [x] Animate the document drawer in both interface directions, including its
  exit path and backdrop, while respecting reduced-motion settings.
- [x] Keep the active `@` or `/` suggestion visible during keyboard navigation
  and give the suggestion list a clear, contained scrollbar.
- [x] Add real keyboard shortcuts and operating-system-specific labels in
  Settings; verify Control and Command behavior in browser tests.
- [x] Expand the skippable and replayable tour to cover conversation history,
  documents, composer, answer modes, response branches and sources, model
  settings, privacy, local data controls, and installability.

## Phase 14: Release 1.0.0 (2026-10-08)

- [x] Stream answers token by token over Server-Sent Events, with numbered
  citations, a provenance badge, and suggested questions for new conversations.
- [x] Rebuild Persian PDF text in reading order, correct rotated and skewed
  scans, and normalize Persian spelling in indexed text and questions.
- [x] Chunk Word documents under their headings, detect duplicate uploads by
  content, and read legacy Windows-1256 and UTF-16 text files.
- [x] Fuse BM25 keyword search with vector search and rerank Hybrid answers
  with an Arabic-script cross-encoder; fit prompts to the model's context.
- [x] Roll back failed uploads, block DNS rebinding, and return stable error
  codes that the interface translates.
- [x] Store conversations in IndexedDB, add backup and restore, and add an
  end-to-end CI job with a retrieval quality gate.

## Phase 15: Release 1.1.0 (2026-10-19)

- [x] Make 27 `.env` settings changeable in the app without a restart; show
  each `.env` value, allow a reset, and show what "automatic" resolves to.
- [x] Cite tables and images inside Word and PowerPoint by number, show the
  cited image next to its source, and send a retrieved table to the model whole.
- [x] Search each part of a question that asks several things, and ask the
  model to answer every part.
- [x] Use the Ollama installed on the computer, with its models and GPU, from
  Docker; list installed models; stop thinking models from returning empty
  answers.
- [x] Support Google AI Studio (model prefix, reasoning removal, retries for
  5xx and 429) and report an out-of-credit API (402) clearly.
- [x] OCR images in parallel (96-image report: 121 s to 33 s parse) and read
  screenshots and tinted panels better.
- [x] Keep question parsing linear on hostile input (CodeQL regular-expression
  alerts) and run every backend test without skips or Docker.
- [x] Acceptance test on the project's own reports (52 questions, 244 images):
  44/52 Strict and 42/52 Hybrid with `gemini-flash-lite-latest`, up from 33 and
  30; 9/12 in both modes with local `gemma3:4b`.

## Phase 16: Defects to Fix

Found in a full review of the code, CI, and documentation on 2026-10-21.
Each item names where the problem is and what it breaks.

### Task 16.1: Release blockers
- [x] Publish 1.1.1. The only supported version (1.1.x) still ships Pillow
  12.3.0 with a critical advisory; the fix (Pillow 13.0.0) and the PowerPoint
  slide-number fix are only in `develop`.
- [x] Configure logging from `LOG_LEVEL` in `backend/main.py`. Nothing sets up
  a handler, so the request log in `api/middleware.py` and the operation logs
  in the use cases are dropped, and `LOG_LEVEL`/`ENVIRONMENT` have no effect.
- [x] Add `OLLAMA_DOCKER_BASE_URL=http://ollama:11434` to the README sections
  that run Ollama inside Docker (CPU, NVIDIA, AMD; both languages). Without it
  the app keeps calling the host Ollama from `.env.example`.

### Task 16.2: Backend correctness
- [x] BM25 cache race (`infrastructure/database/qdrant_repo.py`,
  `keyword_index.py`): writes invalidate the cache before they change Qdrant, so
  a query in that window caches the old corpus, including deleted documents.
  Invalidate again after the write; prune the per-session version map.
- [x] `/query/stream` reports a full query slot (`busy`) or an invalid mention
  as HTTP 200 plus an `error` event, because the slot and validation run inside
  the generator (`core/use_case/query/answer_query.py`). Check both before
  returning the `StreamingResponse`.
- [x] Strict evidence gate is skipped for any question containing «خلاصه»,
  «موضوع», «کلیات» or «چه نوع» (`DOCUMENT_OVERVIEW_PATTERN` in
  `core/strategies/strict_rag.py`). Match only whole-document questions.
- [x] The stored API key is sent to a new base URL when the user changes the
  host without entering a key (`infrastructure/llm/factory.py`). Reuse it only
  for the same scheme, host, and port.
- [x] Session routes (files, images, reuse, delete) are not gated on readiness
  and can build the repository before the embedding model is set, which probes
  the wrong vector size (`api/dependencies.py`, `api/routes.py`).
- [x] Hybrid context trimming ranks reranker scores and cosine scores
  together, so a top reranked chunk can be dropped for a weaker dense anchor
  (`core/strategies/hybrid_rag.py`, `core/service/context_budget.py`).
- [x] PowerPoint: a linked (not embedded) picture fails the whole deck, and
  text and pictures inside grouped shapes are not indexed
  (`infrastructure/parsers/document_parser.py`).
- [x] Word: content inside content controls (`w:sdt`) is not indexed.
- [x] OCR has no per-document deadline: one image can run eight Tesseract
  passes and scanned PDF pages run one after another, holding the only
  ingestion slot for a long time (`infrastructure/parsers/ocr.py`).
- [x] Catch `Image.DecompressionBombError`; an image that declares huge
  dimensions returns 500 instead of a notice.
- [x] Citation parsing counts math intervals such as `[1, 3]` as citations
  (`core/service/citations.py`); skip math and code spans.
- [x] Runtime settings: the file, batch, and request-size check runs outside
  the store lock, `os.environ` changes before the file is saved, and model
  rebuilds run outside the lock (`core/use_case/system/runtime_settings.py`,
  `infrastructure/runtime_settings.py`). Apply, validate, and save atomically.
- [x] Resetting `PARSRAG_CPU_THREADS` to automatic leaves the old thread count
  in PyTorch while Settings shows the default (`infrastructure/llm/factory.py`).
- [x] An invalid `STRICT_RAG_THRESHOLD` in `.env` makes every Strict query fail
  while Settings shows 0.75; parse it with a bounded helper.
- [x] The reranker download is retried on every query after a failure and has
  no network timeout (`infrastructure/llm/reranker.py`).
- [x] Retries stack: the OpenAI SDK retries inside ParsRAG's own status retries
  (`max_retries=1` plus `MODEL_API_MAX_RETRIES`). Let one layer retry.
- [x] The model endpoint is validated once; later DNS changes and HTTP
  redirects are not checked (`infrastructure/llm/endpoint_policy.py`). Disable
  redirects and check the address at connect time.
- [x] HTML table cells are joined without a separator (`<td>Name</td><td>Ali`
  becomes `NameAli`), and a UTF-8 file with one bad byte is decoded as cp1256
  garbage (`infrastructure/parsers/document_parser.py`).
- [x] `max_tokens` is ignored for Ollama titles and suggestions; pass
  `num_predict` instead.
- [x] A disconnected stream leaves the progress stage at "generating" for five
  minutes; set a final stage in `finally`.
- [x] Unify the Strict refusal text: `STRICT_REFUSAL_FA/EN` are unused and the
  gate and the prompt use different wording (`core/strategies/strict_rag.py`).
- [ ] The evaluation runner (`backend/tests/evaluation/run_pdf_evaluation.py`)
  skips Persian normalization, page bridges, and duplicate checks; run it
  through the real ingestion use case.

### Task 16.3: Frontend correctness
- [x] The composer accepts 30,000 characters but the API accepts 12,000; the
  error is generic and the long turn is resent as history, so the next
  questions fail too (`components/Composer.tsx`, `core/state.ts`,
  `services/api.ts`). Match the limit, map 422 errors, and mark the failed turn.
- [x] The math normalizer breaks links, `snake_case` words, and dollar amounts
  (`core/markdown.ts`): `[docs](…/my_page)` loses its link and "$5" loses its
  sign.
- [x] Unsaved server-setting edits are reset whenever the app re-renders, for
  example on the 30-second health check (`components/SettingsModal.tsx`,
  `components/ServerSettings.tsx`).
- [x] Editing a prompt that never got an answer attaches the new answer to a
  later question (`App.tsx`, `core/state.ts`).
- [x] A save that fell back to `localStorage` is discarded on the next load in
  favour of the older IndexedDB copy, and two open tabs overwrite each other
  (`hooks/usePersistentWorkspace.ts`, `core/storage.ts`).
- [x] The 330-second stream timeout ignores the server's answer timeout (up to
  600 s); derive it from the runtime settings or send SSE heartbeats.
- [x] Keyboard shortcuts compare `event.key`, so they do not fire with the
  Persian keyboard layout; compare `event.code` (`core/shortcuts.ts`).
- [x] The Strict threshold in browser settings (`strictThreshold`) is never sent
  to the server; remove it or send it.
- [x] The Vite development proxy has no `/settings` route, so runtime settings
  fail under `npm run dev` (`vite.config.ts`).
- [x] Deleting a conversation or clearing data fails while the backend is
  offline, even for conversations without documents.
- [x] Backup import drops the saved preferences and shows imported documents as
  indexed although they are not on this server (`core/workspaceTransfer.ts`).
- [x] A timeout or dropped connection discards text that already streamed;
  keep it as Stop does.
- [x] Smaller issues: clearing a number field switches it to automatic;
  upload limits are stale after a settings change until the next health check;
  answer-version arrows point the wrong way in English; Strict mode with every
  document unticked returns "no evidence" instead of asking to select one; an
  unanswered question has no retry; starter cards change the chosen mode;
  dragging out of a dialog closes it; the rename field is not focused.
- [x] Add interface messages for the backend codes `not_found`, `conflict`,
  `upstream_unavailable`, `invalid_session`, `no_file`, `untrusted_host`,
  `service_error`, and `request_failed`, and pass codes through on the reuse,
  delete, and model-settings paths (`i18n/errors.ts`).

### Task 16.4: Configuration and documentation
- [x] Use one default model everywhere: `gemma3:12b` in `compose.yaml`,
  `factory.py`, and `core/state.ts`, but `qwen2.5:7b` in `.env.example` and the
  README. The quick start also pulls a 7B model while recommending 3-4B.
- [x] After the startup retries give up, readiness stays `failed` and the
  container is never restarted (`main.py`, `Dockerfile` healthcheck). Exit
  non-zero or keep retrying with a capped backoff.
- [x] README settings table: API requests are retried up to
  `MODEL_API_MAX_RETRIES` (default 4), not once, and the ⚙ marker misses most
  runtime settings. Generate the table from `RUNTIME_SETTINGS`.
- [x] CHANGELOG 1.0.0 does not record that the Strict threshold moved from 0.80
  to 0.75.
- [x] `CONTRIBUTING.md` points to `.agents/AGENTS.md`, which is not in the
  repository; `EMBED_QUERY_PREFIX` and `EMBED_PASSAGE_PREFIX` (DATA.md) are not
  passed through `compose.yaml`.
- [ ] Bring the ADRs in line with the project: `.context/03` (Poetry,
  `docker-compose.yml`, Testcontainers, Ragas, JSON logs), `.context/04` (GitHub
  Flow, `staging`, image publishing), the two files numbered 07, React 18 in ADR
  06, and the missing `Reranker`, `RuntimeSettingsStore`, and
  `SuggestQuestions` in `ARCHITECTURE.md` and `docs/architecture/use-cases.md`.

## Phase 17: Improvements

### Task 17.1: Retrieval quality
- [ ] Read images with a vision model during indexing (see Task 19.1); OCR
  errors in small screenshots and near-identical screenshots cause most of the
  remaining wrong answers in the acceptance test.
- [ ] Add MMR or a similar diversity step so near-duplicate chunks do not fill
  the context.
- [ ] Re-measure the Strict threshold on a labelled set: top scores of relevant
  and off-topic questions overlap (medians 0.806 and 0.807).
- [ ] Evaluate larger multilingual embedding models (`multilingual-e5-large`,
  `bge-m3`) against `multilingual-e5-base` on Persian questions.
- [ ] Return a distinct outcome for an empty model answer instead of
  `answered` with no text.

### Task 17.2: Performance
- [ ] Embed each question once per request instead of once per search call;
  a multi-part question over ten files can trigger about 50 embeddings.
- [ ] List a session's files with Qdrant facets instead of scrolling every
  chunk, at least twice per question.
- [ ] Give BM25 an inverted index instead of scanning every chunk per query.
- [x] OCR scanned PDF pages in parallel, as Office images already are, and skip
  the deskew search when the first reading is confident.
- [ ] Frontend: memoize messages and markdown rendering, keep the draft out of
  the sessions state, and window long conversations; typing and streaming slow
  down in long chats.

### Task 17.3: Ingestion
- [x] Parse CSV and TSV as tables so they get row records and whole-table
  answers.
- [x] Split plain-text files into line or heading sections so citations point
  somewhere more precise than "section 1".
- [x] Index PowerPoint speaker notes.
- [x] Keep an image preview for standalone image uploads, as for Word and
  PowerPoint images.

### Task 17.4: Interface
- [ ] Stop a streaming answer with Escape; cancel and retry uploads; add a copy
  button to code blocks.
- [ ] Show the offline hint, poll faster while the backend is preparing, and
  check for new service-worker versions while the app stays open.
- [ ] Call `navigator.storage.persist()`, flush pending saves on `pagehide`,
  and keep a copy of stored data that fails to parse instead of overwriting it.
- [ ] Offer export and reset from the error screen, so stored data that breaks
  rendering does not crash every reload.
- [ ] Remove dead code (`progressRef`, `revealingMessageId`, unused API calls,
  `selectedModel`, unused strings) and fix the smaller accessibility gaps in
  version navigation, settings tabs, and the mobile sidebar.

### Task 17.5: CI, packaging, and supply chain
- [ ] Add an explicit CodeQL workflow that runs on every pull request to
  `develop`; today CodeQL is GitHub's default setup and skips most of them, so
  its alerts appeared only on the 1.1.0 release pull request.
- [ ] Generate a full, hashed lock file (for example with `uv` or
  `pip-compile`) so Dependabot can update Python dependencies and builds are
  reproducible; audit the packages inside the image.
- [ ] Add the `docker-compose` ecosystem to Dependabot (Qdrant and Ollama
  images) and pin `ollama/ollama:rocm` to a version.
- [ ] Install the same CPU PyTorch in CI as in the image; split PyTorch into
  its own Docker layer and use BuildKit pip caches.
- [ ] Turn `.dockerignore` into an allowlist; local folders (`demo-video`,
  `graphify-out`, `defense`) add about 95 MB to the build context.
- [ ] Add `concurrency` and `timeout-minutes` to workflows, cache image builds,
  and build the image once per push.
- [ ] Start the built container in CI and request `/health/live` and `/`;
  build the CUDA and ROCm variants.
- [ ] Split the release job into a read-only verify job and a write-scoped
  publish job; pin every action by commit SHA; check `backend/main.py`,
  `CITATION.cff`, and the CHANGELOG section in the release version check.
- [ ] Add `cap_drop`, `no-new-privileges`, and `pids_limit` to the Qdrant and
  Ollama services.
- [ ] Add a test that compares Compose defaults, `.env.example`, and
  `RUNTIME_SETTINGS`; replace wall-clock assertions in the regular-expression
  tests with growth checks; add an SSE disconnect test through the route.
- [ ] Add a pre-commit configuration, ESLint, and frontend coverage.
- [ ] Add a GitHub ruleset that allows only squash merges into `main`, so each
  release stays one commit.
- [ ] Refresh the landing-site screenshots (`ParsRAG-Landing`,
  `assets/img/shots/wall`) on each release.

## Phase 18: New Features

- [ ] Vision-model image descriptions during indexing, optional and
  configurable like OCR (Task 19.1).
- [ ] Legacy Office formats (`.doc`, `.ppt`) and spreadsheets (`.xlsx`).
- [ ] Background indexing queue with progress, so large documents do not hold
  an HTTP request and the single ingestion slot.
- [ ] A shared, persistent document library next to per-conversation documents,
  as described in the original PRD (Section 3.2).
- [ ] Answer export (Markdown or PDF) with its sources, and a link that opens a
  cited page or image in the original document.
- [ ] Conversation search that shows the matching snippet and jumps to it.
- [ ] In-app evaluation: run a labelled question set against the current model
  and settings and show the results.

## Phase 19: Long-Term Plans

### Task 19.1: Vision model for images
- [ ] Describe each image with a vision model (local through Ollama, for
  example `gemma3:4b`, or Gemini through an API) in addition to OCR, and store
  the description with the OCR text.
- [ ] Make it optional, since it slows indexing, and re-run the 52-question
  acceptance set to measure the effect on the 19 image questions.

### Task 19.2: Multi-user deployment
- [ ] Authentication, per-user sessions and documents, and roles, so the app
  can run on a shared server instead of only on one workstation.
- [ ] Move BM25 into Qdrant sparse vectors so keyword search scales beyond the
  in-memory per-session index.

### Task 19.3: Evaluation
- [ ] Measure faithfulness and answer relevance with Ragas or TruLens on a
  larger, standard Persian question set, alongside the current deterministic
  fact-coverage scoring.

### Task 19.4: Distribution
- [ ] Publish signed images with SBOM and provenance to a registry from the
  release workflow, so users do not have to build the PyTorch layer locally
  (check the license terms on redistribution first).
- [ ] Validate a current ROCm PyTorch for the AMD overlay or mark it
  experimental, and give it its own constraints.

### Task 19.5: Knowledge graph
- [ ] GraphRAG for questions about relations between entities across
  documents, reserved for after Phase 1 in the original PRD.
