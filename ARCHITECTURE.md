# Architecture

## Overview

AI Knowledge Base API is a multi-tenant SaaS backend that allows teams to upload documents, ask AI-powered questions against them, and analyze usage over time. It is built around three storage layers with distinct responsibilities, a background processing pipeline for document ingestion, and a real-time delivery layer for streaming responses.

---

## System Diagram

```
                        ┌─────────────────────────────────────────┐
                        │              Client Layer                │
                        │   REST Client · WebSocket · SSE Stream  │
                        └────────────────┬────────────────────────┘
                                         │
                        ┌────────────────▼────────────────────────┐
                        │           FastAPI Application            │
                        │                                          │
                        │  app/api/v1/                            │
                        │  ├── auth.py        JWT auth            │
                        │  ├── documents.py   upload + ingest     │
                        │  ├── chat.py        Q&A + history       │
                        │  ├── websocket.py   streaming chat      │
                        │  ├── search.py      semantic search     │
                        │  ├── workspace.py   RBAC management     │
                        │  ├── subscription.py plan management    │
                        │  ├── analytics.py   time-series + SSE  │
                        │  ├── usage.py       stats + history     │
                        │  └── admin.py       platform dashboard  │
                        └───┬──────────┬────────────┬────────────┘
                            │          │            │
              ┌─────────────▼──┐  ┌───▼──────┐ ┌──▼──────────────┐
              │  PostgreSQL    │  │ MongoDB  │ │     Redis        │
              │  (Neon)        │  │ (Atlas)  │ │    (Upstash)     │
              │                │  │          │ │                  │
              │ users          │  │ chunks   │ │ rate limit keys  │
              │ workspaces     │  │ embeddings│ │ search cache     │
              │ documents      │  │ chat_msgs│ │ Celery broker    │
              │ workspace_     │  │ usage_   │ │ live counters    │
              │   members      │  │   logs   │ │                  │
              │ subscriptions  │  │          │ │                  │
              └────────────────┘  └──────────┘ └──────────────────┘
                                                        │
                        ┌───────────────────────────────▼──────────┐
                        │            Celery Worker                  │
                        │                                           │
                        │  app/workers/tasks.py                     │
                        │  1. chunk_text() → overlapping windows   │
                        │  2. generate_embeddings_batch() → vectors│
                        │  3. store chunks in MongoDB               │
                        │  4. update document status in PostgreSQL  │
                        └───────────────────────────────────────────┘
                                         │
                        ┌────────────────▼────────────────────────┐
                        │          External Services               │
                        │                                          │
                        │  Anthropic Claude API  (Q&A generation) │
                        │  sentence-transformers (embeddings)      │
                        └──────────────────────────────────────────┘
```

---

## Storage Layer Responsibilities

Each database was chosen for what it does best. Mixing them deliberately rather than using one database for everything keeps each concern clean and independently scalable.

**PostgreSQL** holds all relational, transactional data — users, workspaces, documents, members, subscriptions. Everything that needs foreign keys, constraints, and ACID guarantees lives here. SQLAlchemy async + Alembic for schema migrations.

**MongoDB** holds all document-derived data — the text chunks, their vector embeddings, chat messages, and usage logs. These are naturally document-shaped, variable in size, and append-heavy. MongoDB's flexible schema and native array support make it a better fit than PostgreSQL for storing thousands of variable-length chunks per document.

**Redis** serves three distinct purposes: rate limiting (atomic INCR counters keyed by workspace + date), search result caching (5-minute TTL on semantic search results to avoid re-embedding identical queries), and Celery broker (task queue for document processing jobs). Using Redis for all three keeps infrastructure simple without adding a separate queue service.

---

## Request Flow: Document Upload

