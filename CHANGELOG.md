# Changelog

All notable changes follow [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this project uses Semantic Versioning.

## [Unreleased]

### Added

- Update check: once a day the server asks GitHub (anonymously) for newer
  releases (`GET /updates`, `UPDATE_CHECK_ENABLED`, on by default and in
  Settings). The sidebar offers the latest one, and its window lists the
  changes of every newer release in Persian or English, asks for a backup of
  the conversations, and gives one command:
  `scripts/update.ps1` (Windows) or `scripts/update.sh`.
- The update scripts back up `.env`, the Qdrant data, and the model settings,
  go straight to the latest release tag, rebuild with the same Compose files
  and profile, wait until the service is ready, and start the previous
  version again if the rebuild fails.
- After an update the app shows what changed in every version since the last
  one seen (`GET /release-notes`, from `release-notes/<version>.<fa|en>.md`),
  and an open page loads the new interface by itself: the page and the service
  worker are served with `Cache-Control: no-cache`, hashed assets are cached
  for a year, and a waiting interface is activated when nothing is running.
- One version for the project in `VERSION`, read by the backend and the
  frontend build; `scripts/set_version.py` copies it to `pyproject.toml`,
  `package.json`, `package-lock.json`, and `CITATION.cff`, and a test keeps
  them in step.

- `OCR_DOCUMENT_TIMEOUT_SECONDS` (default 900, changeable in Settings) bounds
  the OCR time of one document. Remaining pages and images are skipped with a
  notice and the rest is indexed.
- PowerPoint speaker notes are indexed with their slide.
- CSV and TSV files are read as tables, with row records and whole-table
  answers.
- Text files are split at Markdown headings or about 300 words, so sources
  name a section instead of the whole file.
- Uploaded images keep a preview shown next to their source.
- Streamed answers send a `ping` event every 15 seconds while the server
  works, so the browser waits as long as the model needs (up to the server's
  own timeouts) and gives up only on a connection that went quiet.
- An unanswered question (stopped before any text, or interrupted) has a
  Try again button.
- Open tabs of the workspace share their changes instead of overwriting each
  other's conversations.

### Improved

- The service status card shows the model clearly for any name: the model
  in monospace with its variant as a tag (`gemma3` `4b`), its publisher and
  the provider below (`google · API service`), an icon for local or API, and
  the full id on hover.
- Scanned PDF pages are recognized several at a time, like images in Word and
  PowerPoint, and near-certain OCR readings skip the skew search. On the
  96-image final report the text is unchanged.

### Fixed

- After the Settings window (or any dialog) closes with the mouse, the button
  that opened it no longer shows the keyboard focus ring.
- An external model API can no longer be connected without an API key.
  OpenRouter lists its models without a key, so saving the connection passed
  and every question then failed with "internal error". Saving is now refused
  with a message, the sidebar says "No API key is set" instead of "Service
  ready", and a question names the missing key. The key form shows which host
  the service holds a key for (a key is only sent to its own host; a key in
  `.env` belongs to `MODEL_API_BASE_URL`).
- "Service ready" no longer appears while the model cannot answer. A new
  `GET /models/status` checks the active model service (Ollama running with
  the selected model installed; an API reachable and accepting the key, at
  most every 10 seconds), and the sidebar says "Ollama is not reachable",
  "This model is not installed in Ollama", "The model API is not reachable"
  or "The API key was rejected" instead, with a Check again button whose
  icon spins while the check runs.
- Answers are written in the language of the question, also when the
  documents are in the other language. A follow-up such as «چطور تمدید
  می‌شوند؟» about English documents was rewritten as an English question, and
  the answer language was taken from that rewrite; with gemma3:4b all five
  such test questions were answered in the wrong language, and now all five
  are right. The prompt asks to translate what it uses and starts the answer
  in the question's language. A question without words (a formula) is
  answered in the interface language, which the browser now sends.
- Your questions sit on the side their language starts from: Persian on the
  right and English on the left, in either interface language. They were on
  the opposite side.
- Text and pictures inside grouped PowerPoint shapes are indexed, and a
  linked picture adds a notice instead of rejecting the whole deck.
- Content inside Word content controls (forms, templates) is indexed; a
  generated table of contents is skipped.
- An image that declares more pixels than allowed is reported as an OCR
  notice instead of a server error.
- HTML table cells are separated instead of running together.
- A UTF-8 file with a few stray bytes is read as UTF-8 instead of turning
  into Windows-1256 mojibake.
- A question asked while a document was being deleted could keep that
  document in keyword search until the next change.
- `/query/stream` answers a full query capacity with 429 and an unknown
  `@{file}` with 400 before streaming, instead of 200 plus an error event. A
  client that disconnects marks the query failed instead of leaving it at
  "generating" for five minutes.
- Documents-only mode no longer skips its evidence check for ordinary
  questions that contain words such as «خلاصه», «موضوع» or «چه نوع»; only
  questions about the document itself, or a bare request to summarize, do.
- The documents-only refusal is the same sentence in the evidence check and
  in the prompt, in the question's language. An invalid
  `STRICT_RAG_THRESHOLD` falls back to the default instead of failing every
  documents-only question.
- Brackets inside math and code, such as the interval `[1, 3]`, are no
  longer counted as citations.
- Hybrid mode trims the context in its ranked order; mixing reranker and
  cosine scores could drop the best reranked passage.
- A stored API key is only sent to the server it was entered for; changing
  the API address without a new key no longer sends the old one.
- API requests have one retry layer (`MODEL_API_MAX_RETRIES`); the OpenAI SDK
  no longer retries on top of it.
- Conversation titles and suggested questions are capped on Ollama too.
- Resetting CPU threads to automatic restores the startup value.
- A failed reranker download waits five minutes before the next attempt
  instead of being retried on every Hybrid question, and the download has a
  timeout.
- Listing, previewing, reusing and deleting documents wait until the
  embedding model is ready, like questions and uploads.
- Runtime settings are validated, saved, and applied as one step; a failed
  save changes nothing.
- The message box accepts 12,000 characters, the API's limit, and a question
  that is too long says so. A failed or unanswered turn is no longer sent as
  history, and long turns are shortened, so one failure does not make the
  next questions fail too.
- Answers keep links, `snake_case` names and dollar amounts such as "$5"
  instead of typesetting them as math.
- Unsaved server-setting edits survive the 30-second health check and other
  changes, and clearing a number field no longer switches it to Automatic.
- Editing a question that never got an answer no longer attaches the new
  answer to a later question; the answer is placed right after it.
- A save that fell back to `localStorage` (IndexedDB failed) is loaded on the
  next start instead of the older IndexedDB copy.
- Keyboard shortcuts work with the Persian keyboard layout.
- The unused browser setting `strictThreshold` is removed; the Strict
  threshold is a server setting.
- `npm run dev` proxies `/settings`, so server settings load in development.
- Deleting a conversation or clearing all data works while the service is
  offline; documents on the server are deleted when it is reachable again.
  Conversations without documents never need the server.
- Importing a backup applies its preferences, and its documents show as not
  on this server until the server lists them.
- A timeout or dropped connection keeps the text that already streamed, with
  the reason below it, as Stop does.
- Upload limits follow a server-settings change at once; answer-version
  arrows point the reading direction in English; Strict mode with every
  document unticked asks to select one; starter cards keep the chosen mode;
  dragging from inside a dialog to outside no longer closes it; the rename
  field is focused.
- The backend codes `not_found`, `conflict`, `upstream_unavailable`,
  `invalid_session`, `no_file`, `untrusted_host`, `service_error` and
  `request_failed` have messages, and reusing or deleting a document and the
  model settings show the server's reason.

### Documentation

- The ADRs describe the project as it is: pip with `requirements.lock` instead
  of Poetry, `compose.yaml`, the e2e suite instead of Testcontainers, opt-in
  live evaluation, JSON logs, the GitFlow-style branches without `staging`,
  the actual CI jobs, and releases that build but do not publish images. The
  PWA ADR is now number 09 (two were numbered 07), and `Reranker`,
  `RuntimeSettingsStore` and `SuggestQuestions` are in the architecture
  documents.
- The live PDF evaluation indexes and asks through the same use cases as the
  API, so it includes Persian normalization, page bridges, duplicate checks
  and the answer language.

### Security

- `filelock` (pulled in by PyTorch and Hugging Face) is upgraded to 4.2.1
  for CVE-2026-112940, an arbitrary file overwrite.
- At startup, a saved API connection to one host no longer receives the
  `.env` key of another (`MODEL_API_KEY` belongs to `MODEL_API_BASE_URL`).
  A connection saved for OpenRouter was given the Google AI Studio key from
  `.env` and sent it to OpenRouter.
- Model API requests re-check the host's addresses each time and do not
  follow redirects, so a DNS change or redirect cannot reach link-local
  (cloud metadata), multicast, or reserved addresses.

## [1.1.1] - 2026-10-22

### Changed

- The default local model is `gemma3:4b` everywhere (code, Compose,
  `.env.example`, the interface, and the README). It fits fully on a 6 GB GPU
  and was the most accurate of the small models tested. Set `LLM_MODEL_NAME`
  to keep another model.

### Fixed

- Request and operation logs are written to stdout at `LOG_LEVEL` (one JSON
  object per line, or plain text with `ENVIRONMENT=development`). Nothing
  configured them before, so they were dropped.
- After the startup retries run out, the service reports `failed` but keeps
  retrying every minute and becomes ready once Qdrant or the model cache is
  back, without a restart.
- The README sections that run Ollama inside Docker set
  `OLLAMA_DOCKER_BASE_URL=http://ollama:11434`; without it the app kept using
  the Ollama installed on the computer.
- `EMBED_QUERY_PREFIX` and `EMBED_PASSAGE_PREFIX` reach the app in Docker.
- The README settings tables mark every setting that can be changed in the
  app and document `MODEL_API_MAX_RETRIES`.
- PowerPoint slides no longer add their slide number, date, or footer to the
  text, so the slide-number field (shown as `‹#›`) no longer appears in
  answer sources or search. Upload existing presentations again to remove it
  from them.

### Security

- Pillow is upgraded to 13.0.0 to fix denial-of-service and information
  disclosure vulnerabilities in 12.3.0, one of them critical.

## [1.1.0] - 2026-10-19

### Added

- Settings in the app can change the options that used to need `.env` and a
  restart (27 in all), in four groups:
  - model: context sizes, thinking, retries, timeouts
  - retrieval: threshold, depths, keyword search
  - documents: upload limits, OCR, image previews
  - indexing speed: OCR workers, CPU threads, batches

  Each shows its `.env` value and can be reset to it. Overrides survive
  restarts. Ports, allowed addresses, Qdrant, memory limits, and the embedding
  model stay in `.env`.
- Answer sources show the image an excerpt was read from, next to the excerpt.
- Installed Ollama models are offered in a menu, with their sizes.
- `.env.example` now has only the model choice active. Every other setting
  shows its default, grouped by whether Settings can also change it.
- The README starts with one complete setup using every capability; other ways
  to run follow it.
- The app can use the Ollama installed on the computer (Windows, macOS,
  Linux) with its existing models and GPU. Set
  `OLLAMA_DOCKER_BASE_URL=http://host.docker.internal:11434` in `.env` and
  start without the `local-model` profile. No override file is needed, and the
  app container needs no GPU. The README's "Complete run" section covers
  each system, GPU memory, and troubleshooting.
- `OLLAMA_ALLOWED_HOSTS` adds hosts that Ollama URLs may use.
  `OLLAMA_INTERNAL_HOST` is still read.
- Settings explains Ollama failures ("address not allowed", "did not answer")
  in Persian and English. When an API is active, it offers the server's own
  Ollama URL.

- Images inside Word and PowerPoint files are cited by number: text read
  from an image is its own excerpt with the image's caption, shown as
  "paragraph 120 · image 7" or "slide 25 · image 9", and answers say when a
  fact comes from an image. Each image excerpt also carries the text that
  introduces it (the end of the paragraph before it, or the slide's text).
- Word tables are cited by number and the paragraph they follow
  ("paragraph 120 · table 3") instead of an internal element index.
- When part of a table is retrieved, the rest of the table comes with it, so
  questions about the largest or smallest value see every row.

### Improved

- Questions that ask several things ("… with which key, and which fields …")
  are also searched part by part. Each part keeps its best excerpts, and the
  model is asked to answer every part. In the acceptance set, 5 of the 6
  answers that missed a part became complete, with no regressions among the
  questions that were already right.
- Indexing is faster with the same results:
  - Pictures in Word and PowerPoint are read several at a time
    (`OCR_WORKERS`). The 96-image final report parsed in 33 s instead of
    121 s, with identical text.
  - Each document is embedded in length-sorted batches.

  Indexing that whole report went from about 4.5 minutes to about 3.
- OCR reads screenshots better: a second, sparse-text pass adds text that
  page layout analysis skipped (status panels, dark UI themes).
- Up to 200 images per Word or PowerPoint file are read (was 30).
- With several documents, specific questions search all files together, so
  the file that holds the answer can provide most excerpts; each other file
  still contributes its best match, and passages repeated across files are
  kept once.
- Commands and code in one-cell boxes in Word stay with the sentence that
  introduces them, so questions about them find them.
- OCR reads text on tinted panels (for example a light-blue status box).

### Fixed

- `[extract_itex]...[/extract_itex]` markup that Gemini models leak into answers
  is shown as math, and table rows inside a source excerpt render as a table.
- Thinking models on Ollama (such as `qwen3.5`) no longer return empty
  answers. They could spend the whole answer budget on reasoning, so Ollama
  is now asked not to think unless `OLLAMA_THINK=1`. On a 6 GB GPU with
  `qwen3.5:4b`, an empty reply after 59 s became a cited answer in 7 s.
- Reasoning that some APIs put inside answers (`<thought>...</thought>` from
  Google AI Studio's Gemma 4, `<think>...</think>` elsewhere) is removed from
  answers, streams, conversation titles, and suggested questions.
- Transient API failures (HTTP 5xx and 429) are retried up to
  `MODEL_API_MAX_RETRIES` times (default 4) with growing delays; Google AI
  Studio's free tier fails about one Gemma request in three.
- Google AI Studio model ids get the `models/` prefix its endpoint requires.
- English questions get English answers in Hybrid and open-chat modes; they
  were often answered in Persian. Every prompt now names the answer language,
  detected from the question.
- The service retries startup when Qdrant is briefly unavailable instead of
  staying not ready until restarted.
- A question is no longer limited to one file just because it shares an
  ordinary word with the file name (such as «اول» or «تست»).
- An API provider that is out of credit (HTTP 402) is reported as such, with
  a hint to top up the account or choose another model.

### Security

- Questions with long runs of spaces or many unclosed `@{` mentions can no
  longer make question splitting or answer-language detection slow (CodeQL
  regular-expression alerts).

### Changed

- Every backend test runs without skips and without Docker:
  `PARSRAG_E2E=1 pytest` runs the end-to-end tests against an in-memory
  Qdrant unless `QDRANT_HOST` names a server.
- Dependencies: FastAPI 0.143, Uvicorn 0.54, python-dotenv 1.2.4, Ruff 0.17,
  mypy 2.4, KaTeX 0.19, Vite 8.3.4, Playwright 1.64, lucide-react 1.56,
  msgpack 1.2.3 or later.

### Upgrade note

- Documents indexed by 1.0.0 keep working. Upload Word and PowerPoint files
  again to gain image and table citations, image previews next to sources,
  images past the 30th, and the improved OCR of screenshots.
- Settings changed in the app are saved in the `app_config` volume and take
  precedence over `.env`; each can be reset to its `.env` value.

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

- The Strict evidence threshold defaults to 0.75 (was 0.80), so paraphrased
  questions about the documents are no longer refused.
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

[Unreleased]: https://github.com/Pooria82/ParsRAG/compare/v1.1.1...HEAD
[1.1.1]: https://github.com/Pooria82/ParsRAG/compare/v1.1.0...v1.1.1
[1.1.0]: https://github.com/Pooria82/ParsRAG/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/Pooria82/ParsRAG/compare/v0.2.0...v1.0.0
[0.2.0]: https://github.com/Pooria82/ParsRAG/releases/tag/v0.2.0
[0.1.0]: https://github.com/Pooria82/ParsRAG/releases/tag/v0.1.0
