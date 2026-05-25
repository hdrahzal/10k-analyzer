from retrieval.rrf import reciprocal_rank_fusion


def test_chunk_in_both_lists_scores_higher():
    semantic = [(0, 0.9), (1, 0.8), (2, 0.7)]
    bm25     = [(2, 5.0), (0, 4.0), (3, 3.0)]
    results = reciprocal_rank_fusion(semantic, bm25)
    result_ids = [r[0] for r in results]
    assert result_ids.index(0) < result_ids.index(1)


def test_returns_at_most_top_k():
    semantic = [(i, float(10 - i)) for i in range(15)]
    bm25     = [(i, float(15 - i)) for i in range(15)]
    results = reciprocal_rank_fusion(semantic, bm25, top_k=10)
    assert len(results) <= 10


def test_scores_are_positive():
    semantic = [(0, 0.9), (1, 0.8)]
    bm25     = [(1, 5.0), (2, 4.0)]
    results = reciprocal_rank_fusion(semantic, bm25)
    for _, score in results:
        assert score > 0


def test_empty_inputs_return_empty():
    assert reciprocal_rank_fusion([], []) == []
