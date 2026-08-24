# Technical Standards & Code Quality Guidelines

## 1. Code Quality & Linting
To maintain a FAANG-grade, highly readable, and uniform codebase, all Python code must adhere to strict formatting and linting rules before any commit is accepted.
- **Formatter:** `ruff format`. We rely on Ruff's blazing-fast Rust-based formatter to enforce a strict 88-character line limit (compatible with Black).
- **Linter:** `ruff check`. We replace Flake8, isort, and Pylint entirely with Ruff for massive speed improvements.
- **Rules:**
  - Import sorting is enforced automatically.
  - No unused imports or variables (enforced as errors).
  - Cyclomatic complexity must remain below 10 for any given function/method.

## 2. Type Hinting & Static Analysis
ParsRAG is treated as a strongly-typed project. Dynamic typing is minimized to prevent runtime bugs.
- **Tool:** `mypy` configured in `--strict` mode.
- **Strictness Level:** 100% type hint coverage is mandatory for all function signatures (arguments and return types) and class attributes.
- **Rules:**
  - `Any` is strictly prohibited unless interacting with an un-typed third-party library (and must be justified with an inline comment).
  - Pydantic V2 is used for all data validation at system boundaries (API endpoints, database serialization).

## 3. Documentation Standards
Code explains *what*; documentation explains *why*.
- **Docstrings:** We adhere to the **Google Python Style Guide** for docstrings. Every class, module, and public method must include a docstring detailing its purpose, `Args:`, `Returns:`, and `Raises:`.
- **Inline Comments:** Used sparingly and exclusively to explain complex business logic, algorithmic choices, or non-obvious workarounds. 
- **ADRs (Architecture Decision Records):** Any significant architectural shift must be documented in the `.context/` directory before implementation.

## 4. Testing Strategy
Given the non-deterministic nature of LLMs, testing a RAG pipeline requires specialized approaches.
- **Framework:** `pytest` and `pytest-asyncio` for all asynchronous endpoints.
- **Coverage Expectation:** Minimum **85% global test coverage**, with 100% coverage on core domain models, routers, and strategy classes.
- **RAG/LLM Testing Approach:**
  - **Unit Tests:** Mock the LLM and Qdrant responses using `unittest.mock`. Test the deterministic parts: routing logic, chunking algorithms, and prompt formatting. Ensure assertions validate the strict Pydantic `QueryResponse` structures, not just raw strings.
  - **Integration Tests:** Use `Testcontainers` (or local docker-compose spin-ups) to test the actual FastAPI -> Qdrant connection without an LLM.
  - **LLM Evaluation:** For end-to-end RAG testing, use an evaluation framework like `Ragas` or `TruLens` in a separate staging CI pipeline to measure *Faithfulness* (no hallucination) and *Answer Relevance*.

## 5. Project Directory Structure
Based on our microservices architecture, the repository follows a strict Domain-Driven Design (DDD) layout:

```text
ParsRAG/
├── .context/                  # Architecture Decision Records (ADRs) and PRDs
├── backend/                   # FastAPI & LlamaIndex Core
│   ├── api/                   # REST endpoints and WebSockets
│   │   ├── dependencies.py    # FastAPI Depends() injections
│   │   └── routes.py          # API route definitions
│   ├── core/                  # Business Logic (Framework Agnostic)
│   │   ├── interfaces/        # Abstract Base Classes (Strategy & Repository)
│   │   ├── models/            # Pydantic V2 domain models
│   │   ├── strategies/        # RAG Query Strategies (Strict, Hybrid, LLM-Only)
│   │   ├── condenser.py       # Conversational memory re-writer pipeline
│   │   └── exceptions.py      # Centralized domain errors (ParsRAGError)
│   ├── infrastructure/        # External I/O (LlamaIndex config, Qdrant, PyMuPDF)
│   │   ├── database/          # Qdrant repository implementations
│   │   ├── llm/               # Ollama factory (Prompt templates are encapsulated in strategies)
│   │   └── parsers/           # Document ingestion and PDF parsing
│   ├── tests/                 # Backend pytest suite
│   └── main.py                # FastAPI application entrypoint
├── frontend/                  # Chainlit UI
│   ├── app.py                 # Chainlit async event loop and UI layout
│   ├── chainlit.md            # Chainlit welcome screen markdown
│   └── public/                # Static assets (logos, custom CSS)
├── docker-compose.yml         # Defines backend, frontend, qdrant, and ollama
├── pyproject.toml             # Poetry/Ruff/MyPy configurations
└── README.md
```

## 6. Error Handling & Logging Standards
Errors must never leak stack traces to the user and must not crash the application.
- **Global Exception Handling:** FastAPI will utilize a centralized exception handler to catch unhandled exceptions, returning a clean, standard HTTP 500 JSON response.
- **Custom Domain Exceptions:** Create specific exceptions inherited from a base `ParsRAGError` (e.g., `VectorDBConnectionError`, `LLMInferenceTimeoutError`, `EmptyDocumentError`).
- **Logging:**
  - Use the built-in Python `logging` module configured with a JSON formatter for production (for easy ingestion into ELK/Datadog) and colored console output for development.
  - **Traceability:** Every API request must generate a unique `correlation_id` passed through the entire LlamaIndex pipeline and logged alongside every INFO/ERROR message.

## 7. Security Practices
Security must be implemented defensively at every system boundary.
- **Input Validation:** All incoming API requests and uploaded files MUST be rigorously validated using Pydantic before processing.
- **Path Traversal Prevention:** Uploaded filenames must be sanitized (`werkzeug.utils.secure_filename` or similar) to prevent path traversal attacks.
- **Zero Leakage:** The system is air-gapped. Never transmit data to external APIs (OpenAI, Anthropic) or telemetry services.
- **Prompt Injection:** Employ defensive system prompts to mitigate user prompt injection attempting to leak organizational documents out of context.

## 8. Database Optimization & Scalability
While a traditional SQL ORM isn't applicable to a vector database, Qdrant relies on strict Pydantic schemas acting as our data modeling layer.
- **Data Modeling (ORM-like validation):** Pydantic models define the schema for vector payloads. No unstructured dictionaries should be directly written to the database.
- **Scalability & Indexing:** 
  - Ensure Qdrant payload fields (e.g., `session_id`) are explicitly indexed (`create_payload_index`) to allow fast filtering.
- **Optimization:** Use batched upserts instead of single-point inserts to maximize throughput during document ingestion. Maintain connection pooling via `qdrant-client` for high concurrency.
