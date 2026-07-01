# AI Knowledge Base API

> Production-grade intelligent document Q&A SaaS API built with FastAPI, PostgreSQL, MongoDB, Redis, and Claude AI

[![CI](https://github.com/andugetachew/ai-knowledgebase-api/actions/workflows/ci.yml/badge.svg)](https://github.com/andugetachew/ai-knowledgebase-api/actions)

**Live URLs:**
- API: https://ai-knowledgebase-api-m9ry.onrender.com
- Docs: https://ai-knowledgebase-api-m9ry.onrender.com/docs
- Health: https://ai-knowledgebase-api-m9ry.onrender.com/health

---

## Features

- JWT authentication with workspace isolation
- Multi-workspace team collaboration with role-based access (owner/editor/viewer)
- Real document processing — PDF, DOCX, CSV, web URL ingestion
- Document versioning — upload v2, track which version chunks came from
- AI-powered Q&A using Claude API with multi-turn conversation memory
- Real-time streaming chat via WebSocket
- Semantic search with cosine similarity and Redis caching
- Rate limiting and subscription tiers (free: 10/day, pro: unlimited)
- Real-time analytics — time-series queries, document performance, SSE streaming
- Admin dashboard API — platform-wide stats, token trends, workspace activity
- Background document processing with Celery
- Prometheus metrics at /metrics
- 176 passing tests, 93% coverage on app code

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Framework | FastAPI (async) |
| Auth | JWT (python-jose) |
| SQL DB | PostgreSQL + SQLAlchemy + Alembic |
| NoSQL DB | MongoDB (Motor async) |
| Cache/Queue | Redis + Celery |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) |
| AI | Anthropic Claude API (claude-haiku) |
| Containers | Docker multi-stage + docker-compose |
| CI/CD | GitHub Actions + Docker Hub |
| Deployment | Render (Docker runtime) |
| Monitoring | Prometheus + Grafana |

---

## Architecture
Client → FastAPI → PostgreSQL (users, workspaces, documents, subscriptions)

→ MongoDB (chunks, embeddings, chat history, analytics)

→ Redis (cache, rate limiting, Celery broker)

→ Claude API (Q&A, multi-turn conversation)

→ Celery Worker (async chunking + embedding)

---

## API Endpoints

### Auth
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/v1/auth/register | Register user + create workspace + subscription |
| POST | /api/v1/auth/login | Login, get JWT token |

### Documents
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/v1/documents/ | Upload document (PDF, DOCX, CSV, TXT) |
| POST | /api/v1/documents/ingest-url | Ingest web URL as document |
| GET | /api/v1/documents/ | List workspace documents |
| GET | /api/v1/documents/{id}/versions | Get all versions of a document |
| DELETE | /api/v1/documents/{id} | Delete document |

### Chat
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/v1/chat/ | Ask question with conversation memory |
| GET | /api/v1/chat/conversations/{workspace_id} | List conversation threads |
| GET | /api/v1/chat/conversations/{workspace_id}/{conversation_id} | Get conversation history |
| WS | /api/v1/ws/chat/{workspace_id} | Streaming chat via WebSocket |

### Search
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/v1/search/ | Semantic search across documents |

### Workspaces
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/v1/workspaces/ | List all workspaces (owned + member) |
| GET | /api/v1/workspaces/{id}/members | List workspace members |
| POST | /api/v1/workspaces/{id}/members | Invite member (owner/editor only) |
| PATCH | /api/v1/workspaces/{id}/members/{user_id} | Update member role (owner only) |
| DELETE | /api/v1/workspaces/{id}/members/{user_id} | Remove member |

### Subscription
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/v1/subscription/{workspace_id} | Get plan and usage |
| PATCH | /api/v1/subscription/{workspace_id} | Upgrade plan (free/pro) |

### Analytics
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/v1/analytics/{workspace_id}/queries-over-time | Time-series query data |
| GET | /api/v1/analytics/{workspace_id}/top-documents | Most referenced documents |
| GET | /api/v1/analytics/{workspace_id}/performance | Response time and token metrics |
| GET | /api/v1/analytics/{workspace_id}/live | Live Redis counters |
| GET | /api/v1/analytics/{workspace_id}/stream | SSE live event stream |

### Usage
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/v1/usage/{workspace_id}/stats | Workspace statistics |
| GET | /api/v1/usage/{workspace_id}/history | Query history |

### Admin
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/v1/admin/dashboard | Platform-wide stats + token trends |
| GET | /api/v1/admin/workspaces | All workspaces with activity |
| GET | /api/v1/admin/users | All users with workspace count |
| GET | /api/v1/admin/stats/tokens | Token usage trends (N days) |

---

## Quick Start

### Prerequisites
- Docker and Docker Compose
- Anthropic API key

### Setup

```bash
git clone https://github.com/andugetachew/ai-knowledgebase-api
cd ai-knowledgebase-api

cp .env.example .env.docker
# Edit .env.docker with your credentials

docker compose up -d
docker compose exec api alembic upgrade head
```

API: `http://localhost:8000`
Swagger: `http://localhost:8000/docs`

### Local Development

```bash
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements-dev.txt

cp .env.example .env
# Edit .env with your values

pytest -v
```

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| DATABASE_URL | PostgreSQL connection string |
| MONGO_URL | MongoDB connection string |
| MONGO_DB_NAME | MongoDB database name |
| REDIS_URL | Redis connection string |
| SECRET_KEY | JWT signing key (32+ chars) |
| ANTHROPIC_API_KEY | Claude API key |
| ENVIRONMENT | development or production |

---

## WebSocket Usage

Connect to `ws://localhost:8000/api/v1/ws/chat/{workspace_id}`

```json
{"token": "your_jwt_token"}
{"question": "What does the document say about X?"}

{"type": "token", "content": "The document..."}
{"type": "done", "sources": ["doc-id"], "tokens_used": 120}
```

---

## CI/CD Pipeline

On every push to main:
1. Spin up PostgreSQL, MongoDB, Redis services
2. Run full test suite (121 tests)
3. Build Docker image
4. Push to Docker Hub (`momiyyee/ai-knowledgebase-api`)

---

## Monitoring

Prometheus metrics available at `/metrics`. Compatible with Grafana dashboards.

Key metrics:
- `http_requests_total` — request count by endpoint and status
- `http_request_duration_seconds` — response latency per endpoint
- `process_resident_memory_bytes` — memory usage

---

## License
MIT