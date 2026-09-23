# ADR 06: Persian conversation workspace

Date: 2026-09-16

## Context

The repository replaced its Chainlit interface with React 18, TypeScript and
Vite in commit `7c3662a`. FastAPI serves `frontend/dist`; the obsolete Python
frontend was removed after the migration. This ADR records that boundary and the
refinement of the React interface. Backend strategies, repositories, query
condensation and the three query modes remain the source of truth.

## Decisions

- Design a quiet, Persian-first conversation workspace: warm paper surfaces,
  deep evergreen accents, a geometric book-inspired mark, generous reading
  measure and an equivalent charcoal dark theme. Avoid decorative gradients.
- Keep the empty-state composer at the center of the workspace. In an active
  conversation, anchor it below the scrolling messages. Put document management
  in a deliberate side panel and history in a collapsible sidebar.
- Bundle Persian typography locally. No runtime CDN, font service, telemetry,
  remote illustrations or external image rendering from model output.
- Use semantic CSS tokens, logical RTL properties, native accessible dialogs,
  keyboard-operable controls, reduced motion and responsive layouts.
- Preserve existing local conversation/settings storage keys. Validate stored
  data and handle persistence failures without crashing the UI.
- Show backend query stages while work is in progress, progressively reveal the
  completed response, and abort the browser request on Stop. Browser abort does
  not claim that an already-running backend inference was cancelled.
- Discover upload capabilities from the backend. The current defaults allow ten
  documents, 100 MiB per file, and 500 MiB per batch across PDF, Office, image,
  text, data, markup, configuration, log, and common source-code formats.
- Support single-document deletion, deselect-all retrieval, and complete session
  deletion. Report server failures instead of claiming cleanup. Clearing browser
  conversation history remains an explicit local action.
- Expose persisted model-runtime settings for local Ollama and OpenAI-compatible
  private or external APIs. Never return, log, or store API-key contents in the
  browser; report only whether a process-memory or environment credential exists.
- Development uses Vite on port 3000 with a same-origin API proxy. Production
  uses the FastAPI origin. UI preferences and chat history remain in the browser.

## Validation

Run TypeScript and production build checks, focused automated frontend tests
for state/API contracts, browser interaction and responsive checks, and the
existing backend pytest suite. Record any unavailable live-model validation
separately from deterministic API-fixture verification.
