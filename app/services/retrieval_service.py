import numpy as np
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.services.embedding_service import generate_embedding


def cosine_similarity(a: list[float], b: list[float]) -> float:
    a_arr = np.array(a)
    b_arr = np.array(b)
    return float(np.dot(a_arr, b_arr) / (np.linalg.norm(a_arr) * np.linalg.norm(b_arr) + 1e-10))


async def retrieve_relevant_chunks(
    query: str,
    workspace_id: str,
    db: AsyncIOMotorDatabase,
    top_k: int = 5,
) -> list[dict]:
    """Find the most relevant chunks for a query using cosine similarity."""
    query_embedding = generate_embedding(query)

    # fetch all chunks for this workspace
    cursor = db["chunks"].find({"workspace_id": workspace_id})
    chunks = await cursor.to_list(length=500)

    if not chunks:
        return []

    # score each chunk
    scored = []
    for chunk in chunks:
        if not chunk.get("embedding"):
            continue
        score = cosine_similarity(query_embedding, chunk["embedding"])
        scored.append((score, chunk))

    # return top_k by score
    scored.sort(key=lambda x: x[0], reverse=True)
    return [chunk for _, chunk in scored[:top_k]]