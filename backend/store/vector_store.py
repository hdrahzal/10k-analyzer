import faiss
import numpy as np
from pathlib import Path


def save_index(vectors: np.ndarray, index_path: Path):
    """Saves L2-normalized vectors as a FAISS IndexFlatIP (cosine similarity)."""
    index = faiss.IndexFlatIP(vectors.shape[1])
    index.add(vectors)
    faiss.write_index(index, str(index_path))


def load_index(index_path: Path) -> faiss.IndexFlatIP:
    return faiss.read_index(str(index_path))


def search_index(
    index: faiss.IndexFlatIP, query_vec: np.ndarray, top_k: int
) -> list[tuple[int, float]]:
    """Returns list of (chunk_index, score) sorted by score desc."""
    scores, indices = index.search(query_vec, top_k)
    return [
        (int(i), float(s))
        for i, s in zip(indices[0], scores[0])
        if i >= 0
    ]
