import httpx
from app.core.config import settings


class LLMServiceError(Exception):
    """Raised when the LLM provider call fails after the chunks were retrieved."""
    pass


async def generate_answer(
    question: str,
    context_chunks: list[dict],
    conversation_history: list[dict] | None = None,
) -> dict:
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

    system_prompt = f"""You are a helpful assistant that answers questions based on the provided documents.

Context from documents:
{context}

Answer based only on the context above. If the answer is not in the context, say so clearly.
If the user asks a follow-up question, use the conversation history to understand what they are referring to."""

    messages = []
    if conversation_history:
        for msg in conversation_history[-6:]:
            messages.append({"role": "user", "content": msg["question"]})
            messages.append({"role": "assistant", "content": msg["answer"]})
    messages.append({"role": "user", "content": question})

    try:
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
                    "system": system_prompt,
                    "messages": messages,
                },
            )
            response.raise_for_status()
            data = response.json()
    except httpx.TimeoutException as exc:
        raise LLMServiceError("The AI service took too long to respond. Please try again.") from exc
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 429:
            raise LLMServiceError("The AI service is rate limited. Please try again in a moment.") from exc
        if exc.response.status_code >= 500:
            raise LLMServiceError("The AI service is temporarily unavailable. Please try again shortly.") from exc
        raise LLMServiceError(f"The AI service returned an error: {exc.response.status_code}") from exc
    except httpx.RequestError as exc:
        raise LLMServiceError("Could not reach the AI service. Please try again.") from exc

    content_blocks = data.get("content", [])
    if not content_blocks or "text" not in content_blocks[0]:
        raise LLMServiceError("The AI service returned an unexpected response. Please try rephrasing your question.")

    answer = content_blocks[0]["text"]
    tokens_used = data["usage"]["input_tokens"] + data["usage"]["output_tokens"]
    sources = list({chunk.get("document_id", "") for chunk in context_chunks})

    return {
        "answer": answer,
        "sources": sources,
        "tokens_used": tokens_used,
    }