```
1. POST /api/v1/documents/?workspace_id=...
   │
2. FastAPI → get_workspace_access() → verify RBAC (editor+)
   │
3. Read file bytes → validate content_type and size (≤ 10MB)
   │
4. extract_text(bytes, content_type) → plain text
   │    PDF  → PyMuPDF
   │    DOCX → python-docx
   │    CSV  → csv.reader row join
   │    TXT  → decode UTF-8
   │
5. Truncate extracted text to 2,000,000 chars if necessary
   │
6. Check for existing document with same filename
   │    exists → increment version, set parent_document_id
   │    new    → version = 1
   │
7. INSERT Document(status=pending) into PostgreSQL → COMMIT
   │
8. process_document.delay(document_id, workspace_id, text, version)
   │    OperationalError (broker down) →
   │    UPDATE Document(status=failed) → 503
   │
9. Return 201 DocumentOut immediately
   │
   └── [async, Celery worker picks up task]
       │
10.    chunk_text(text, chunk_size=500, overlap=50)
       │    validates chunk_size > overlap > 0
       │    produces overlapping word windows
       │
11.    generate_embeddings_batch(chunks)
       │    sentence-transformers all-MiniLM-L6-v2
       │    384-dimensional float32 vectors
       │
12.    INSERT chunk documents into MongoDB
       │    fields: document_id, workspace_id, content, chunk_index,
       │            embedding (list[float]), version
       │
13.    UPDATE Document(status=completed) in PostgreSQL
```

---

## Request Flow: Chat Q&A

```
1. POST /api/v1/chat/
   │
2. get_workspace_access() → verify RBAC (viewer+)
   │
3. check_rate_limit(workspace_id, plan)
   │    Redis INCR key="rate:{workspace_id}:{date}"
   │    atomic — no check-then-act race condition
   │    429 if new_count > limit
   │
4. Fetch last 6 chat messages for conversation_id from MongoDB
   │    (3 turns of user/assistant history)
   │
5. retrieve_relevant_chunks(question, workspace_id)
   │    embed query → 384-dim vector
   │    fetch all chunks for workspace from MongoDB
   │    cosine similarity → top-k results
   │    Redis cache: key="search:{workspace_id}:{query_hash}"
   │
6. generate_answer(question, chunks, history)
   │    build system prompt with chunk context
   │    build messages array with conversation history
   │    POST https://api.anthropic.com/v1/messages
   │    timeout=30s
   │    TimeoutException    → LLMServiceError → 502
   │    HTTPStatusError 429 → LLMServiceError → 502
   │    HTTPStatusError 5xx → LLMServiceError → 502
   │    RequestError        → LLMServiceError → 502
   │    empty content[]     → LLMServiceError → 502
   │
7. INSERT ChatMessage into MongoDB
   │    fields: conversation_id, workspace_id, user_id,
   │            question, answer, sources, tokens_used, created_at
   │
8. Return 200 ChatResponse
```

---

## RBAC Model

Every workspace has exactly one owner (the user who created it). Additional members can be invited with one of three roles. Access checks happen in `app/api/deps.get_workspace_access()`, which is called at the start of every protected endpoint.

```
Owner
  └── full control: invite members, change roles, remove members,
      upload documents, delete documents, chat, search, view analytics

Editor
  └── upload documents, ingest URLs, delete documents, chat, search,
      view analytics, invite members (cannot change roles or remove others)

Viewer
  └── read-only: list documents, chat (query only), search, view analytics
      cannot upload, invite, or mutate anything
```

The check is implemented as a single helper to avoid duplicating the logic across endpoints:

```python
# app/api/deps.py
async def get_workspace_access(
    workspace_id: UUID,
    current_user: User,
    db: AsyncSession,
    min_role: MemberRole = MemberRole.viewer,
) -> tuple[Workspace, MemberRole]:
```

Owners always pass. Members are checked against the `workspace_members` table. Non-members get 403. Non-existent workspaces get 404.

---

## Rate Limiting

Rate limits are enforced per workspace per day using Redis atomic operations. The implementation avoids the classic check-then-act race condition by incrementing first and checking the result.

```python
new_count = await redis.incr(key)   # atomic — always returns distinct value
if new_count == 1:
    await redis.expire(key, 86400)  # set TTL only on first request of the day
if new_count > limit:
    return {"allowed": False}
```

If two concurrent requests arrive simultaneously, Redis guarantees they receive consecutive values (e.g. 9 and 10), not both receiving 9. This means the limit is never exceeded, even under concurrent load. Proven by `test_rate_limit_concurrent_requests_never_exceed_limit` which fires 20 concurrent requests against a limit of 10 using `asyncio.gather`.

| Plan | Daily limit |
|------|-------------|
| free | 10 queries |
| pro | 10,000 queries |

---

## Document Versioning

