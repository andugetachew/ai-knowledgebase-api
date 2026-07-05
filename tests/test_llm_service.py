import httpx
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.llm_service import generate_answer, LLMServiceError

async def test_generate_answer_with_no_chunks_returns_early():

    result = await generate_answer(question="What is this?", context_chunks=[])
    assert result["answer"] == "No relevant documents found to answer your question."
    assert result["sources"] == []
    assert result["tokens_used"] == 0


def _make_mock_client(response_json):
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = response_json

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


async def test_generate_answer_calls_anthropic_and_parses_response():
    mock_client = _make_mock_client({
        "content": [{"text": "This is the answer."}],
        "usage": {"input_tokens": 100, "output_tokens": 20},
    })

    with patch("app.services.llm_service.httpx.AsyncClient", return_value=mock_client):
        result = await generate_answer(
            question="What is the capital of France?",
            context_chunks=[{"document_id": "doc-1", "content": "Paris is the capital of France."}],
        )

    assert result["answer"] == "This is the answer."
    assert result["sources"] == ["doc-1"]
    assert result["tokens_used"] == 120


async def test_generate_answer_includes_conversation_history_in_messages():
    mock_client = _make_mock_client({
        "content": [{"text": "Follow-up answer."}],
        "usage": {"input_tokens": 50, "output_tokens": 10},
    })
    history = [{"question": "Who wrote it?", "answer": "An author."}]

    with patch("app.services.llm_service.httpx.AsyncClient", return_value=mock_client):
        result = await generate_answer(
            question="When?",
            context_chunks=[{"document_id": "doc-2", "content": "Some content."}],
            conversation_history=history,
        )

    sent_messages = mock_client.post.call_args.kwargs["json"]["messages"]
    assert sent_messages[0] == {"role": "user", "content": "Who wrote it?"}
    assert sent_messages[1] == {"role": "assistant", "content": "An author."}
    assert sent_messages[-1] == {"role": "user", "content": "When?"}
    assert result["answer"] == "Follow-up answer."


async def test_generate_answer_deduplicates_sources():
    mock_client = _make_mock_client({
        "content": [{"text": "Answer."}],
        "usage": {"input_tokens": 10, "output_tokens": 5},
    })

    with patch("app.services.llm_service.httpx.AsyncClient", return_value=mock_client):
        result = await generate_answer(
            question="Q",
            context_chunks=[
                {"document_id": "doc-1", "content": "a"},
                {"document_id": "doc-1", "content": "b"},
                {"document_id": "doc-2", "content": "c"},
            ],
        )

    assert sorted(result["sources"]) == ["doc-1", "doc-2"]


def _make_raising_client(exc):
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=exc)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


async def test_generate_answer_raises_on_timeout():
    mock_client = _make_raising_client(httpx.TimeoutException("timed out"))

    with patch("app.services.llm_service.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(LLMServiceError, match="took too long"):
            await generate_answer(
                question="Q",
                context_chunks=[{"document_id": "doc-1", "content": "c"}],
            )


async def test_generate_answer_raises_on_rate_limit():
    mock_response = MagicMock()
    mock_response.status_code = 429
    exc = httpx.HTTPStatusError("rate limited", request=MagicMock(), response=mock_response)
    mock_client = _make_raising_client(exc)

    with patch("app.services.llm_service.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(LLMServiceError, match="rate limited"):
            await generate_answer(
                question="Q",
                context_chunks=[{"document_id": "doc-1", "content": "c"}],
            )


async def test_generate_answer_raises_on_server_error():
    mock_response = MagicMock()
    mock_response.status_code = 503
    exc = httpx.HTTPStatusError("server error", request=MagicMock(), response=mock_response)
    mock_client = _make_raising_client(exc)

    with patch("app.services.llm_service.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(LLMServiceError, match="temporarily unavailable"):
            await generate_answer(
                question="Q",
                context_chunks=[{"document_id": "doc-1", "content": "c"}],
            )


async def test_generate_answer_raises_on_other_http_error():
    mock_response = MagicMock()
    mock_response.status_code = 400
    exc = httpx.HTTPStatusError("bad request", request=MagicMock(), response=mock_response)
    mock_client = _make_raising_client(exc)

    with patch("app.services.llm_service.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(LLMServiceError, match="400"):
            await generate_answer(
                question="Q",
                context_chunks=[{"document_id": "doc-1", "content": "c"}],
            )


async def test_generate_answer_raises_on_request_error():
    exc = httpx.RequestError("connection failed")
    mock_client = _make_raising_client(exc)

    with patch("app.services.llm_service.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(LLMServiceError, match="Could not reach"):
            await generate_answer(
                question="Q",
                context_chunks=[{"document_id": "doc-1", "content": "c"}],
            )


async def test_generate_answer_raises_on_empty_content():
    mock_client = _make_mock_client({"content": [], "usage": {"input_tokens": 1, "output_tokens": 1}})

    with patch("app.services.llm_service.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(LLMServiceError, match="unexpected response"):
            await generate_answer(
                question="Q",
                context_chunks=[{"document_id": "doc-1", "content": "c"}],
            )