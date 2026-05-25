import voyageai
from config import settings

_client = voyageai.Client(api_key=settings.voyage_api_key)
RERANK_MODEL = "rerank-2"
TOP_K = 5


def rerank(query: str, candidates: list[dict]) -> list[dict]:
    """
    Reranks candidate chunks using Voyage rerank-2.
    Returns up to TOP_K chunks sorted by relevance score (highest first),
    each enriched with 'rerank_score'.
    """
    if not candidates:
        return []
    texts = [c["text"] for c in candidates]
    result = _client.rerank(query, texts, model=RERANK_MODEL, top_k=TOP_K)
    return [
        {**candidates[item.index], "rerank_score": item.relevance_score}
        for item in result.results
    ]
