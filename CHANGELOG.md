# Changelog

All notable changes follow [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this project uses Semantic Versioning.

## [Unreleased]

## [1.0.0] - 2026-09-24

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

### Upgrade note

- Remove and upload previously indexed PDFs again to gain page-boundary chunks
  and improved OCR text. Existing vectors are retained until users replace them.

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
[1.0.0]: https://github.com/Pooria82/ParsRAG/releases/tag/v1.0.0
[0.1.0]: https://github.com/Pooria82/ParsRAG/releases/tag/v0.1.0
