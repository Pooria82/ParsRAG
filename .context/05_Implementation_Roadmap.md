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
- [x] Install frontend library: `chainlit`.
- [x] Install dev dependencies: `ruff`, `mypy`, `pytest`, `pytest-asyncio`.
- [x] Create `.env.example` defining required environment variables (e.g., `QDRANT_HOST`, `OLLAMA_BASE_URL`).

### Task 1.2: Directory Structure & Git Ignore
**Description:** Scaffold the exact directory tree defined in `03_Tech_Standards.md`.
**Actionable Steps:**
- [x] Create the `.gitignore` file exactly as specified in `04_Git_and_CI.md`.
- [x] Create `backend/api/`, `backend/core/models/`, `backend/core/strategies/`, `backend/core/interfaces/`.
- [x] Create `backend/infrastructure/database/`, `backend/infrastructure/llm/`, `backend/infrastructure/parsers/`.
- [x] Create `frontend/` and `tests/` directories.
- [x] Add `__init__.py` files where necessary to define Python modules.

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
**Description:** Build the ingestion pipeline for Persian RTL text.
**Actionable Steps:**
- [x] Create `backend/infrastructure/parsers/pdf_parser.py` using `PyMuPDF`.
- [x] Implement logic to reject scanned PDFs if 0 selectable text is found.
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
- [ ] **VRAM Profiling:** Spin up `qwen2.5:7b` via Ollama and monitor VRAM usage during peak inference. Ensure it stays within the 6GB limit without swapping to CPU RAM.
- [ ] **Qdrant Indexing Audit:** Verify that Qdrant collections are created with the exact correct vector dimensions (from the HuggingFace embedding model) and that the `session_id` payload index is successfully created for O(1) filtering.
- [ ] **Connection Resilience:** Simulate a database timeout or Ollama crash during a request and verify the backend fails gracefully (intercepted by `ParsRAGError`).

### Task 6.2: Persian Data Ingestion Rigor (Parsing & Chunking)
**Description:** Ensure the ingestion pipeline handles complex Persian (RTL) text flawlessly.
**Actionable Steps:**
- [x] **Encoding & RTL Validation:** Upload a PDF with complex Persian text (containing Zero-Width Non-Joiners / نیم‌فاصله) and extract the exact chunks to verify encoding isn't mangled. (Successfully verified using DOCX/PDF parsers).
- [ ] **Chunk Boundary Inspection:** Extract overlapping chunks and manually inspect them to guarantee the LlamaIndex `SentenceSplitter` is respecting Persian sentence boundaries (periods, question marks) rather than slicing mid-word.
- [ ] **Malformed Payloads:** Send corrupted PDFs, pure image PDFs (scans), and excessively large PDFs (>50MB) to `/ingest`. Verify the exact HTTP 400 behavior and error messaging.

### Task 6.3: Retrieval & Re-ranking Precision (RAG Core)
**Description:** Validate the mathematical boundaries of the RAG strategies.
**Actionable Steps:**
- [ ] **FlashRank Validation:** In `HYBRID` mode, track the node scores before and after FlashRank. Confirm that FlashRank correctly elevates the most semantically relevant Persian nodes to the top.
- [ ] **Strict Mode Thresholding:** In `STRICT` mode, deliberately ask an out-of-domain question. Verify the vector similarity score falls below the accepted threshold and the pipeline short-circuits to prevent hallucination.
- [ ] **Conversational Memory (Anaphora):** Test the `CondenseQuestionPipeline` with a 4-turn conversation containing complex Persian pronouns (e.g., "او چه گفت؟", "آن کجا بود؟"). Verify the LLM successfully rewrites the prompt into a standalone question.

### Task 6.4: API Security, Concurrency, and Load
**Description:** Guarantee the FastAPI layer acts as an impenetrable shield.
**Actionable Steps:**
- [ ] **Zero-Leakage Audit:** Deliberately trigger internal `KeyError`s and division-by-zero exceptions inside the strategy layers. Assert that the `POST /query` endpoint returns a sterile HTTP 500 JSON without leaking a single line of stack trace.
- [ ] **Input Sanitization:** Attempt Path Traversal or NoSQL injection payloads inside the `session_id` parameter to ensure Pydantic V2 rigorously sanitizes inputs.
- [ ] **Concurrency Test:** Send 10 simultaneous asynchronous requests to `/query` to observe how the FastAPI threadpool and Qdrant/Ollama handle concurrent locks.

### Checkpoint: Phase 6 (Final Sign-off)
- [x] **Test Coverage:** All 23 tests pass consistently without race conditions.
- [x] **Architectural Compliance:** 100% adherence to DDD, with no leakage of Qdrant logic into the API routes (Dependency Injection successfully applied to Strategies).
- [ ] **Sign-off:** Achieving 99.99% confidence across reliability, speed, and accuracy. System is declared production-ready for UI integration.

---

## Phase 7: Frontend Integration (Chainlit)

### Task 7.1: Chainlit Application
**Description:** Build the user-facing chat UI.
**Actionable Steps:**
- [ ] Create `frontend/app.py`.
- [ ] Implement `on_chat_start` to configure radio buttons for the 3 RAG modes.
- [ ] Implement file upload handlers in the chat interface.
- [ ] Implement the `on_message` hook to send user messages to the FastAPI `/query` endpoint and stream the response back.

---

## Phase 8: Dockerization & Final Orchestration

### Task 8.1: Dockerfiles
**Description:** Containerize the microservices.
**Actionable Steps:**
- [ ] Create `backend/Dockerfile` optimizing for Python (multi-stage build).
- [ ] Create `frontend/Dockerfile` for Chainlit.

### Task 8.2: Docker Compose
**Description:** Orchestrate the entire system.
**Actionable Steps:**
- [ ] Create `docker-compose.yml` in the root directory.
- [ ] Define `ui`, `api`, `qdrant`, and `ollama` services.
- [ ] Configure networking and volume mounts (excluding qdrant_storage from git).

### Checkpoint: Final
- [ ] Run `docker-compose up --build`.
- [ ] Upload a Persian PDF and ask a follow-up question. Verify response quality.
