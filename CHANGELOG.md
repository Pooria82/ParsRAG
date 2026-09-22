# Changelog

All notable changes follow [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this project uses Semantic Versioning.

## [Unreleased]

## [0.1.0] - 2026-09-22

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

[Unreleased]: https://github.com/Pooria82/ParsRAG/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Pooria82/ParsRAG/releases/tag/v0.1.0
