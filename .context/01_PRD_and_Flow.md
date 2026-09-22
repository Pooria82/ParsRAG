# Product Requirements Document (PRD): ParsRAG

## 1. Executive Summary & Vision
**ParsRAG** is an offline-first, privacy-aware, RTL-optimized Persian AI assistant for single-user personal and corporate workstations. Parsing, embedding, and vector storage remain local. Generation can run through local Ollama, a private corporate OpenAI-compatible endpoint, or an explicitly enabled external API for users without suitable local hardware.

## 2. Core Objectives & Success Metrics
To guarantee production-readiness, the system must meet the following strict criteria:
- **Visible Trust Boundary:** Local Ollama keeps generation on the workstation. API mode must disclose that prompts and retrieved context are sent to the configured service while embeddings and vector storage stay local.
- **RTL & Persian Efficacy:** The system must accurately parse, OCR, chunk, and embed right-to-left Persian content across documents, images, structured text, and common source formats while maintaining structural integrity.
- **Retrieval Latency:** The retrieval pipeline (Condense Question + Vector Search + Reranking) should target a sub-2-second execution time on appropriate hardware before LLM generation begins.
- **Grounded Strict Mode:** Strict mode must refuse when retrieved evidence does not meet the configured threshold. Evaluation results apply only to the recorded dataset, model, configuration, and run date.

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
1. **Ingestion Trigger:** The user uploads up to ten supported files through the React workspace.
2. **Parsing (RTL Optimized):** Format-specific parsers extract native text and metadata. Bounded Persian/English OCR processes scanned PDF pages, standalone images, and embedded Office images only when needed.
3. **Smart Chunking:** LlamaIndex's `SentenceSplitter` (configured for Persian sentence boundaries) chunks the text (e.g., 500-1000 characters, 150 overlap).
4. **Embedding & Storage:** Chunks are vectorized using a multilingual embedding model and persisted into Qdrant Local.
5. **Query Initiation:** The user submits a prompt and selects a Query Mode.
6. **Query Condensation:** If chat history exists, the LLM rewrites the query into a standalone sentence.
7. **Vector Retrieval & Reranking:** LlamaIndex queries Qdrant for Top-K nodes. `FlashRank` reranks these nodes based on semantic relevance to the rewritten query, filtering out noise.
8. **Prompt Construction & Generation:** The reranked nodes are injected into a Persian-optimized system prompt. The selected Ollama or OpenAI-compatible adapter generates the response. In API mode, this step sends the prompt and retrieved excerpts to the configured endpoint.

## 5. Edge Cases & Graceful Degradation
The backend must never crash uncontrollably. It must degrade gracefully:
- **Scanned/Image-Only Content:** The parser applies bounded OCR and records page, slide, or image provenance. Unsupported or unreadable content returns a localized per-file error without terminating the upload batch.
- **Empty Retrieval (Strict Mode):** If the vector search + reranking returns no relevant chunks above the similarity threshold, the LLM generation is bypassed. The system returns a hardcoded/templated localized response: *"No relevant information found in the documents."*
- **LLM Timeout / Out of Memory (OOM):** Inference limits must be strictly enforced. If Ollama times out or the host machine runs out of VRAM/RAM, the backend intercepts the `500 Internal Server Error` or timeout exception, returning a graceful UI alert: *"The model took too long to respond or ran out of memory. Please try a shorter query or clear your session."*

## 6. Out of Scope (Phase 1)
To ensure a successful MVP, the following are strictly excluded from Phase 1 development:
- **Unbounded OCR and media understanding:** OCR is supported within configured page, image, pixel, memory, and concurrency limits. General video/audio understanding and unrestricted vision-model processing remain outside this release.
- **Multi-Tenancy & Auth:** While the architecture is stateless to support future scaling, Phase 1 is strictly a single-user local deployment. No login systems or user permission matrices will be built.
- **Managed Cloud Storage:** Documents and vectors are not stored in a managed cloud database. An external model API remains an explicit user-selected generation option.
- **GraphRAG:** Advanced knowledge graph extraction is reserved for Phase 2+.
