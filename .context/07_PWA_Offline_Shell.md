# Installable Workspace and Offline Shell

ParsRAG can be installed as a progressive web app from the local web origin.
The manifest provides a stable identity, standalone display, and raster icons
derived from the project mark. Production builds generate a versioned service
worker from the emitted Vite assets. Development builds do not register it, so
hot reload and API proxying remain predictable.

The service worker precaches only the application shell and its static files.
Navigations to the workspace use the network when available and fall back to
the shell when disconnected. It never intercepts or caches model configuration,
health, ingestion, query, session, or other API responses. Conversations remain
in the existing browser storage; indexed vectors and model execution still
require the local service. The offline shell must therefore communicate an
unavailable service instead of pretending that document questions work offline.

A new worker waits while an older version is in use. The interface offers an
explicit reload after an update is ready and disables that action during an
upload or answer. Activation removes only old ParsRAG shell caches. The PWA
does not add another server-side store or increase model memory usage.
