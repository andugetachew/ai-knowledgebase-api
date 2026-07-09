# AI Knowledge Base API

![Stripe](https://img.shields.io/badge/Stripe-test%20mode-635bff?logo=stripe&logoColor=white)
![Coverage](https://img.shields.io/badge/coverage-93%25-brightgreen)
![Tests](https://img.shields.io/badge/tests-210%20passed-brightgreen)
![Python](https://img.shields.io/badge/python-3.12-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-async-009688?logo=fastapi)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-blue)
![MongoDB](https://img.shields.io/badge/MongoDB-7-green)
![Redis](https://img.shields.io/badge/Redis-7-red)
![Celery](https://img.shields.io/badge/Celery-enabled-green)
![Docker](https://img.shields.io/badge/Docker-enabled-blue)

[![CI](https://github.com/andugetachew/ai-knowledgebase-api/actions/workflows/ci.yml/badge.svg)](https://github.com/andugetachew/ai-knowledgebase-api/actions)
[![Run in Postman](https://run.pstmn.io/button.svg)](https://github.com/andugetachew/ai-knowledgebase-api/blob/main/postman_collection.json)

## 🌐 Live Demo

| | URL |
|--|--|
| **API Base** | https://ai-knowledgebase-api-m9ry.onrender.com |
| **Swagger Docs** | https://ai-knowledgebase-api-m9ry.onrender.com/docs |
| **ReDoc** | https://ai-knowledgebase-api-m9ry.onrender.com/redoc |
| **Health Check** | https://ai-knowledgebase-api-m9ry.onrender.com/health |

> ⚠️ Hosted on Render free tier — first request may take 50 seconds to wake up.

## 📊 Quality Metrics

- 210 automated tests
- 93% code coverage on app code
- Concurrency regression tests included
- Unit + integration + security test layers

A production-grade AI-powered document Q&A SaaS API built with FastAPI that supports multi-workspace team collaboration, JWT authentication, semantic search, real-time streaming chat, Stripe billing, S3 file storage, and background document processing.

Built to demonstrate real-world backend engineering skills including async architecture, multi-tenant workspace isolation, distributed task processing, AI integration, and production deployment patterns.

---

## 📸 API Documentation Preview

> Full interactive documentation available at `/docs` — supports JWT authentication directly in the browser.

### Overview & Auth
![Swagger Overview](docs/swagger1.png)

### Documents & Chat
![Documents and Chat](docs/swagger2.png)

### Health Check
![Health Check](docs/health.png)

---

## 🚀 Key Highlights

- Multi-workspace architecture with role-based access control (owner/editor/viewer)
- JWT authentication with password reset via email and workspace invite emails
- Real document processing — PDF, DOCX, CSV, web URL ingestion with text extraction
- Document versioning — re-upload same filename creates v2, tracks parent chain
- AI-powered Q&A using Claude API with multi-turn conversation memory
- Real-time streaming chat via WebSocket — tokens streamed as they generate
- Semantic search with cosine similarity against sentence-transformer embeddings
- Redis caching for search results and live analytics counters
- Atomic rate limiting with Redis INCR — no race conditions under concurrent load
- Stripe billing — checkout sessions, webhook-driven plan activation
- S3-compatible file storage — upload persistence, presigned download URLs
- Background document processing with Celery — chunk, embed, store asynchronously
- Real-time analytics — time-series queries, SSE streaming, document performance
- Admin dashboard API — platform-wide stats, token trends, workspace activity
- Prometheus metrics + Grafana dashboard + Sentry error tracking + UptimeRobot
- 210 automated tests with 93% coverage

---

## 🛠 Tech Stack

| Layer | Technology |
|-------|-----------|
| Framework | FastAPI (fully async) |
| Auth | JWT (python-jose) + bcrypt |
| SQL DB | PostgreSQL 16 + SQLAlchemy + Alembic |
| NoSQL DB | MongoDB 7 (Motor async) |
| Cache & Broker | Redis 7 + Celery |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) |
| AI | Anthropic Claude API (claude-haiku) |
| Payments | Stripe (checkout + webhooks) |
| Email | Gmail SMTP via aiosmtplib |
| File Storage | S3-compatible (boto3 + MinIO) |
| Real-Time | WebSocket + Server-Sent Events (SSE) |
| Containerization | Docker multi-stage + docker-compose |
| CI/CD | GitHub Actions + Docker Hub |
| Deployment | Render (Docker runtime) |
| Monitoring | Prometheus + Grafana + Sentry + UptimeRobot |

---

## 📁 Project Structure
app/
├── api/v1/
│   ├── auth.py           # JWT auth, password reset (Redis tokens)
│   ├── documents.py      # Upload, ingest URL, versioning, S3 storage
│   ├── chat.py           # Q&A, conversation memory, RBAC
│   ├── websocket.py      # Streaming chat via WebSocket
│   ├── search.py         # Semantic search + Redis cache
│   ├── workspace.py      # Members, roles, invite emails
│   ├── subscription.py   # Plan management
│   ├── checkout.py       # Stripe checkout sessions
│   ├── stripe_webhook.py # Stripe webhook handler
│   ├── analytics.py      # Time-series, SSE stream, live counters
│   ├── usage.py          # Stats + query history
│   └── admin.py          # Platform dashboard
├── services/
│   ├── llm_service.py       # Claude API + error isolation
│   ├── embedding_service.py # sentence-transformers inference
│   ├── retrieval_service.py # Cosine similarity search
│   ├── chunking_service.py  # Overlapping word windows
│   ├── document_processor.py # PDF/DOCX/CSV/URL extractors
│   ├── storage_service.py   # S3-compatible upload/download
│   ├── rate_limiter.py      # Atomic Redis INCR rate limiting
│   └── email_service.py     # Password reset + invite emails
├── models/
│   ├── sql/              # SQLAlchemy ORM (users, workspaces, documents, subscriptions)
│   └── nosql/            # Pydantic models (chunks, chat messages, usage logs)
├── workers/
│   └── tasks.py          # Celery: chunk → embed → store → update status
└── main.py               # App factory, Sentry init, Prometheus

---

## 🏢 Multi-Workspace Architecture

Every user registers with a workspace. Additional users can be invited to join a workspace with one of three roles. All data (documents, chat, analytics) is scoped to the workspace and enforced by a shared `get_workspace_access` dependency called at the start of every protected endpoint.

### Role-Based Access Control

| Role | Documents | Chat | Search | Analytics | Members |
|------|-----------|------|--------|-----------|---------|
| Owner | Full | Full | Full | Full | Full |
| Editor | Upload/Delete | Full | Full | Full | Invite |
| Viewer | Read-only | Full | Full | Full | No |

---

## 🔐 Authentication & Authorization

- Register → creates user + workspace + free subscription in one transaction
- JWT access tokens — signed with `HS256`, validated on every request
- Password reset — token stored in Redis with 1-hour TTL, one-time use, invalidated after use
- Workspace invites — email sent via Gmail SMTP with role assignment
- RBAC enforced via `get_workspace_access(min_role=...)` dependency

---

## 📁 Core Modules

### Documents
- Upload PDF, DOCX, CSV, TXT — text extracted per format
- Ingest web URLs — fetched, HTML stripped, processed as plain text
- File persisted to S3-compatible storage — presigned download URLs valid 1 hour
- Versioning — same filename → new version with parent chain tracking
- Processing async via Celery — chunk → embed → store in MongoDB → update status
- Celery failure handled — document marked `failed`, 503 returned, no orphaned rows

### Chat
- Ask questions against the workspace knowledge base
- Claude API generates answers from retrieved chunks
- Multi-turn conversation memory — last 3 turns included as context
- Rate limited per workspace per day (free: 10, pro: 10,000)
- All Anthropic failures (429/529/timeout) caught and returned as 502

### Search
- Semantic search using cosine similarity against 384-dim embeddings
- Results cached in Redis for 5 minutes per query
- Configurable `top_k` results

### Analytics
- Time-series query counts grouped by day or hour
- Most referenced documents across all chat queries
- Performance metrics — total queries, average tokens, total tokens
- Live counters from Redis
- SSE stream endpoint — pushes updates every 3 seconds

### Billing
- Stripe Checkout integration — self-serve upgrades via Stripe-hosted page
- Webhook-driven plan activation — `checkout.session.completed` updates subscription
- Subscription cancelled → auto-downgrade to free via `customer.subscription.deleted`
- Plans: Free (10 queries/day), Pro (10,000 queries/day)

### Monitoring
- Prometheus metrics at `/metrics` — request counts, latency, memory
- Grafana dashboard for API request rate visualization
- Sentry — real-time error tracking with FastAPI + SQLAlchemy integrations
- UptimeRobot — 5-minute health check pings, email alerts on downtime

---

## 📡 API Endpoints

| Module | Endpoint | Methods |
|--------|----------|---------|
| Auth | `/api/v1/auth/register` | POST |
| Auth | `/api/v1/auth/login` | POST |
| Auth | `/api/v1/auth/forgot-password` | POST |
| Auth | `/api/v1/auth/reset-password` | POST |
| Documents | `/api/v1/documents/` | GET, POST |
| Documents | `/api/v1/documents/ingest-url` | POST |
| Documents | `/api/v1/documents/{id}/versions` | GET |
| Documents | `/api/v1/documents/{id}/download-url` | GET |
| Documents | `/api/v1/documents/{id}` | DELETE |
| Chat | `/api/v1/chat/` | POST |
| Chat | `/api/v1/chat/conversations/{workspace_id}` | GET |
| Chat | `/api/v1/chat/conversations/{workspace_id}/{conv_id}` | GET |
| WebSocket | `/api/v1/ws/chat/{workspace_id}` | WS |
| Search | `/api/v1/search/` | POST |
| Workspaces | `/api/v1/workspaces/` | GET |
| Workspaces | `/api/v1/workspaces/{id}/members` | GET, POST, PATCH, DELETE |
| Subscription | `/api/v1/subscription/{workspace_id}` | GET, PATCH |
| Checkout | `/api/v1/checkout/{workspace_id}/pro` | POST |
| Checkout | `/api/v1/checkout/{workspace_id}/free` | POST |
| Webhooks | `/api/v1/webhooks/stripe` | POST |
| Analytics | `/api/v1/analytics/{workspace_id}/queries-over-time` | GET |
| Analytics | `/api/v1/analytics/{workspace_id}/top-documents` | GET |
| Analytics | `/api/v1/analytics/{workspace_id}/performance` | GET |
| Analytics | `/api/v1/analytics/{workspace_id}/live` | GET |
| Analytics | `/api/v1/analytics/{workspace_id}/stream` | GET (SSE) |
| Usage | `/api/v1/usage/{workspace_id}/stats` | GET |
| Usage | `/api/v1/usage/{workspace_id}/history` | GET |
| Admin | `/api/v1/admin/dashboard` | GET |
| Admin | `/api/v1/admin/workspaces` | GET |
| Admin | `/api/v1/admin/users` | GET |
| Admin | `/api/v1/admin/stats/tokens` | GET |
| Health | `/health` | GET |
| Metrics | `/metrics` | GET |

Full interactive documentation: `/docs`

---

## 💡 Example API Usage

**Register and get JWT token:**
```bash
curl -X POST https://ai-knowledgebase-api-m9ry.onrender.com/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "strongpassword123",
    "full_name": "Andualem Getachew",
    "workspace_name": "My Knowledge Base"
  }'
```

**Upload a document:**
```bash
curl -X POST "https://ai-knowledgebase-api-m9ry.onrender.com/api/v1/documents/?workspace_id=<id>" \
  -H "Authorization: Bearer <token>" \
  -F "file=@report.pdf"
```

**Ask a question:**
```bash
curl -X POST https://ai-knowledgebase-api-m9ry.onrender.com/api/v1/chat/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"question": "What are the key findings?", "workspace_id": "<id>"}'
```

---

## ⚡ Performance Strategy

### Redis Caching
- Search results — 5 min TTL per query hash
- Live analytics counters — real-time Redis INCR
- Rate limit keys — daily TTL per workspace

### Database Optimization
- MongoDB compound indexes on `(conversation_id, created_at)` and `(workspace_id, created_at)`
- PostgreSQL foreign key indexes on all relations
- Async SQLAlchemy throughout — no blocking DB calls

### Document Processing
- Text extraction capped at 2,000,000 characters before chunking
- Overlapping word windows (500 words, 50-word overlap) for boundary coverage
- Embeddings generated in batches inside Celery worker

---

## 🔌 Real-Time Architecture
Client (WebSocket)
↓
FastAPI / Uvicorn
↓
WebSocket Handler
↓
Claude API (SSE stream)
↓
Token frames → client
Client (SSE)
↓
FastAPI / Uvicorn
↓
Analytics SSE endpoint
↓
Redis poll every 3s → event frames → client
---

## ⚙️ Background Processing (Celery)

Async tasks handled by Celery workers with Redis as broker:

- Document chunking — split text into overlapping word windows
- Embedding generation — sentence-transformers inference
- MongoDB storage — insert chunk documents with embeddings
- Status update — mark document `completed` or `failed` in PostgreSQL
- Retry on failure — up to 3 retries with 10 second delay

---

## 🔐 Security

- JWT with configurable expiry, validated on every request
- Workspace-level data isolation enforced at every endpoint
- RBAC permissions checked via shared dependency
- Atomic rate limiting — Redis INCR prevents concurrent request bypass
- Password reset tokens — one-time use, 1-hour TTL, stored in Redis
- Stripe webhook signature verification on every event
- S3 presigned URLs — time-limited direct file access
- No sensitive data in logs or error responses

---

## 🎯 Notable Engineering Decisions

**Atomic rate limiting** — initial implementation used GET-check-INCR which has a TOCTOU race condition under concurrent load. Fixed by using Redis INCR first (atomic at server level) and checking the result. Proven by a regression test firing 20 concurrent requests against a limit of 10 — always exactly 10 allowed.

**Celery broker failure handling** — without error handling, a Redis outage at upload time would commit a document row as `pending` with no recovery path. Fixed by catching `OperationalError`, marking the document `failed`, and returning 503. Client can retry; database stays consistent.

**LLM error isolation** — Anthropic API failures (429, 529, timeout, malformed response) are caught in `llm_service.py` and re-raised as `LLMServiceError`, converted to 502 Bad Gateway in the endpoint. Rate limit counter is not refunded — avoiding a second atomic operation that would reopen the race condition.

**Redis password reset tokens** — initial implementation stored tokens in a module-level dict, lost on server restart. Migrated to Redis with `setex` TTL — tokens expire automatically and survive restarts.

**Storage failure tolerance** — S3 upload failure is caught silently; document creation and Celery processing continue. A failed upload means no download URL but the document is still searchable and queryable.

**Authorization 403 vs 404** — original endpoints returned 404 for both "workspace does not exist" and "not a member," enabling workspace ID enumeration. Fixed to return 404 only when workspace genuinely does not exist, 403 when it exists but requester is not a member.

---

## 🧪 Testing

```bash
# Run full test suite
pytest -v

# With coverage report
pytest --cov=app --cov-report=term-missing
```

### Test Coverage: 93% (210 tests)

| Test Category | Status |
|--------------|--------|
| Authentication & JWT | ✅ 10 tests |
| Password Reset (Redis) | ✅ 8 tests |
| Workspace RBAC | ✅ 23 tests |
| Document Upload & Processing | ✅ 20 tests |
| Document Versioning | ✅ 6 tests |
| Document Pipeline Robustness | ✅ 9 tests |
| Chat & Conversation Memory | ✅ 12 tests |
| WebSocket Streaming | ✅ 9 tests |
| Semantic Search | ✅ 8 tests |
| Rate Limiter (concurrency) | ✅ 4 tests |
| LLM Service Error Handling | ✅ 10 tests |
| Analytics & SSE | ✅ 13 tests |
| Usage & History | ✅ 11 tests |
| Admin Dashboard | ✅ 12 tests |
| Subscription & Billing | ✅ 10 tests |
| Stripe Checkout & Webhooks | ✅ 9 tests |
| Email (reset + invites) | ✅ 10 tests |
| S3 File Storage | ✅ 9 tests |
| Celery Tasks | ✅ 5 tests |
| NoSQL Models | ✅ 5 tests |

---

## 📦 Local Setup

```bash
git clone https://github.com/andugetachew/ai-knowledgebase-api
cd ai-knowledgebase-api

cp .env.example .env.docker
# Fill in your values

docker compose up -d
docker compose exec api alembic upgrade head
```

Access points:
- API: `http://localhost:8000`
- Swagger Docs: `http://localhost:8000/docs`
- Metrics: `http://localhost:8000/metrics`

---

## 🔑 Environment Variables

```env
SECRET_KEY=your-secret-key
ENVIRONMENT=development

DATABASE_URL=postgresql+asyncpg://...
MONGO_URL=mongodb+srv://...
MONGO_DB_NAME=ai_knowledgebase_mongo
REDIS_URL=redis://localhost:6379/0

ANTHROPIC_API_KEY=sk-ant-...

STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_FREE_PRICE_ID=price_...
STRIPE_PRO_PRICE_ID=price_...

EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=your@gmail.com
EMAIL_HOST_PASSWORD=your-app-password

S3_ENDPOINT_URL=http://localhost:9000
S3_ACCESS_KEY=minioadmin
S3_SECRET_KEY=minioadmin
S3_BUCKET=ai-knowledgebase-docs

SENTRY_DSN=https://...@sentry.io/...
```

---

## 🐳 Docker Services

```bash
docker compose up -d
```

| Service | Description | Port |
|---------|-------------|------|
| api | FastAPI + Uvicorn | 8000 |
| worker | Celery worker | — |
| postgres | PostgreSQL 16 | 5432 |
| mongo | MongoDB 7 | 27017 |
| redis | Cache + broker | 6379 |

---

## 📄 License

MIT

---

## 👨‍💻 Author

**Andualem Getachew**

[![GitHub](https://img.shields.io/badge/GitHub-andugetachew-black?logo=github)](https://github.com/andugetachew)
[![Email](https://img.shields.io/badge/Email-andugeta41%40gmail.com-red?logo=gmail)](mailto:andugeta41@gmail.com)