When a document is uploaded with a filename that already exists in the workspace, a new version is created rather than overwriting. The version chain is maintained via `parent_document_id`:

```
v1: Document(id=A, filename="report.pdf", version=1, parent_document_id=None)
v2: Document(id=B, filename="report.pdf", version=2, parent_document_id=A)
v3: Document(id=C, filename="report.pdf", version=3, parent_document_id=A)
```

All versions link back to the original root (v1), not to each other. This makes the version chain query simple: fetch all documents where `id == root_id OR parent_document_id == root_id`.

Each version's chunks in MongoDB include a `version` field, allowing future features to query chunks from a specific document version.

---

## Embedding and Retrieval

Documents are chunked into overlapping word windows (default 500 words, 50-word overlap). Overlap ensures that sentences split across chunk boundaries are still findable — a query about content at the boundary of two chunks will match at least one of them.

Embeddings are generated using `sentence-transformers/all-MiniLM-L6-v2`, a 384-dimensional model that balances quality and inference speed. The model is lazy-loaded on first use and cached in memory for the lifetime of the Celery worker process.

Retrieval uses cosine similarity computed in Python against all chunks for the workspace. This is a simple implementation appropriate for workspaces with up to a few thousand chunks. For larger scale, the natural upgrade path is to replace the in-process similarity search with a dedicated vector database (Pinecone, Weaviate, pgvector) while keeping the same interface.

---

## Real-time Delivery

Two real-time mechanisms serve different use cases:

**WebSocket (chat streaming)** — bidirectional connection used for chat. The client authenticates over the socket, sends questions, and receives answer tokens as they stream from Claude. The connection is held open for the duration of a chat session.

**Server-Sent Events (analytics streaming)** — unidirectional push used for live dashboard updates. The server polls Redis counters every 3 seconds and pushes JSON events to any connected client. SSE is simpler than WebSocket for one-way data because it works over plain HTTP and reconnects automatically.

---

## Error Handling Philosophy

Every failure point in the request path has a specific, informative HTTP status code rather than a generic 500. The key design decisions:

**Celery broker failure on upload** returns 503 (not 500) and marks the document `failed` in PostgreSQL before returning. Without this, the document would be silently orphaned in `pending` status with no recovery path.

**Anthropic API failures** return 502 (bad gateway) with a human-readable message. The original `httpx.HTTPStatusError` or `httpx.TimeoutException` is caught in `llm_service.py` and re-raised as `LLMServiceError`, which `chat.py` catches and converts to 502. This keeps error handling logic in the service layer, not scattered across endpoints.

**Rate limiter Redis failure** returns `allowed: True` with a high limit rather than blocking all requests. The reasoning: a Redis outage should not take down the chat feature entirely. Accepting a brief period of unthrottled requests during an outage is a deliberate tradeoff.

**Authorization** distinguishes between 403 (workspace exists, user is not a member) and 404 (workspace does not exist). The previous implementation returned 404 for both cases, which was both semantically wrong and an information leak (it allowed enumeration of workspace IDs by observing which 404s vs 403s were returned).

---

## Project Structure

```
app/
├── main.py                     FastAPI app, lifespan, router registration
├── api/
│   ├── deps.py                 Shared dependencies: auth, RBAC helper
│   ├── scripts/
│   │   └── create_indexes.py   MongoDB index creation (run once)
│   └── v1/
│       ├── admin.py            Platform dashboard (admin only)
│       ├── analytics.py        Time-series, top docs, SSE stream
│       ├── auth.py             Register, login
│       ├── chat.py             Q&A, conversation history
│       ├── documents.py        Upload, ingest URL, versioning
│       ├── search.py           Semantic search
│       ├── subscription.py     Plan management
│       ├── usage.py            Stats, query history
│       ├── websocket.py        Streaming chat
│       └── workspace.py        Members, roles, invites
├── core/
│   ├── config.py               Settings from environment variables
│   └── security.py             JWT encode/decode, password hashing
├── db/
│   ├── postgres.py             SQLAlchemy async engine, session factory
│   ├── mongodb.py              Motor async client
│   └── redis.py                Redis async client
├── models/
│   ├── sql/                    SQLAlchemy ORM models
│   │   ├── user.py
│   │   ├── workspace.py
│   │   ├── workspace_member.py
│   │   ├── document.py
│   │   └── subscription.py
│   └── nosql/                  Pydantic models for MongoDB documents
│       ├── chat_message.py
│       ├── chunk.py
│       └── usage_log.py
├── schemas/                    Pydantic request/response schemas
│   ├── auth.py
│   ├── chat.py
│   ├── document.py
│   ├── user.py
│   └── workspace.py
├── services/                   Business logic, no HTTP concerns
│   ├── chunking_service.py     Text splitting with overlap
│   ├── document_processor.py   PDF/DOCX/CSV/URL text extraction
│   ├── embedding_service.py    sentence-transformers inference
│   ├── llm_service.py          Anthropic API call + error handling
│   ├── rate_limiter.py         Redis atomic rate limiting
│   └── retrieval_service.py    Cosine similarity search
└── workers/
    └── tasks.py                Celery task: chunk + embed + store
```

