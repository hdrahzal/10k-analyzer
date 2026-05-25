from config import settings
from store.chunk_store import get_db, load_bm25, load_chunks
from store.vector_store import load_index, search_index
from ingest.embedder import embed_query

TOP_K = 20


def dual_search(
    doc_id: str, query: str
) -> tuple[list[tuple[int, float]], list[tuple[int, float]], list[dict]]:
    """
    Returns (semantic_results, bm25_results, all_chunks).
    Each results list is [(chunk_index, score), ...] length <= TOP_K.
    """
    doc_dir = settings.data_dir / doc_id
    db = get_db(doc_dir)
    all_chunks = load_chunks(db)

    faiss_index = load_index(doc_dir / "vectors.faiss")
    query_vec = embed_query(query)
    semantic_results = search_index(faiss_index, query_vec, TOP_K)

    bm25 = load_bm25(db, doc_id)
    db.close()
    tokenized = query.lower().split()
    bm25_scores = bm25.get_scores(tokenized)
    bm25_results = sorted(
        [(i, float(s)) for i, s in enumerate(bm25_scores)],
        key=lambda x: x[1],
        reverse=True,
    )[:TOP_K]

    return semantic_results, bm25_results, all_chunks
