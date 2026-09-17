# ParsRAG

**An Offline-First, Privacy-Aware, RTL-Optimized Persian AI Assistant.**

ParsRAG is a single-user Retrieval-Augmented Generation (RAG) workspace for Persian and English documents. Parsing, embeddings, and vector storage stay on the workstation. Generation can stay local through Ollama, use a private OpenAI-compatible service on a corporate network, or use an external OpenAI-compatible API when local hardware is unavailable.

---

## Key Features

* **3 Intelligent RAG Modes:**
  * **Strict RAG:** Answers only from retrieved document context and refuses when the configured evidence threshold is not met.
  * **Hybrid RAG:** Combines retrieved document chunks with the LLM's inherent reasoning for comprehensive answers.
  * **LLM-Only:** Bypasses the vector DB to act as a general-knowledge offline chatbot.
* **Flawless RTL Extraction:** Utilizes PyMuPDF to extract right-to-left Persian text from digital PDFs while preserving structural integrity.
* **Conversational Memory:** Employs a fast "Condense Question" pipeline to accurately resolve pronouns in follow-up queries.
* **Explicit trust boundary:** Ollama supports fully local generation. API mode clearly warns that prompts and retrieved context are sent to the configured endpoint.

## Technology Stack

ParsRAG is built using a modern, loosely-coupled microservices architecture:

* **UI:** React 18, TypeScript and Vite (bilingual RTL/LTR conversation workspace)
* **API:** [FastAPI](https://fastapi.tiangolo.com/) (Robust, typed backend)
* **RAG Orchestrator:** [LlamaIndex](https://www.llamaindex.ai/) (Advanced chunking and semantic routing)
* **Vector Database:** [Qdrant](https://qdrant.tech/) (High-performance, Rust-based vector search)
* **LLM Engine:** [Ollama](https://ollama.com/) or an OpenAI-compatible API
* **Parser:** PyMuPDF
* **Infrastructure:** Docker & Docker Compose

## Repository Structure

```text
ParsRAG/
├── .context/                  # Architecture Decision Records (ADRs) and PRDs
├── backend/                   # FastAPI API, LlamaIndex Core, and Infrastructure
├── frontend/                  # React UI, local font and brand assets
├── Dockerfile                 # Multi-stage React and FastAPI production image
└── compose.yaml               # App, Qdrant, Ollama, and persistent volumes
```

## Local Development

1. **Create a private local configuration:**
   ```bash
   cp .env.example .env
   ```
   Select `LLM_PROVIDER=ollama` for a local model. For API mode set
   `LLM_PROVIDER=api`, `MODEL_API_BASE_URL`, `LLM_MODEL_NAME`, and optionally
   `MODEL_API_KEY`. Private services without authentication are supported. Never
   commit `.env`.

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

Native OCR is disabled by default. Install Tesseract with Persian and English
language data and set `OCR_ENABLED=1` to process scanned PDF pages locally.

## Docker Compose

Docker packages the Vite build, FastAPI, Tesseract, Persian OCR data, and Python
runtime in one non-root application image. Qdrant and Ollama are private services;
only the application port is published.

For an Ollama deployment, choose `OLLAMA_MODEL` in `.env` and start the local-model
profile. The one-shot initializer downloads the model into its persistent volume:

```bash
docker compose --profile local-model up --build
```

For an API-backed model, configure `LLM_PROVIDER=api`, `LLM_MODEL_NAME`,
`MODEL_API_BASE_URL`, and optional `MODEL_API_KEY`, then run:

```bash
docker compose up --build
```

The application port binds to `127.0.0.1` by default. Set
`PARSRAG_BIND_HOST=0.0.0.0` only when the workstation must be reachable on a
trusted LAN, and set `PARSRAG_ALLOWED_ORIGINS` to the exact browser origins.
Public model APIs require HTTPS; HTTP is accepted only for loopback and private
network addresses. Saving model settings verifies the provider's model-list
endpoint first. The API key stays in process memory (or the environment) and is
never written to browser storage or `model-configuration.json`; enter it again
after a process restart unless it is supplied through `MODEL_API_KEY`.

### Model trust modes

| Mode | Generation location | What can leave the workstation |
| --- | --- | --- |
| Local Ollama | This workstation | Nothing through the model adapter |
| Private API | A server on your trusted network | Prompt and, in RAG modes, retrieved document excerpts |
| External API | A third-party service | Prompt and, in RAG modes, retrieved document excerpts |

Embeddings and Qdrant remain local in all three modes. Review the configured API
operator's retention and training policy before sending confidential material.

The first start may download the multilingual embedding model into the
`model_cache` volume. Check the application at `http://127.0.0.1:8000/health`
and inspect service state with `docker compose ps`.
`HF_HUB_DISABLE_XET=1` uses the regular HTTP download path during this bootstrap;
set it to `0` only when the deployment has a tested Xet connection.

```bash
docker compose logs -f app
docker compose down
```

Qdrant vectors, Ollama models, the embedding cache, and non-secret application
configuration survive `docker compose down`. Run `docker compose down -v` only
when you intentionally want to delete all persistent volumes.

OCR behavior is controlled with `OCR_ENABLED`, `OCR_LANGUAGES`, `OCR_DPI`,
`OCR_TIMEOUT_SECONDS`, and `OCR_MAX_PAGES`. Native PDF text always uses the fast
path; Tesseract runs only for pages without selectable text.

## Verification

```bash
cd frontend
npm test
npm run build

cd ..
.venv/Scripts/python -m pytest backend/tests -q
.venv/Scripts/python -m ruff format --check backend
.venv/Scripts/python -m ruff check backend
.venv/Scripts/python -m mypy --strict backend
docker compose config -q
```

The visual identity, color tokens, motion rules and SVG usage are documented in [`frontend/BRAND.md`](frontend/BRAND.md).

## Architecture & ADRs

All foundational decisions, Domain-Driven Design (DDD) specifications, and GoF patterns (Strategy, Factory, Repository) are strictly documented in the `.context/` directory. If you are contributing to this project, please review these files carefully before submitting a PR.

## Contributing

We follow a strict **GitHub Flow** strategy and enforce **Conventional Commits**. Please refer to `.context/04_Git_and_CI.md` for branch naming rules, CI/CD pipeline requirements, and PR guidelines.
