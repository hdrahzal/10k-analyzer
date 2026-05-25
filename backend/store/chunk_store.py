import sqlite3
import pickle
from pathlib import Path
from rank_bm25 import BM25Okapi


def get_db(doc_dir: Path) -> sqlite3.Connection:
    db = sqlite3.connect(doc_dir / "chunks.sqlite")
    db.row_factory = sqlite3.Row
    db.executescript("""
        CREATE TABLE IF NOT EXISTS chunks (
            chunk_id   TEXT PRIMARY KEY,
            doc_id     TEXT NOT NULL,
            section    TEXT NOT NULL,
            page_start INTEGER NOT NULL,
            page_end   INTEGER NOT NULL,
            text       TEXT NOT NULL,
            anchor_text TEXT NOT NULL,
            cch_text   TEXT NOT NULL,
            chunk_index INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS bm25_index (
            doc_id     TEXT PRIMARY KEY,
            index_blob BLOB NOT NULL
        );
    """)
    db.commit()
    return db


def save_chunks(db: sqlite3.Connection, doc_id: str, chunks: list[dict]):
    db.executemany(
        "INSERT OR REPLACE INTO chunks VALUES (?,?,?,?,?,?,?,?,?)",
        [
            (
                c["chunk_id"], doc_id, c["section"],
                c["page_start"], c["page_end"],
                c["text"], c["anchor_text"], c["cch_text"],
                c["chunk_index"],
            )
            for c in chunks
        ],
    )
    db.commit()


def save_bm25(db: sqlite3.Connection, doc_id: str, chunks: list[dict]):
    tokenized = [c["text"].lower().split() for c in chunks]
    bm25 = BM25Okapi(tokenized)
    db.execute(
        "INSERT OR REPLACE INTO bm25_index VALUES (?,?)",
        (doc_id, pickle.dumps(bm25)),
    )
    db.commit()


def load_bm25(db: sqlite3.Connection, doc_id: str) -> BM25Okapi:
    row = db.execute(
        "SELECT index_blob FROM bm25_index WHERE doc_id=?", (doc_id,)
    ).fetchone()
    return pickle.loads(row["index_blob"])


def load_chunks(db: sqlite3.Connection) -> list[dict]:
    rows = db.execute(
        "SELECT * FROM chunks ORDER BY chunk_index"
    ).fetchall()
    return [dict(r) for r in rows]


def chunk_count(db: sqlite3.Connection) -> int:
    return db.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
