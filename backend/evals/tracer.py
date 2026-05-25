import json
import sqlite3
import uuid
from datetime import datetime, timezone
from config import settings


def get_eval_db() -> sqlite3.Connection:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(settings.data_dir / "evals.sqlite")
    db.row_factory = sqlite3.Row
    db.executescript("""
        CREATE TABLE IF NOT EXISTS traces (
            id                   TEXT PRIMARY KEY,
            doc_id               TEXT NOT NULL,
            session_id           TEXT,
            timestamp            TEXT NOT NULL,
            query                TEXT NOT NULL,
            conversation_history TEXT NOT NULL,
            retrieved_chunks     TEXT NOT NULL,
            response             TEXT NOT NULL,
            latency_ms           INTEGER NOT NULL,
            model                TEXT NOT NULL,
            embedding_model      TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS human_feedback (
            id         TEXT PRIMARY KEY,
            trace_id   TEXT NOT NULL REFERENCES traces(id),
            rating     TEXT NOT NULL,
            comment    TEXT,
            timestamp  TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS llm_scores (
            id         TEXT PRIMARY KEY,
            trace_id   TEXT NOT NULL REFERENCES traces(id),
            grounded   INTEGER,
            relevant   INTEGER,
            concise    INTEGER,
            scored_at  TEXT NOT NULL
        );
    """)
    db.commit()
    return db


def log_trace(
    doc_id: str,
    query: str,
    conversation_history: list,
    retrieved_chunks: list[dict],
    response: str,
    latency_ms: int,
    session_id: str | None = None,
) -> str:
    trace_id = str(uuid.uuid4())
    db = get_eval_db()
    db.execute(
        "INSERT INTO traces VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (
            trace_id, doc_id, session_id,
            datetime.now(timezone.utc).isoformat(),
            query,
            json.dumps(conversation_history),
            json.dumps([
                {
                    "section": c.get("section"), "page_start": c.get("page_start"),
                    "page_end": c.get("page_end"), "rerank_score": c.get("rerank_score"),
                }
                for c in retrieved_chunks
            ]),
            response, latency_ms,
            "claude-sonnet-4-6", "voyage-finance-2",
        ),
    )
    db.commit()
    db.close()
    return trace_id


def log_feedback(trace_id: str, rating: str, comment: str | None):
    db = get_eval_db()
    db.execute(
        "INSERT INTO human_feedback VALUES (?,?,?,?,?)",
        (str(uuid.uuid4()), trace_id, rating, comment,
         datetime.now(timezone.utc).isoformat()),
    )
    db.commit()
    db.close()
