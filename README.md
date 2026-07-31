# ParsRAG 🇮🇷

**An Offline, Privacy-First, RTL-Optimized Persian AI Assistant.**

ParsRAG is an enterprise-grade Retrieval-Augmented Generation (RAG) system built exclusively for the Persian language. Designed for environments with strict data confidentiality (educational, research, and organizational), ParsRAG operates **100% locally**. It parses Persian PDFs with high fidelity, executes complex semantic retrieval, and reasons over local documents with zero data leakage to the internet.

---

## 🚀 Key Features

* **3 Intelligent RAG Modes:**
  * **Strict RAG:** Answers solely based on ingested documents to prevent hallucination.
  * **Hybrid RAG:** Combines retrieved document chunks with the LLM's inherent reasoning for comprehensive answers.
  * **LLM-Only:** Bypasses the vector DB to act as a general-knowledge offline chatbot.
* **Flawless RTL Extraction:** Utilizes PyMuPDF to extract right-to-left Persian text from digital PDFs while preserving structural integrity.
* **Conversational Memory:** Employs a fast "Condense Question" pipeline to accurately resolve pronouns in follow-up queries.
* **100% Air-gapped & Offline:** Powered by Ollama (Qwen 2.5) running locally. No external APIs or cloud services required.

## 🛠 Technology Stack

ParsRAG is built using a modern, loosely-coupled microservices architecture:

* **UI:** [Chainlit](https://docs.chainlit.io/) (Asynchronous, streaming chat interface)
* **API:** [FastAPI](https://fastapi.tiangolo.com/) (Robust, typed backend)
* **RAG Orchestrator:** [LlamaIndex](https://www.llamaindex.ai/) (Advanced chunking and semantic routing)
* **Vector Database:** [Qdrant](https://qdrant.tech/) (High-performance, Rust-based vector search)
* **LLM Engine:** [Ollama](https://ollama.com/) (Serving Qwen 2.5 locally)
* **Parser:** PyMuPDF
* **Infrastructure:** Docker & Docker Compose

## 📁 Repository Structure

```text
ParsRAG/
├── .context/                  # Architecture Decision Records (ADRs) and PRDs
├── backend/                   # FastAPI API, LlamaIndex Core, and Infrastructure
├── frontend/                  # Chainlit Chat UI
├── tests/                     # Pytest suite
└── docker-compose.yml         # Container orchestration
```

## ⚙️ Quick Start (Coming Soon)

*(Note: The project is currently entering the implementation phase. The following instructions are a blueprint for deployment.)*

1. **Clone the repository:**
   ```bash
   git clone https://github.com/your-org/ParsRAG.git
   cd ParsRAG
   ```
2. **Configure Environment:**
   ```bash
   cp .env.example .env
   ```
3. **Start the Microservices:**
   ```bash
   docker-compose up --build
   ```
4. **Access the UI:**
   Open your browser and navigate to `http://localhost:8000`.

## 📖 Architecture & ADRs

All foundational decisions, Domain-Driven Design (DDD) specifications, and GoF patterns (Strategy, Factory, Repository) are strictly documented in the `.context/` directory. If you are contributing to this project, please review these files carefully before submitting a PR.

## 🤝 Contributing

We follow a strict **GitHub Flow** strategy and enforce **Conventional Commits**. Please refer to `.context/04_Git_and_CI.md` for branch naming rules, CI/CD pipeline requirements, and PR guidelines.
