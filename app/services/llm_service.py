import httpx
from app.core.config import settings


async def generate_answer(question: str, context_chunks: list[dict]) -> dict:
    """Send question + context to Claude API and return answer."""

    if not context_chunks:
        return {
            "answer": "No relevant documents found to answer your question.",
            "sources": [],
            "tokens_used": 0,
        }

    context = "\n\n".join([
        f"[Document: {chunk.get('document_id', 'unknown')}]\n{chunk['content']}"
        for chunk in context_chunks
    ])

    prompt = f"""You are a helpful assistant that answers questions based on the provided documents.

Context:
{context}

Question: {question}

Answer based only on the context above. If the answer is not in the context, say so clearly."""

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": settings.anthropic_api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-haiku-4-5-20251001",
                "max_tokens": 1024,
                "messages": [{"role": "user", "content": prompt}],
            },
        )
        response.raise_for_status()
        data = response.json()

    answer = data["content"][0]["text"]
    tokens_used = data["usage"]["input_tokens"] + data["usage"]["output_tokens"]
    sources = list({chunk.get("document_id", "") for chunk in context_chunks})

    return {
        "answer": answer,
        "sources": sources,
        "tokens_used": tokens_used,
    }