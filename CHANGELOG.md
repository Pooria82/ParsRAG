# Changelog

All notable changes follow [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this project uses Semantic Versioning.

## [Unreleased]

### Changed

- Redesigned the bilingual project website around cited answers: a scroll-driven
  demo ties each citation to its source page, followed by the ingestion
  sequence, answer modes, the local trust boundary, supported formats and quick
  start. Fonts and scripts are self-hosted, and reduced motion is respected.

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

[Unreleased]: https://github.com/Pooria82/ParsRAG/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/Pooria82/ParsRAG/releases/tag/v0.2.0
[0.1.0]: https://github.com/Pooria82/ParsRAG/releases/tag/v0.1.0
