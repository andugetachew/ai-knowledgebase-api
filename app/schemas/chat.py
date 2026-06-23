from pydantic import BaseModel

from pydantic import BaseModel


class ChatRequest(BaseModel):
    question: str
    workspace_id: str


class ChatResponse(BaseModel):
    answer: str
    sources: list[str] = []
    tokens_used: int = 0


class SearchRequest(BaseModel):
    query: str
    workspace_id: str
    top_k: int = 5


class ChunkResult(BaseModel):
    document_id: str
    content: str
    chunk_index: int
    score: float


class SearchResponse(BaseModel):
    query: str
    results: list[ChunkResult]
    total: int

class ChatRequest(BaseModel):
    question: str
    workspace_id: str


class ChatResponse(BaseModel):
    answer: str
    sources: list[str] = []
    tokens_used: int = 0

class WorkspaceStats(BaseModel):
    workspace_id: str
    total_documents: int
    total_chunks: int
    total_queries: int
    total_tokens_used: int


class QueryLog(BaseModel):
    question: str
    answer: str
    sources: list[str]
    tokens_used: int
    created_at: str