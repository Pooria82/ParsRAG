# 05. Implementation Roadmap: ParsRAG

## Overview
This document serves as the self-executable, atomic roadmap for building the ParsRAG system from scratch. It strictly adheres to the architectural boundaries defined in the `.context/` ADRs. The tasks are sequenced using Domain-Driven Design (DDD) principles: foundation first, interfaces second, concrete implementations third, API fourth, and UI/Docker last.

---

## Phase 1: Project Initialization & Configuration

### Task 1.1: Dependency & Environment Setup
**Description:** Initialize the Python environment and install core dependencies.
**Actionable Steps:**
- [ ] Initialize the project (e.g., using `poetry init` or `requirements.txt`).
- [ ] Install core backend libraries: `fastapi`, `uvicorn`, `llama-index`, `qdrant-client`, `pymupdf`.
- [ ] Install frontend library: `chainlit`.
- [ ] Install dev dependencies: `ruff`, `mypy`, `pytest`, `pytest-asyncio`.
- [ ] Create `.env.example` defining required environment variables (e.g., `QDRANT_HOST`, `OLLAMA_BASE_URL`).

### Task 1.2: Directory Structure & Git Ignore
**Description:** Scaffold the exact directory tree defined in `03_Tech_Standards.md`.
**Actionable Steps:**
- [ ] Create the `.gitignore` file exactly as specified in `04_Git_and_CI.md`.
- [ ] Create `backend/api/`, `backend/core/models/`, `backend/core/strategies/`, `backend/core/interfaces/`.
- [ ] Create `backend/infrastructure/database/`, `backend/infrastructure/llm/`, `backend/infrastructure/parsers/`.
- [ ] Create `frontend/` and `tests/` directories.
- [ ] Add `__init__.py` files where necessary to define Python modules.

### Checkpoint: Phase 1
- [ ] Run `ruff check .` to ensure zero errors in the empty structure.
- [ ] Confirm `.gitignore` protects against accidental large file commits.

---

## Phase 2: Core Domain Models & Interfaces

### Task 2.1: Domain Models (Pydantic)
**Description:** Define the strict data contracts that cross system boundaries.
**Actionable Steps:**
- [ ] Create `backend/core/models/domain.py`.
- [ ] Implement `DocumentIngestionRequest` (file data, session ID).
- [ ] Implement `QueryRequest` (prompt, chat history, mode).
- [ ] Implement `ExtractedNode` (text, metadata, score) and `QueryResponse`.

### Task 2.2: Abstract Base Classes (ABCs)
**Description:** Define the interfaces to adhere to the Open-Closed Principle.
**Actionable Steps:**
- [ ] Create `backend/core/interfaces/repository.py` and define `AbstractDocumentRepository` with `save_nodes`, `similarity_search`, `delete_session`.
- [ ] Create `backend/core/interfaces/strategy.py` and define `AbstractQueryStrategy` with an `execute(request: QueryRequest)` method.

### Checkpoint: Phase 2
- [ ] Run `mypy backend/` to ensure the base schemas and interfaces are 100% type-safe.

---

## Phase 3: Infrastructure Implementations (Data & Logic Layers)

### Task 3.1: Qdrant Repository Implementation
**Description:** Implement the concrete database layer.
**Actionable Steps:**
- [ ] Create `backend/infrastructure/database/qdrant_repo.py`.
- [ ] Implement `QdrantRepository` inheriting from `AbstractDocumentRepository`.
- [ ] Add logic to filter by global vs. session-scoped namespaces using Qdrant's payload filtering.

### Task 3.2: Document Parsing & Chunking
**Description:** Build the ingestion pipeline for Persian RTL text.
**Actionable Steps:**
- [ ] Create `backend/infrastructure/parsers/pdf_parser.py` using `PyMuPDF`.
- [ ] Implement logic to reject scanned PDFs if 0 selectable text is found.
- [ ] Create `backend/infrastructure/parsers/chunker.py` using LlamaIndex `SentenceSplitter` configured for Persian (500-1000 char size, 150 overlap).

