# AI Knowledge Base API

> Intelligent document Q&A API built with FastAPI, PostgreSQL, MongoDB, Redis, and Claude AI

## Features
- JWT authentication with workspace isolation
- Document upload with semantic chunking and embedding
- AI-powered Q&A using Claude API
- Real-time streaming via WebSocket
- Semantic search with cosine similarity
- Usage analytics and query history
- Background processing with Celery
- Redis caching for search and stats
- Full Docker production setup
- 53 passing tests across all modules

## Tech Stack
| Layer | Technology |
|-------|-----------|
| Framework | FastAPI |
| Auth | JWT (python-jose) |
| SQL DB | PostgreSQL + SQLAlchemy + Alembic |
| NoSQL DB | MongoDB (Motor) |
| Cache/Queue | Redis + Celery |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) |
| AI | Anthropic Claude API |
| Containers | Docker + docker-compose |
| CI/CD | GitHub Actions |
| Deployment | Render |

## Architecture
\`\`\`
Client → FastAPI → PostgreSQL (users, workspaces, documents)
                 → MongoDB (chunks, embeddings, chat history)
                 → Redis (cache, Celery broker)
                 → Claude API (Q&A, streaming)
                 → Celery Worker (async chunking/embedding)
\`\`\`

## API Endpoints

### Auth
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/v1/auth/register | Register user + create workspace |
| POST | /api/v1/auth/login | Login, get JWT token |

### Documents
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/v1/documents/ | Upload document (PDF, TXT, MD) |
| GET | /api/v1/documents/ | List workspace documents |
| DELETE | /api/v1/documents/{id} | Delete document |

### Chat
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/v1/chat/ | Ask question, get AI answer |
| WS | /api/v1/ws/chat/{workspace_id} | Streaming chat via WebSocket |

### Search
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/v1/search/ | Semantic search across documents |

### Usage
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/v1/usage/{workspace_id}/stats | Workspace statistics |
| GET | /api/v1/usage/{workspace_id}/history | Query history |

## Quick Start

### Prerequisites
- Docker and Docker Compose
- Anthropic API key

### Setup

\`\`\`bash
git clone https://github.com/andugetachew/ai-knowledgebase-api
cd ai-knowledgebase-api

cp .env.example .env.docker
# Edit .env.docker and add your ANTHROPIC_API_KEY

docker compose up -d
docker compose exec api alembic upgrade head
\`\`\`

API available at `http://localhost:8000`
Swagger docs at `http://localhost:8000/docs`

### Local Development

\`\`\`bash
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt

cp .env.example .env
# Edit .env with your local values

pytest -v
\`\`\`

## Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| DATABASE_URL | PostgreSQL connection string | postgresql+asyncpg://... |
| MONGO_URL | MongoDB connection string | mongodb://... |
| MONGO_DB_NAME | MongoDB database name | ai_knowledgebase_mongo |
| REDIS_URL | Redis connection string | redis://localhost:6379/0 |
| SECRET_KEY | JWT signing key (32+ chars) | ... |
| ANTHROPIC_API_KEY | Claude API key | sk-ant-... |
| ENVIRONMENT | development or production | development |

## Running Tests

\`\`\`bash
pytest -v
\`\`\`

53 tests across auth, chat, documents, search, usage, and WebSocket modules.

## WebSocket Usage

Connect to `ws://localhost:8000/api/v1/ws/chat/{workspace_id}`

\`\`\`json
// Send auth first
{"token": "your_jwt_token"}

// Then send questions
{"question": "What does the document say about X?"}

// Receive streaming tokens
{"type": "token", "content": "The document..."}
{"type": "done", "sources": ["doc-id"], "tokens_used": 120}
\`\`\`

## CI/CD

GitHub Actions runs on every push to main:
1. Spins up PostgreSQL and MongoDB services
2. Runs full test suite (53 tests)
3. Builds Docker image

## License
MIT