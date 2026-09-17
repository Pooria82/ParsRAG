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
- Use the existing JSON query endpoint honestly: show a pending indicator and
  abort the browser request on Stop. This cannot cancel backend inference.
- Offer only PDF, DOCX and PPTX uploads, matching the current parser (50 MiB,
  five documents). Upload files separately so per-file results are accurate.
- There is no single-file deletion endpoint. Indexed documents remain listed;
  retrieval selection uses the supported `file_filter` contract. Full session
  deletion uses the existing endpoint and reports failures instead of claiming
  successful server cleanup. Browser-history clearing is explicitly local.
- Do not expose model selection or strict-threshold inputs as functional
  controls: the current query API cannot apply either. Settings explain that
  the backend configures them; default mode and retrieval depth remain editable.
- Development uses Vite on port 3000 with a same-origin API proxy. Production
  uses the FastAPI origin. UI preferences and chat history remain in the browser.

## Validation

Run TypeScript and production build checks, focused automated frontend tests
for state/API contracts, browser interaction and responsive checks, and the
existing backend pytest suite. Record any unavailable live-model validation
separately from deterministic API-fixture verification.