### Task 3.3: LLM & Embeddings Factory
**Description:** Configure Ollama and the multilingual embedding model via LlamaIndex.
**Actionable Steps:**
- [ ] Create `backend/infrastructure/llm/factory.py`.
- [ ] Instantiate the LlamaIndex `Settings.llm` pointing to the local Ollama Qwen 2.5 instance.
- [ ] Instantiate `Settings.embed_model` pointing to `intfloat/multilingual-e5-base`.

### Checkpoint: Phase 3
- [ ] Write a basic unit test in `tests/` to mock Qdrant and verify the chunking logic outputs valid `ExtractedNode` models.

---

## Phase 4: Query Routing & Strategies

### Task 4.1: Condense Question Pipeline
**Description:** Build the conversational memory logic.
**Actionable Steps:**
- [ ] Create `backend/core/condenser.py`.
- [ ] Implement logic to inject chat history and the current query into a LlamaIndex prompt to rewrite pronouns into a standalone question.

### Task 4.2: Concrete RAG Strategies
**Description:** Implement the three distinct execution modes.
**Actionable Steps:**
- [ ] Create `backend/core/strategies/strict_rag.py`. Implement logic to halt if retrieval similarity is too low (0% hallucination target).
- [ ] Create `backend/core/strategies/llm_only.py`. Bypass Qdrant entirely.
- [ ] Create `backend/core/strategies/hybrid_rag.py`. Retrieve from Qdrant, pass to FlashRank reranker, then to LLM.

---

## Phase 5: FastAPI Backend & Endpoints

### Task 5.1: Dependency Injection Setup
**Description:** Wire up the interfaces to concrete implementations for FastAPI.
**Actionable Steps:**
- [ ] Create `backend/api/dependencies.py`.
- [ ] Provide functions `get_document_repository()` and `get_query_strategy(mode)`.

### Task 5.2: API Routes & Exception Handling
**Description:** Expose the REST API and handle errors gracefully.
**Actionable Steps:**
- [ ] Create `backend/api/routes.py` with `/ingest` and `/query` endpoints.
- [ ] Create `backend/main.py` initializing the FastAPI app.
- [ ] Add a global exception handler in `main.py` to intercept timeouts and OOM errors, returning a clean 500 JSON response.

### Checkpoint: Phase 5
- [ ] Run `pytest` to ensure all backend routing logic passes.
- [ ] Spin up `uvicorn backend.main:app` locally and hit `/docs` to verify OpenAPI schema.

---

## Phase 6: Frontend Integration (Chainlit)

### Task 6.1: Chainlit Application
**Description:** Build the user-facing chat UI.
**Actionable Steps:**
- [ ] Create `frontend/app.py`.
- [ ] Implement `on_chat_start` to configure radio buttons for the 3 RAG modes.
- [ ] Implement file upload handlers in the chat interface.
- [ ] Implement the `on_message` hook to send user messages to the FastAPI `/query` endpoint and stream the response back.

---

## Phase 7: Dockerization & Final Orchestration

### Task 7.1: Dockerfiles
**Description:** Containerize the microservices.
**Actionable Steps:**
- [ ] Create `backend/Dockerfile` optimizing for Python (multi-stage build).
- [ ] Create `frontend/Dockerfile` for Chainlit.

### Task 7.2: Docker Compose
**Description:** Orchestrate the entire system.
**Actionable Steps:**
- [ ] Create `docker-compose.yml` in the root directory.
- [ ] Define `ui`, `api`, `qdrant`, and `ollama` services.
- [ ] Configure networking and volume mounts (excluding qdrant_storage from git).

### Checkpoint: Final
- [ ] Run `docker-compose up --build`.
- [ ] Upload a Persian PDF and ask a follow-up question. Verify response quality.
