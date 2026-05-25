import numpy as np
from sentence_transformers import SentenceTransformer
from config import settings

BATCH_SIZE = 32

_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    """Lazy-load to avoid loading the model at import time (helps tests/CLI)."""
    global _model
    if _model is None:
        _model = SentenceTransformer(settings.embedding_model)
    return _model


def embed_chunks(chunks: list[dict]) -> np.ndarray:
    """
    Embeds each chunk's 'cch_text'. Returns L2-normalized float32 array
    of shape (n_chunks, embedding_dim) for use with FAISS IndexFlatIP.
    """
    texts = [c["cch_text"] for c in chunks]
    model = _get_model()
    vectors = model.encode(
        texts,
        batch_size=BATCH_SIZE,
        show_progress_bar=False,
        normalize_embeddings=True,
        convert_to_numpy=True,
    ).astype(np.float32)
    return vectors


def embed_query(query: str) -> np.ndarray:
    """Returns L2-normalized float32 array of shape (1, embedding_dim)."""
    model = _get_model()
    vec = model.encode(
        [query],
        show_progress_bar=False,
        normalize_embeddings=True,
        convert_to_numpy=True,
    ).astype(np.float32)
    return vec
