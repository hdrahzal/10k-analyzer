import pytest
from unittest.mock import patch


@pytest.fixture
def patched_settings(tmp_path):
    with patch("evals.tracer.settings") as mock:
        mock.data_dir = tmp_path
        yield mock


def test_log_trace_creates_row(patched_settings):
    from evals.tracer import log_trace, get_eval_db
    trace_id = log_trace(
        doc_id="doc1",
        query="What are the risks?",
        conversation_history=[{"role": "user", "content": "What are the risks?"}],
        retrieved_chunks=[{"section": "Item 1A", "page_start": 5, "page_end": 6,
                           "anchor_text": "risk", "rerank_score": 0.9}],
        response="The main risk is competition **[Page 5]**.",
        latency_ms=1200,
    )
    db = get_eval_db()
    row = db.execute("SELECT * FROM traces WHERE id=?", (trace_id,)).fetchone()
    assert row is not None
    assert row["query"] == "What are the risks?"
    assert row["latency_ms"] == 1200
    db.close()


def test_log_feedback_creates_row(patched_settings):
    from evals.tracer import log_trace, log_feedback, get_eval_db
    trace_id = log_trace(
        doc_id="doc1", query="q",
        conversation_history=[], retrieved_chunks=[],
        response="r", latency_ms=100,
    )
    log_feedback(trace_id, "up", "Great answer")
    db = get_eval_db()
    row = db.execute(
        "SELECT * FROM human_feedback WHERE trace_id=?", (trace_id,)
    ).fetchone()
    assert row["rating"] == "up"
    assert row["comment"] == "Great answer"
    db.close()
