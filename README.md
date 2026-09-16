# ParsRAG

**An Offline, Privacy-First, RTL-Optimized Persian AI Assistant.**

ParsRAG is an enterprise-grade Retrieval-Augmented Generation (RAG) system built exclusively for the Persian language. Designed for environments with strict data confidentiality (educational, research, and organizational), ParsRAG operates **100% locally**. It parses Persian PDFs with high fidelity, executes complex semantic retrieval, and reasons over local documents with zero data leakage to the internet.

---

## Key Features

* **3 Intelligent RAG Modes:**
  * **Strict RAG:** Answers solely based on ingested documents to prevent hallucination.
  * **Hybrid RAG:** Combines retrieved document chunks with the LLM's inherent reasoning for comprehensive answers.
  * **LLM-Only:** Bypasses the vector DB to act as a general-knowledge offline chatbot.
* **Flawless RTL Extraction:** Utilizes PyMuPDF to extract right-to-left Persian text from digital PDFs while preserving structural integrity.
* **Conversational Memory:** Employs a fast "Condense Question" pipeline to accurately resolve pronouns in follow-up queries.
* **100% Air-gapped & Offline:** Powered by Ollama (Qwen 2.5) running locally. No external APIs or cloud services required.

## Technology Stack

ParsRAG is built using a modern, loosely-coupled microservices architecture:

* **UI:** React 18, TypeScript and Vite (bilingual RTL/LTR conversation workspace)
* **API:** [FastAPI](https://fastapi.tiangolo.com/) (Robust, typed backend)
* **RAG Orchestrator:** [LlamaIndex](https://www.llamaindex.ai/) (Advanced chunking and semantic routing)
* **Vector Database:** [Qdrant](https://qdrant.tech/) (High-performance, Rust-based vector search)
* **LLM Engine:** [Ollama](https://ollama.com/) (Serving Qwen 2.5 locally)
* **Parser:** PyMuPDF
* **Infrastructure:** Docker & Docker Compose

## Repository Structure

```text
ParsRAG/
├── .context/                  # Architecture Decision Records (ADRs) and PRDs
├── backend/                   # FastAPI API, LlamaIndex Core, and Infrastructure
├── frontend/                  # React UI, local font and brand assets
├── tests/                     # Pytest suite
└── docker-compose.yml         # Container orchestration
```

## Quick Start

1. **Configure the local environment:**
   ```bash
   cp .env.example .env
   ```
2. **Install and build the frontend:**
   ```bash
   cd frontend
   npm install
   npm run build
   ```
3. **Start FastAPI from the repository root:**
   ```bash
   .venv/Scripts/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
   ```
4. Open `http://127.0.0.1:8000`. FastAPI serves the production frontend build and the API from the same local origin.

For frontend hot reload, run `npm run dev` inside `frontend`. The interface validates persisted state, keeps conversations in the browser, and accepts only local backend endpoints.

## Verification

```bash
cd frontend
npm test
npm run build

cd ..
.venv/Scripts/python -m pytest backend/tests -q
.venv/Scripts/python -m ruff check backend
.venv/Scripts/python -m mypy --strict backend
```

The visual identity, color tokens, motion rules and SVG usage are documented in [`frontend/BRAND.md`](frontend/BRAND.md).

## Architecture & ADRs

All foundational decisions, Domain-Driven Design (DDD) specifications, and GoF patterns (Strategy, Factory, Repository) are strictly documented in the `.context/` directory. If you are contributing to this project, please review these files carefully before submitting a PR.

## Contributing

We follow a strict **GitHub Flow** strategy and enforce **Conventional Commits**. Please refer to `.context/04_Git_and_CI.md` for branch naming rules, CI/CD pipeline requirements, and PR guidelines.
