# Runtime Trust and Data Boundaries

## Decision

ParsRAG 0.x is a single-user workstation application. Authentication and tenant
authorization are outside this boundary. The HTTP listener therefore binds to
loopback by default; LAN exposure is an explicit administrator choice with exact
browser origins.

Parsing, OCR, embeddings, Qdrant storage, and browser conversation history stay
on the workstation. Generation has three user-visible trust modes:

1. Local Ollama keeps model input on the workstation.
2. A private OpenAI-compatible endpoint sends prompts and retrieved excerpts to
   the configured corporate service.
3. An external OpenAI-compatible endpoint sends the same model input to a third
   party and requires an explicit disclosure acknowledgement.

API keys are runtime secrets. They may come from process environment or current
process memory, but are excluded from API responses, browser storage, logs, and
the persisted model configuration.

## Vector schema versioning

The default Qdrant collection name includes the first twelve hexadecimal digits
of the SHA-256 digest of `EMBED_MODEL_NAME`. Its vector size is derived from a
probe embedding and validated against existing collection metadata. Changing an
embedding model therefore creates a separate collection. Documents must be
re-ingested for the new model; old collections may be backed up or removed after
verification. `QDRANT_COLLECTION` is an operator override and retains strict
dimension validation.

## Consequences

- A shared corporate deployment needs an authenticated reverse proxy or a future
  multi-user product phase.
- External API privacy depends on the chosen operator's retention and training
  policy.
- Browser history and Qdrant storage must be backed up together for complete
  conversation recovery.
