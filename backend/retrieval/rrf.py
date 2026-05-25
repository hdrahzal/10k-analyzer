_K = 60


def reciprocal_rank_fusion(
    semantic_results: list[tuple[int, float]],
    bm25_results: list[tuple[int, float]],
    top_k: int = 20,
) -> list[tuple[int, float]]:
    """
    Merges two ranked lists via RRF. Returns up to top_k (chunk_index, rrf_score) pairs.
    score(chunk) = sum 1 / (K + rank) across all lists where chunk appears.
    """
    scores: dict[int, float] = {}
    for rank, (idx, _) in enumerate(semantic_results):
        scores[idx] = scores.get(idx, 0.0) + 1.0 / (_K + rank + 1)
    for rank, (idx, _) in enumerate(bm25_results):
        scores[idx] = scores.get(idx, 0.0) + 1.0 / (_K + rank + 1)
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
