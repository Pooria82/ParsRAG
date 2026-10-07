# Blueprint: Data Flow

Layer-by-layer sequences for the main flows. Lanes follow the backend layers
in [ARCHITECTURE.md](../../ARCHITECTURE.md#3-backend-layers): HTTP adapter →
use case → ports → driven adapters. Related blueprints:
[use cases](use-cases.md) and [DTOs](dtos.md).

## Layer map

```mermaid
flowchart LR
    subgraph L1[1 · Driving adapter]
        R[Route] --> D[Depends: composition root]
    end
    subgraph L2[2 · Application]
        UC[Use case]
    end
    subgraph L3[3 · Domain]
        P[Policies, entities, errors]
        S[Strategies, services]
    end
    subgraph L4[4 · Ports]
        PT[Protocols]
    end
    subgraph L5[5 · Driven adapters]
        A[Qdrant, parsers, OCR, model gateway]
    end
    D --> UC
    UC --> P
    UC --> S
    UC --> PT
    S --> PT
    A -. implements .-> PT
```

Data crosses each boundary as a DTO or entity, never as a framework object:
`UploadFile` becomes `IncomingFile`, a request body becomes a validated input
DTO, and Qdrant points become `ExtractedNode` entities.

## Ingestion: `POST /ingest`

```mermaid
sequenceDiagram
    autonumber
    participant B as Browser
    participant MW as Middleware
    participant R as routes.ingest_document
    participant UC as IngestDocuments
    participant V as file_validation
    participant DP as DocumentParser<br>(LocalDocumentParser)
    participant TC as TextChunker<br>(SentenceWindowChunker)
    participant DR as DocumentRepository<br>(QdrantRepository)

    B->>MW: multipart files + session_id
    MW->>MW: trusted origin, body ≤ PARSRAG_MAX_REQUEST_BYTES
    MW->>R: request (correlation ID bound)
    R->>R: require_runtime_ready (503 while preparing)
    R->>UC: execute(IngestDocumentsCommand)
    UC->>UC: session ID, file count, duplicate names
    UC->>UC: reserve ingestion slot (429 if busy) and session lock
    UC->>DR: get_session_files(session)
    DR-->>UC: existing names (409 on clash)
    loop each file
        UC->>UC: read_bounded (413 over file/batch budget)
        UC->>V: validate_upload(name, bytes)
        V-->>UC: ok or ValueError (400)
        UC->>DP: parse(bytes, name)
        DP-->>UC: ParsedSection[] (OCR inside adapter)
        loop each section
            UC->>TC: chunk(text, metadata)
            UC->>TC: bridge(previous, current) for adjacent pages
            UC->>DR: save_nodes(chunks, session)
            DR->>DR: embed in batches, upsert points
        end
    end
    UC-->>R: MessageResponse
    R-->>B: 200 {"message": "... (N chunks)."}
```

## Question answering: `POST /query`

```mermaid
sequenceDiagram
    autonumber
    participant B as Browser
    participant R as routes.query_rag
    participant UC as AnswerQuery
    participant PG as ProgressTracker
    participant QC as QuestionCondenser
    participant ST as QueryStrategy
    participant DR as DocumentRepository
    participant M as LLM (Settings.llm)

    B->>R: QueryRequest (prompt, history, mode, session, request_id)
    R->>UC: execute(request)
    UC->>UC: reserve query slot (429 if busy)
    UC->>PG: stage = understanding
    UC->>QC: condense(prompt, history)
    QC->>M: rewrite follow-up (only if history)
    UC->>UC: resolve strategy for mode
    UC->>DR: session files (only for @{file} mentions)
    UC->>ST: execute(query, history, session, top_k, filter, progress, segments)
    alt Strict or Hybrid
        ST->>PG: stage = retrieving
        ST->>DR: similarity_search (session-filtered, per file)
        ST->>ST: evidence gate (Strict) or rerank (Hybrid)
    end
    ST->>PG: stage = generating
    ST->>M: complete(prompt with grouped context)
    ST-->>UC: QueryResponse(answer, source_nodes)
    UC->>PG: stage = complete (failed on any error)
    UC-->>R: QueryResponse
    R-->>B: 200 answer + citations
    par while waiting
        B->>R: GET /queries/{request_id}/progress
        R-->>B: {"stage": "..."}
    end
```

## Document reuse: `POST /sessions/{id}/files/reuse`

```mermaid
sequenceDiagram
    autonumber
    participant B as Browser
    participant UC as ReuseDocument
    participant DR as DocumentRepository

    B->>UC: target session + ReuseDocumentRequest
    UC->>UC: target valid and different from source (400)
    UC->>UC: ingestion slot + locks on both sessions (sorted)
    UC->>DR: get_session_files(source) (404 if missing)
    UC->>DR: get_session_files(target) (409 duplicate, 400 full)
    UC->>DR: copy_document(source, target, filename)
    DR->>DR: scroll source points, upsert copies in pages
    UC-->>B: {"filename": ..., "chunks": N}
```

## Model configuration: `PUT /models/configuration`

```mermaid
sequenceDiagram
    autonumber
    participant B as Browser
    participant UC as ConfigureModel
    participant GW as ModelGateway<br>(LlamaIndexModelGateway)
    participant F as llm.factory
    participant EP as endpoint_policy

    B->>UC: ModelConfigurationRequest
    UC->>GW: configure(request)
    GW->>F: configure_model
    alt Ollama
        F->>F: loopback or internal host only
        F->>F: GET /api/tags
    else OpenAI-compatible API
        F->>EP: validate URL, block unsafe targets, HTTPS for public
        F->>F: external requires disclosure acknowledgement
        F->>F: GET /models
    end
    F->>F: persist non-secret settings, swap Settings.llm
    GW-->>UC: ModelConfigurationResponse (no key)
    Note over GW,UC: any client or validation failure becomes ModelConnectionError
    UC-->>B: 200, or 400 "could not be verified or saved"
```

## Startup and readiness

```mermaid
sequenceDiagram
    autonumber
    participant P as Process
    participant T as Init thread
    participant RS as RuntimeState
    participant DR as QdrantRepository

    P->>RS: preparing
    P->>T: start (UI and /health/live already served)
    T->>T: setup_llm_and_embeddings
    T->>DR: connect, probe vector size, ensure collection + indexes
    alt success
        T->>RS: ready
    else any failure
        T->>RS: failed (logged, not exposed)
    end
    Note over RS: /health/ready → CheckReadiness → 200 ready / 503 preparing|failed
```
