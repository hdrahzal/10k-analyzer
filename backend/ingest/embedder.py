import numpy as np
import voyageai
from config import settings

_client = voyageai.Client(api_key=settings.voyage_api_key)
MODEL = "voyage-finance-2"
BATCH_SIZE = 128


def embed_chunks(chunks: list[dict]) -> np.ndarray:
    """
    Embeds each chunk's 'cch_text'. Returns L2-normalized float32 array
    of shape (n_chunks, embedding_dim) for use with FAISS IndexFlatIP.
    """
    texts = [c["cch_text"] for c in chunks]
    embeddings = []
    for i in range(0, len(texts), BATCH_SIZE):
        result = _client.embed(texts[i : i + BATCH_SIZE], model=MODEL, input_type="document")
        embeddings.extend(result.embeddings)
    vectors = np.array(embeddings, dtype=np.float32)
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    return vectors / norms


def embed_query(query: str) -> np.ndarray:
    """Returns L2-normalized float32 array of shape (1, embedding_dim)."""
    result = _client.embed([query], model=MODEL, input_type="query")
    vec = np.array(result.embeddings[0], dtype=np.float32)
    return (vec / np.linalg.norm(vec)).reshape(1, -1)
