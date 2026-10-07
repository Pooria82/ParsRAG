# ADR 08: Ports, Use Cases, and Directional DTOs

## Context

Before 1.0.0 the backend already separated `api`, `core`, and `infrastructure`,
but three boundaries leaked:

- `backend/api/routes.py` contained ingestion, query, and session business
  rules (validation, limits, locking, page bridging, mention resolution), so
  those rules could only be tested through HTTP.
- `core` imported web frameworks: `WorkLimiter` raised FastAPI's
  `HTTPException`, and `core/security.py` held Starlette middleware.
- `core/models/domain.py` mixed domain entities (`ExtractedNode`) with API
  request/response models, and contracts lived in two places
  (`core/interfaces/` and `core/strategies/base_strategy.py`).

## Decision

Adopt a ports-and-adapters (hexagonal) layout inside the existing packages:

| Package | Responsibility | May import |
| --- | --- | --- |
| `core/domain` | Entities, enums, session rules, upload policy, errors | stdlib, Pydantic |
| `core/dto/input`, `core/dto/output` | Inbound commands/requests and outbound responses | `domain` |
| `core/port` | `typing.Protocol` contracts the core needs from adapters | `domain`, `dto` |
| `core/use_case/<module>` | One class per application operation | `domain`, `dto`, `port`, `runtime`, `service`, `strategies` |
| `core/strategies`, `core/service` | Strategy implementations and domain services | `domain`, `dto`, `port`, LlamaIndex |
| `core/runtime` | Process-local limiter, readiness, progress, locks, correlation | `domain` |
| `infrastructure/*` | Driven adapters (Qdrant, model factory/gateway, parsers, OCR) | `core` |
| `api` | Driving adapter: routes, middleware, error mapping, composition root | everything |

Rules:

1. **Dependency direction.** `core` never imports `api`, `infrastructure`,
   FastAPI, Starlette, Qdrant, httpx, or PyMuPDF. LlamaIndex primitives remain
   allowed in strategies and services because ADR 02 adopts LlamaIndex as the
   RAG toolkit and its global `Settings` registry.
2. **Ports are Protocols.** `DocumentRepository`, `QueryStrategy`,
   `DocumentParser`, `TextChunker`, `QuestionCondenser`, `ModelGateway`, and
   `ProgressTracker` are structural; adapters may also subclass them
   explicitly for discoverability. The `Protocol` helpers inside the PDF/OCR
   adapter only describe third-party objects and stay private to that adapter.
3. **DTOs are split by direction.** `dto/input` holds validated requests and
   commands; `dto/output` holds responses. Entities that are part of the public
   contract (`ExtractedNode` as a citation) are referenced, not duplicated.
4. **Use cases own business rules** and raise `ApplicationError` subclasses
   (`InvalidInputError`, `NotFoundError`, `ConflictError`,
   `PayloadTooLargeError`, `CapacityExceededError`, `UpstreamServiceError`).
   `api/errors.py` maps each to exactly one HTTP status; messages are unchanged
   from the previous HTTP contract.
5. **`api/dependencies.py` is the only composition root.** It builds use cases
   from adapters per request; model-bound collaborators (condenser, strategy)
   are created lazily so runtime model switches take effect immediately.

### Builder pattern (evaluated, not adopted)

A Builder was considered for model-client construction. Today there are two
providers (Ollama and OpenAI-compatible), each built in one call with a fixed
parameter set, and validation must happen before construction. A Builder would
add a mutable, multi-step object without removing branching or improving
compatibility handling. The factory plus the `ModelGateway` port already
isolates provider differences. Revisit when a third provider or per-provider
tuning options (retries, headers, context windows) make construction
genuinely multi-step.

## Consequences

- Business rules are unit-tested with in-memory port fakes
  (`backend/tests/core/use_case`), without FastAPI, Qdrant, or models.
- The HTTP contract (paths, status codes, JSON bodies, messages) is unchanged;
  the existing API tests pass with only patch targets updated. OpenAPI now
  documents typed response models for previously untyped endpoints.
- Session ID validation uses a full match, so a trailing newline is rejected.
- `get_query_strategy` reuses the pooled repository instead of opening a new
  Qdrant client when no repository is injected.
- New features add a use case, any missing port, and an adapter; routes stay
  thin translations.
