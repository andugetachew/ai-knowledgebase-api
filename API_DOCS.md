# API Documentation

**Base URL:** `https://ai-knowledgebase-api-m9ry.onrender.com`  
**Interactive Docs:** `/docs` (Swagger UI) · `/redoc` (ReDoc)  
**Version:** v1  
**Auth:** Bearer JWT — include `Authorization: Bearer <token>` on all protected endpoints.

---

## Authentication

### POST /api/v1/auth/register
Register a new user. Automatically creates a default workspace and a free-tier subscription.

**Request**
```json
{
  "email": "user@example.com",
  "password": "strongpassword123",
  "full_name": "Andualem Getachew",
  "workspace_name": "My Knowledge Base"
}
```

**Response 201**
```json
{
  "access_token": "eyJhbGci...",
  "token_type": "bearer",
  "workspace_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Errors:** 400 duplicate email, 422 validation failure.

---

### POST /api/v1/auth/login
Login and receive a JWT token.

**Request**
```json
{
  "email": "user@example.com",
  "password": "strongpassword123"
}
```

**Response 200**
```json
{
  "access_token": "eyJhbGci...",
  "token_type": "bearer"
}
```

**Errors:** 401 wrong credentials.

---

## Documents

### POST /api/v1/documents/?workspace_id={id}
Upload a document for processing. Requires editor role or above. Supported types: PDF, TXT, MD, CSV, DOCX. Max size: 10MB. Processing happens asynchronously via Celery — document status starts as `pending` and moves to `completed` or `failed`.

If a document with the same filename already exists in the workspace, a new version is created automatically.

**Request:** `multipart/form-data`
```
file: <binary>
workspace_id: 550e8400-e29b-41d4-a716-446655440000  (query param)
```

**Response 201**
```json
{
  "id": "doc-uuid",
  "workspace_id": "ws-uuid",
  "filename": "report.pdf",
  "file_type": "application/pdf",
  "file_size": 204800,
  "status": "pending",
  "version": 1,
  "parent_document_id": null,
  "chunk_count": null,
  "created_at": "2026-06-28T10:00:00Z"
}
```

**Errors:** 400 unsupported type or file too large, 403 insufficient role, 503 processing queue unavailable.

---

### POST /api/v1/documents/ingest-url
Ingest a web page as a document. Fetches URL content, strips HTML, and processes as plain text. Requires editor role or above.

**Request**
```json
{
  "url": "https://docs.example.com/guide",
  "workspace_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Response 201** — same schema as document upload.

**Errors:** 400 URL unreachable or invalid, 403 insufficient role, 503 processing queue unavailable.

---

### GET /api/v1/documents/?workspace_id={id}
List all documents in a workspace. Requires viewer role or above.

**Response 200**
```json
{
  "total": 3,
  "documents": [
    {
      "id": "doc-uuid",
      "filename": "report.pdf",
      "file_type": "application/pdf",
      "file_size": 204800,
      "status": "completed",
      "version": 2,
      "chunk_count": 47,
      "created_at": "2026-06-28T10:00:00Z"
    }
  ]
}
```

---

### GET /api/v1/documents/{document_id}/versions
Get all versions of a document. Returns versions sorted oldest to newest. Requires viewer role or above.

**Response 200** — array of document objects, each with `version` field.

---

### DELETE /api/v1/documents/{document_id}
Delete a document. Requires editor role or above.

**Response 204** No content.

**Errors:** 403 insufficient role, 404 not found.

---

## Chat

### POST /api/v1/chat/
Ask a question against the workspace knowledge base. Uses semantic search to retrieve relevant document chunks, then generates an answer using Claude AI. Supports multi-turn conversation memory. Respects subscription rate limits (free: 10/day, pro: unlimited). Requires viewer role or above.

**Request**
```json
{
  "question": "What are the key findings in the Q3 report?",
  "workspace_id": "550e8400-e29b-41d4-a716-446655440000",
  "conversation_id": "optional-existing-conversation-id"
}
```

**Response 200**
```json
{
  "answer": "The Q3 report highlights three key findings...",
  "sources": ["doc-uuid-1", "doc-uuid-2"],
  "tokens_used": 847,
  "conversation_id": "conv-uuid"
}
```

**Errors:** 403 insufficient role, 429 daily rate limit exceeded, 502 AI service temporarily unavailable.

---

### WS /api/v1/ws/chat/{workspace_id}
Real-time streaming chat via WebSocket. Streams answer tokens as they are generated.

**Connection:** `ws://host/api/v1/ws/chat/{workspace_id}`

**Step 1 — Authenticate**
```json
{"token": "eyJhbGci..."}
```

**Step 2 — Send question**
```json
{
  "question": "Summarize the main points",
  "conversation_id": "optional"
}
```

**Step 3 — Receive stream**
```json
{"type": "token", "content": "The "}
{"type": "token", "content": "main "}
{"type": "token", "content": "points "}
{"type": "done", "sources": ["doc-uuid"], "tokens_used": 312, "conversation_id": "conv-uuid"}
```

**Error frames**
```json
{"type": "error", "message": "Daily query limit reached"}
```

---

### GET /api/v1/chat/conversations/{workspace_id}
List all conversation threads in a workspace, sorted by most recent activity. Returns up to 20 conversations. Requires viewer role or above.

**Response 200**
```json
[
  {
    "conversation_id": "conv-uuid",
    "last_question": "What are the key findings?",
    "last_message_at": "2026-06-28T11:30:00Z",
    "message_count": 6
  }
]
```

---

### GET /api/v1/chat/conversations/{workspace_id}/{conversation_id}
Get full message history for a conversation. Returns up to 100 messages sorted oldest first. Requires viewer role or above.

**Response 200**
```json
[
  {
    "question": "What does the document say about X?",
    "answer": "According to the document...",
    "sources": ["doc-uuid"],
    "tokens_used": 423,
    "created_at": "2026-06-28T10:15:00Z"
  }
]
```

---

## Search

### POST /api/v1/search/
Semantic search across all documents in a workspace. Uses cosine similarity against sentence-transformer embeddings. Results are cached in Redis for 5 minutes. Requires viewer role or above.

**Request**
```json
{
  "query": "quarterly revenue targets",
  "workspace_id": "550e8400-e29b-41d4-a716-446655440000",
  "top_k": 5
}
```

**Response 200**
```json
{
  "results": [
    {
      "document_id": "doc-uuid",
      "filename": "Q3_report.pdf",
      "content": "Revenue targets for Q3 were set at...",
      "score": 0.89,
      "chunk_index": 12
    }
  ],
  "total": 5,
  "query": "quarterly revenue targets"
}
```

---

## Workspaces

### GET /api/v1/workspaces/
List all workspaces the current user owns or is a member of.

**Response 200**
```json
[
  {
    "id": "ws-uuid",
    "name": "My Knowledge Base",
    "owner_id": "user-uuid",
    "created_at": "2026-06-01T00:00:00Z"
  }
]
```

---

### GET /api/v1/workspaces/{workspace_id}/members
List all members of a workspace with their roles. Requires any workspace access.

**Response 200**
```json
[
  {
    "id": "member-uuid",
    "user_id": "user-uuid",
    "email": "colleague@example.com",
    "full_name": "Jane Smith",
    "role": "editor",
    "created_at": "2026-06-10T00:00:00Z"
  }
]
```

---

### POST /api/v1/workspaces/{workspace_id}/members
Invite a user to the workspace by email. Requires owner or editor role.

**Request**
```json
{
  "email": "colleague@example.com",
  "role": "editor"
}
```

Roles: `viewer` (read-only), `editor` (upload + chat), `owner` (full control).

**Response 201**
```json
{"message": "colleague@example.com added as editor"}
```

**Errors:** 400 already a member or inviting yourself, 403 insufficient role, 404 user not found.

---

### PATCH /api/v1/workspaces/{workspace_id}/members/{user_id}
Update a member's role. Owner only.

**Request**
```json
{"role": "viewer"}
```

**Response 200**
```json
{"message": "Role updated to viewer"}
```

---

### DELETE /api/v1/workspaces/{workspace_id}/members/{user_id}
Remove a member from the workspace. Owner can remove anyone. Members can remove themselves.

**Response 204** No content.

---

## Subscription

### GET /api/v1/subscription/{workspace_id}
Get current subscription plan and usage for the day.

**Response 200**
```json
{
  "workspace_id": "ws-uuid",
  "plan": "free",
  "queries_today": 4,
  "daily_limit": 10,
  "remaining": 6
}
```

---

### PATCH /api/v1/subscription/{workspace_id}
Upgrade or downgrade the workspace plan. Owner only.

**Request**
```json
{"plan": "pro"}
```

Plans: `free` (10 queries/day), `pro` (10,000 queries/day).

**Response 200**
```json
{"message": "Plan updated to pro"}
```

---

## Analytics

### GET /api/v1/analytics/{workspace_id}/queries-over-time
Time-series query counts. Accepts a `period` query param (e.g. `7d`, `24h`, `30d`). Groups by hour for periods ≤ 2 days, by day otherwise.

**Response 200**
```json
{
  "workspace_id": "ws-uuid",
  "period": "7d",
  "granularity": "day",
  "buckets": [
    {"bucket": "2026-06-21", "query_count": 12, "total_tokens": 8400},
    {"bucket": "2026-06-22", "query_count": 19, "total_tokens": 13300}
  ]
}
```

---

### GET /api/v1/analytics/{workspace_id}/top-documents
Most frequently referenced documents across all chat queries. Accepts `limit` param (default 10, max 100).

**Response 200**
```json
{
  "workspace_id": "ws-uuid",
  "top_documents": [
    {"source": "doc-uuid", "reference_count": 34}
  ]
}
```

---

### GET /api/v1/analytics/{workspace_id}/performance
Aggregate performance metrics for the workspace. Accepts `period` param.

**Response 200**
```json
{
  "workspace_id": "ws-uuid",
  "period": "7d",
  "total_queries": 87,
  "avg_tokens_per_query": 412.5,
  "total_tokens": 35887
}
```

---

### GET /api/v1/analytics/{workspace_id}/live
Current live activity counters from Redis.

**Response 200**
```json
{
  "workspace_id": "ws-uuid",
  "active_queries_last_hour": 7
}
```

---

### GET /api/v1/analytics/{workspace_id}/stream
Server-Sent Events stream. Pushes live query counts every 3 seconds. Connect with an `EventSource` in the browser or any SSE client.

**Event format**
```
data: {"workspace_id": "ws-uuid", "active_queries_last_hour": 7, "timestamp": "2026-06-28T11:00:00Z"}

data: {"workspace_id": "ws-uuid", "active_queries_last_hour": 8, "timestamp": "2026-06-28T11:00:03Z"}
```

---

## Usage

### GET /api/v1/usage/{workspace_id}/stats
Workspace usage statistics.

**Response 200**
```json
{
  "workspace_id": "ws-uuid",
  "total_queries": 247,
  "total_tokens": 184500,
  "total_documents": 12,
  "queries_today": 4
}
```

---

### GET /api/v1/usage/{workspace_id}/history
Paginated query history. Accepts `limit` (default 20) and `offset` params.

**Response 200**
```json
{
  "total": 247,
  "history": [
    {
      "question": "What are the revenue targets?",
      "answer": "According to the Q3 report...",
      "tokens_used": 412,
      "sources": ["doc-uuid"],
      "created_at": "2026-06-28T10:00:00Z"
    }
  ]
}
```

---

## Admin

All admin endpoints require the requesting user to be a platform admin (first registered user or flagged in the database).

### GET /api/v1/admin/dashboard
Platform-wide statistics.

**Response 200**
```json
{
  "total_users": 142,
  "total_workspaces": 98,
  "total_documents": 1847,
  "total_queries": 28491,
  "free_plan_count": 121,
  "pro_plan_count": 21,
  "token_trends": [
    {"date": "2026-06-21", "total_tokens": 84200}
  ]
}
```

---

### GET /api/v1/admin/workspaces
All workspaces with activity metrics.

### GET /api/v1/admin/users
All users with workspace counts.

### GET /api/v1/admin/stats/tokens?days=7
Token usage trends over N days.

---

## Monitoring

### GET /health
Service health check. Returns status of all three databases.

**Response 200**
```json
{
  "postgres": "connected",
  "mongo": "connected",
  "redis": "connected"
}
```

---

### GET /metrics
Prometheus metrics endpoint. Compatible with any Prometheus scraper.

Key metrics exposed:
- `http_requests_total` — request count by handler, method, and status code
- `http_request_duration_seconds` — response latency histogram per endpoint
- `http_request_size_bytes` — incoming request size
- `http_response_size_bytes` — outgoing response size
- `process_resident_memory_bytes` — current memory usage
- `process_cpu_seconds_total` — cumulative CPU time

---

## Error Reference

| Status | Meaning |
|--------|---------|
| 400 | Bad request — invalid input, unsupported file type, duplicate member |
| 401 | Unauthorized — missing or invalid JWT token |
| 403 | Forbidden — authenticated but insufficient role |
| 404 | Not found — resource does not exist |
| 422 | Validation error — request body failed schema validation |
| 429 | Too many requests — daily query limit reached |
| 502 | Bad gateway — AI service (Anthropic) temporarily unavailable |
| 503 | Service unavailable — document processing queue (Celery/Redis) unreachable |

All error responses follow this shape:
```json
{"detail": "Human-readable error message"}
```