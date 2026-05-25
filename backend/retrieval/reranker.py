from sentence_transformers import CrossEncoder
from config import settings

TOP_K = 5

_model: CrossEncoder | None = None


def _get_model() -> CrossEncoder:
    """Lazy-load to avoid loading the model at import time."""
    global _model
    if _model is None:
        _model = CrossEncoder(settings.rerank_model)
    return _model


def rerank(query: str, candidates: list[dict]) -> list[dict]:
    """
    Reranks candidate chunks using a local BGE cross-encoder.
    Returns up to TOP_K chunks sorted by relevance score (highest first),
    each enriched with 'rerank_score'.
    """
    if not candidates:
        return []
    model = _get_model()
    pairs = [(query, c["text"]) for c in candidates]
    scores = model.predict(pairs, show_progress_bar=False)

    scored = list(zip(candidates, scores))
    scored.sort(key=lambda x: x[1], reverse=True)
    return [
        {**c, "rerank_score": float(s)}
        for c, s in scored[:TOP_K]
    ]
