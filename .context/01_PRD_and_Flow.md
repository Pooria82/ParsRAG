# Product Requirements Document (PRD): ParsRAG

## 1. Executive Summary & Vision
**ParsRAG** is a completely offline, privacy-first, RTL-optimized Persian AI assistant. Built upon local Large Language Models (LLMs), it acts as a highly secure Retrieval-Augmented Generation (RAG) system for environments with strict data confidentiality (educational, research, and organizational). The vision is to provide a FAANG-grade intelligent assistant that parses Persian text with high fidelity, executes complex semantic retrieval, and reasons over local documents—ensuring absolutely zero data leakage to the internet.

## 2. Core Objectives & Success Metrics
To guarantee production-readiness, the system must meet the following strict criteria:
- **Zero Data Leakage:** 100% of data processing, embedding, vector storage, and LLM inference must occur locally on the host machine.
- **RTL & Persian Efficacy:** The system must accurately parse, chunk, and embed right-to-left Persian text (PDF/TXT) while maintaining structural integrity.
- **Retrieval Latency:** The retrieval pipeline (Condense Question + Vector Search + Reranking) should target a sub-2-second execution time on appropriate hardware before LLM generation begins.
- **Hallucination Prevention:** In "Strict Mode", the system must achieve a 0% hallucination rate by gracefully refusing to answer questions unsupported by the retrieved context.

## 3. Detailed Functional Requirements

### 3.1. Query Modes
The system features a tripartite query routing mechanism to offer flexible interaction:
1. **Strict RAG (100% Grounded):** The LLM is strictly constrained to the retrieved context. If the answer is absent from the documents, the system will explicitly state its inability to answer. This prevents hallucination and is vital for factual organizational queries.
2. **LLM-Only (General Knowledge):** The vector database is bypassed entirely. The LLM acts as a standard offline chatbot relying solely on its pre-trained weights.
3. **Hybrid RAG (Grounded but Expanded):** The system retrieves relevant chunks as a primary factual basis but permits the LLM to leverage its pre-trained knowledge to synthesize, interpret, or expand upon the retrieved data.

### 3.2. Document Lifecycle
- **Global Knowledge Base:** A persistent collection in the vector database (Qdrant) containing long-term, organizational documents. This data remains searchable across all user sessions.
- **Session-Scoped Uploads:** Users can upload temporary documents for ad-hoc analysis. These documents exist in an isolated vector namespace and are purged or ignored once the specific chat session terminates, preventing permanent database pollution.

### 3.3. Conversational Memory ("Condense Question" Pipeline)
Standard vector search fails on conversational follow-ups containing pronouns (e.g., "What did it say about X?"). To resolve this:
- The system maintains a sliding window of the Chat History.
- Upon receiving a follow-up query, the LLM first executes a fast "Condense Question" prompt, utilizing the chat history to rewrite the user's input into a standalone query.
- *Example:* `[History: "Explain the new HR policy"] + [Query: "When does it start?"] -> [Rewritten: "When does the new HR policy start?"]`
- This rewritten query is then used for semantic vector retrieval.

## 4. User & Data Flow (Step-by-Step)
1. **Ingestion Trigger:** The user uploads a PDF/TXT file via the async Chainlit UI.
2. **Parsing (RTL Optimized):** `PyMuPDF` extracts the raw Persian text, preserving RTL reading order.
3. **Smart Chunking:** LlamaIndex's `SentenceSplitter` (configured for Persian sentence boundaries) chunks the text (e.g., 500-1000 characters, 150 overlap).
4. **Embedding & Storage:** Chunks are vectorized using a multilingual embedding model and persisted into Qdrant Local.
5. **Query Initiation:** The user submits a prompt and selects a Query Mode.
6. **Query Condensation:** If chat history exists, the LLM rewrites the query into a standalone sentence.
7. **Vector Retrieval & Reranking:** LlamaIndex queries Qdrant for Top-K nodes. `FlashRank` reranks these nodes based on semantic relevance to the rewritten query, filtering out noise.
8. **Prompt Construction & Generation:** The reranked nodes are injected into a Persian-optimized system prompt. The LLM (via Ollama) generates a streaming response back to the UI.

## 5. Edge Cases & Graceful Degradation
The backend must never crash uncontrollably. It must degrade gracefully:
- **Scanned/Image-Only PDFs:** If `PyMuPDF` detects zero selectable text layers, the ingestion pipeline immediately halts for that document. A clear UI warning is surfaced to the user stating that scanned documents are not supported.
- **Empty Retrieval (Strict Mode):** If the vector search + reranking returns no relevant chunks above the similarity threshold, the LLM generation is bypassed. The system returns a hardcoded/templated localized response: *"No relevant information found in the documents."*
- **LLM Timeout / Out of Memory (OOM):** Inference limits must be strictly enforced. If Ollama times out or the host machine runs out of VRAM/RAM, the backend intercepts the `500 Internal Server Error` or timeout exception, returning a graceful UI alert: *"The model took too long to respond or ran out of memory. Please try a shorter query or clear your session."*

## 6. Out of Scope (Phase 1)
To ensure a successful MVP, the following are strictly excluded from Phase 1 development:
- **Optical Character Recognition (OCR):** Processing scanned images/PDFs (e.g., via Tesseract) is deferred to future phases to avoid heavy dependencies and performance bottlenecks.
- **Multi-Tenancy & Auth:** While the architecture is stateless to support future scaling, Phase 1 is strictly a single-user local deployment. No login systems or user permission matrices will be built.
- **Cloud Integrations:** No fallback to OpenAI, Anthropic, or external cloud vector databases. The system remains 100% air-gapped.
- **GraphRAG:** Advanced knowledge graph extraction is reserved for Phase 2+.
