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
- [ ] Start the optional Ollama profile and repeat live model checks when model validation is requested; this run intentionally excludes the previously completed model evaluation.

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
- [x] Propagate cancellation where the active model adapter supports it; otherwise label the action as stopping local display and prevent stale responses.
- [x] Add structured request logging with correlation IDs while redacting prompts, document text, and credentials.

### Task 10.6: Architecture & Maintainability
**Description:** Remove duplicate contracts and align the implementation with repository coding rules.
**Actionable Steps:**
- [x] Consolidate the duplicate async/sync query strategy interfaces into one contract and remove unused domain types.
- [x] Split oversized frontend orchestration/state modules where responsibilities can be isolated without prop proliferation.
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
- [x] Add an open-source license, security policy, contribution guide, code of conduct, changelog, PR template, and issue templates.
- [ ] Replace documentation promises that are not implemented and publish reproducible, anonymized evaluation evidence for quantitative claims. (Claims were corrected and an anonymized limitations report was published; a reproducible live report awaits the separately requested model-evaluation run.)
- [x] Document hardware, storage, first-start downloads, offline provisioning, API data flow, and source-only versus container installation.
- [ ] Merge `develop` into protected `main` through CI, configure the GitHub remote, and create the first pre-1.0 semantic version tag.

### Checkpoint: Phase 10
- [ ] Run all backend, frontend, coverage, browser, Compose, container, and documentation checks from a clean checkout.
- [ ] Verify local Ollama and a mock private OpenAI-compatible endpoint without sending project data to the public internet.
- [ ] Verify remote API disclosure, optional-key behavior, validated connection failure, and configuration restart behavior.
- [ ] Verify forged and oversized uploads, saturation controls, complete data deletion, Qdrant pagination, and embedding-schema mismatch handling.
- [ ] Confirm no secrets or private test documents exist in the tracked tree or Git history before creating the public remote.
