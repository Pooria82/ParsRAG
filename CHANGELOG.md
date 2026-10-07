# Changelog

All notable changes follow [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this project uses Semantic Versioning.

## [Unreleased]

## [1.0.0] - 2026-10-08

### Added

- Answers stream token by token (`POST /query/stream`, Server-Sent Events):
  stages, the numbered sources, text, and the final result. Stopping keeps
  what was already written.
- Numbered citations: the model cites excerpts as `[n]`, the response lists
  which ones it used (`cited`), and the interface turns them into chips that
  open the cited passage. Uncited passages fold under "more passages
  consulted".
- Questions your documents can answer: an empty conversation suggests three
  specific questions written from its documents (`POST
  /sessions/{id}/suggestions`).
- Every answer shows where its content came from (documents only, documents
  and model knowledge, model knowledge, or not found in the documents).
- Conversation backup and restore (versioned JSON) and per-conversation
  Markdown export.
- Keyword (BM25) search fused with vector search; on keyword-style queries it
  raised mean reciprocal rank from 0.748 to 0.823.
- OCR re-reads sideways, upside-down, and skewed scans (character error for
  pages rotated 90° fell from 0.85 to 0.09).
- Windows-1256 (Persian), UTF-16, and Windows-1252 text files.
- Duplicate uploads are recognized by content, not only by name.
- Opt-in E5 query/passage prefixes (`EMBED_E5_PREFIXES=1`).
- End-to-end CI job: upload to cited answer through real parsing, embeddings,
  Qdrant, and reranking, with a retrieval quality gate.

### Improved

- Documents-only (Strict) mode answers by meaning: paraphrased questions,
  whole-document questions, and partial answers no longer get refused, while
  facts must still come from the documents.
- Persian PDF text is rebuilt in reading order from glyph positions; the ezafe
  mark stays on its letter; text layers without usable Unicode go to OCR.
- OCR: grayscale at 200 dpi, no contrast stretching, a confidence-based second
  pass, and no invisible bidi marks (mean character error 0.225 → 0.133).
- Mathematical answers: Persian words are never typeset as math, bare LaTeX
  commands are rendered, and unclosed delimiters are removed.
- Hybrid reranks with an Arabic-script cross-encoder that is cached on disk
  (MRR 0.354 → 0.710 against the previous English model).
- Persian spelling is normalized in indexed text and questions (Arabic Yeh and
  Kaf, presentation forms, diacritics, digits).
- Word documents are chunked under their headings (median chunk 13 → 91 words)
  and each chunk carries its heading path.
- Prompts fit the model's context window, and Ollama receives `num_ctx`.
- Conversations are stored in IndexedDB (migrated automatically from
  localStorage).

### Fixed

- A failed upload no longer leaves a partly indexed document behind.
- Word and PowerPoint files with more than 30 images, and scans longer than
  `OCR_MAX_PAGES`, are indexed in part with a notice instead of rejected.
- A PDF with a few image pages is indexed when Tesseract is not installed;
  the skipped pages are named in a notice.
- Uploads up to the advertised 500 MiB fit the container's temporary storage.
- Server timeouts no longer outlive the browser's wait.
- A rendering error shows a recovery screen instead of a blank page.

### Security

- Requests addressed to host names other than localhost, 127.0.0.1, and ::1
  are rejected (DNS rebinding); `PARSRAG_ALLOWED_HOSTS` adds names for LAN use.

### Changed

- Error responses carry a stable `code` next to `detail`, and the interface
  explains each one (for example an encrypted PDF or a rejected API key).
- `POST /ingest` returns per-file chunk counts and notices; `POST /query`
  returns `cited` and `outcome`.
- The project website moved to its own repository,
  [ParsRAG-Landing](https://github.com/Pooria82/ParsRAG-Landing), published at
  <https://pooria82.github.io/ParsRAG-Landing/>; the old GitHub Pages address
  redirects there.

### Upgrade note

- Documents indexed by 0.2.0 keep working. Upload them again to gain Persian
  normalization, heading-based Word chunks, content-based duplicate detection,
  and the improved PDF text and OCR.
- The first start downloads the reranker (about 100 MB) into the model cache.

## [0.2.0] - 2026-10-07

### Added

- Installable PWA with an offline interface shell and a transparent project mark.
- Document mentions, reusable indexed files, quick commands, platform-aware
  shortcuts, personalized color palettes, and a guided tour that opens and
  explains the controls in place.
- Searchable page-boundary excerpts for newly indexed PDFs, with page-range
  citations when an answer spans adjacent pages.

### Improved

- Strict document answers can use borderline vector matches only when the
  retrieved text also supports the question's distinctive terms; unrelated
  evidence continues to be refused.
- OCR also checks image-heavy PDF pages with short text layers and normalizes
  standalone/embedded images before recognition, within the configured limits.
- Scrollbars across the workspace, panels, menus, and long-form content now
  share the active color theme and remain usable in light and dark modes.

### Changed

- The backend core is organized as ports and adapters: Protocol ports,
  one use case per operation, input/output DTOs, and a single composition
  root. The HTTP contract is unchanged; OpenAPI now documents typed responses
  for health, ingestion, progress, reuse, and deletion endpoints.

- Frontend runtime upgraded to React 19 and TypeScript 7; Python runtime and
  tooling refreshed; Dependabot updates now target `develop`.

### Fixed

- Runtime images could build but fail to import the app because
  transformers was not pinned; transformers and sentence-transformers are now
  pinned, and CI imports the app inside the built image.
- `STRICT_RAG_TOP_K`, `RAG_TOP_K`, and `HYBRID_RERANK_TOP_K` now take effect as
  fixed retrieval depths, and the Strict threshold defaults to 0.80 everywhere.

### Security

- CPU and NVIDIA images use Debian Trixie and PyTorch 2.13; the high-severity
  `source-map-js` advisory is resolved in the frontend toolchain.

### Documentation

- Added ARCHITECTURE.md, DATA.md, ADR 08, and blueprints for data flow, use
  cases, and DTOs, plus a bilingual project website under `docs/`.

### Upgrade note

- Remove and upload previously indexed PDFs again to gain page-boundary chunks
  and improved OCR text. Existing vectors are retained until users replace them.
- If your `.env` sets `RAG_TOP_K`, `STRICT_RAG_TOP_K`, or `HYBRID_RERANK_TOP_K`,
  those values now force a fixed depth; leave them empty for adaptive depth.

## [0.1.0] - 2026-09-23

### Added

- Offline-first React workspace with Persian and English direction support.
- Session-scoped document retrieval with source locations across PDF, DOCX,
  PPTX, images, text/data, markup/configuration, and common source-code formats.
- Bounded OCR for scanned PDF pages, standalone images, and images embedded in
  Word and PowerPoint documents.
- Local Ollama and optional-key OpenAI-compatible model connections.
- Docker Compose packaging, Persian OCR, readiness checks, and browser smoke tests.
- CPU, NVIDIA CUDA, and Linux AMD ROCm Compose paths for Ollama and local
  embeddings, with explicit verification commands in English and Persian guides.
- A low-VRAM NVIDIA overlay that reserves GPU capacity for Ollama generation
  when a 7B model and the embedding model cannot fit together.
- Runtime ingestion capability discovery so backend limits and frontend
  validation remain synchronized.

### Changed

- Increased defaults to 10 documents per session, 100 MiB per file, and 500 MiB
  per upload batch.
- Reduced peak ingestion memory with bounded embedding and Qdrant upsert batches,
  configurable CPU threads, OCR image limits, and container memory ceilings.
- Expanded the Vite development proxy to cover model settings, capability
  discovery, query progress, and generated conversation titles.
- Split large React, Markdown/KaTeX, icon, and vendor bundles for faster cache
  reuse and a smaller initial application chunk.

### Security

- Loopback network defaults, trusted browser origins, validated model API URLs,
  bounded uploads and archives, concurrency limits, and non-persistent API keys.

### Legal

- Established owner-controlled source-available terms, an upstream-only
  contribution path, citation metadata, and explicit copyright notices.

[Unreleased]: https://github.com/Pooria82/ParsRAG/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/Pooria82/ParsRAG/compare/v0.2.0...v1.0.0
[0.2.0]: https://github.com/Pooria82/ParsRAG/releases/tag/v0.2.0
[0.1.0]: https://github.com/Pooria82/ParsRAG/releases/tag/v0.1.0