---

## CI/CD Pipeline

```
git push origin main
        │
        ▼
GitHub Actions (.github/workflows/ci.yml)
        │
        ├── Spin up services
        │   ├── postgres:16-alpine
        │   ├── mongo:7
        │   └── redis:7-alpine
        │
        ├── pip install -r requirements.txt -r requirements-dev.txt
        │
        ├── pytest -v  (176 tests, ~60 seconds)
        │   └── fail → pipeline stops, no image built
        │
        └── on pass + branch == main:
            ├── docker/setup-buildx-action
            ├── docker/login-action (DOCKERHUB_TOKEN secret)
            └── docker/build-push-action
                ├── tag: momiyyee/ai-knowledgebase-api:latest
                └── tag: momiyyee/ai-knowledgebase-api:{git_sha}
```

---

## Deployment

Deployed on Render using the Docker runtime. Render pulls `momiyyee/ai-knowledgebase-api:latest` from Docker Hub on each deploy.

Managed external services used in production:
- **Neon** — serverless PostgreSQL, connection pooling via PgBouncer
- **MongoDB Atlas** — M0 free cluster, shared tier
- **Upstash Redis** — serverless Redis, TLS required (`rediss://`)
- **Anthropic** — Claude Haiku model for cost-effective inference

The Docker image uses a multi-stage build: a `builder` stage installs all dependencies into `/install`, and a `runtime` stage copies only the installed packages without build tools. CPU-only PyTorch (`torch+cpu`) is used since no GPU inference is needed, reducing the image from ~12GB to ~6GB.

---

## Notable Engineering Decisions

**1. Atomic rate limiting via Redis INCR**
The initial implementation used GET-check-INCR which has a TOCTOU race condition: two concurrent requests reading the same count could both pass the check and both increment, allowing the limit to be exceeded. Fixed by using INCR first (atomic at Redis server level) and checking the returned value. A concurrent load test with `asyncio.gather` proves the fix — 20 concurrent requests against a limit of 10 always result in exactly 10 allowed.

**2. Celery broker failure handling**
Without error handling, a Redis outage at upload time would commit a document row to PostgreSQL as `pending` and then crash with an unhandled `OperationalError`. The document would be permanently stuck in `pending` with no recovery path. Fixed by catching `OperationalError`, marking the document `failed`, and returning 503. The client can retry; the database stays consistent.

**3. LLM service error isolation**
Anthropic API failures (429, 529, timeout) previously propagated as unhandled exceptions, producing raw 500s. The fix introduces a `LLMServiceError` exception class raised by `llm_service.py` for all provider failures, which `chat.py` catches and converts to 502 Bad Gateway with a human-readable message. This keeps error handling in the service layer and gives clients actionable status codes.

**4. chunk_text infinite loop guard**
If `chunk_size <= overlap`, the step size `chunk_size - overlap` is zero or negative, and the while loop never terminates. The Celery worker would hang forever on that document, consuming a worker slot indefinitely. Fixed with an upfront validation that raises `ValueError` on bad parameters, failing fast instead of hanging silently.

**5. Authorization 403 vs 404 distinction**
The original upload and chat endpoints returned 404 for both "workspace does not exist" and "you are not a member of this workspace". This is an information leak: by observing which workspaces return 403 vs 404, a non-member could enumerate valid workspace IDs. Fixed by returning 404 only when the workspace genuinely does not exist, and 403 when it exists but the requesting user is not a member.