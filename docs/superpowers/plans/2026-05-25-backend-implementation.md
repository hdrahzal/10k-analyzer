# 10-K Analyzer Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python FastAPI sidecar service that provides hybrid RAG retrieval, Claude-powered chat with page citations, and SQLite-based evals for the existing Next.js 10-K analyzer frontend.

**Architecture:** FastAPI (port 8000) owns all ingestion, retrieval, generation, and eval logic. Next.js (port 3000) proxies `/api/upload`, `/api/chat`, `/api/feedback`, and `/api/pdf/[docId]` to FastAPI. Documents are content-addressed by SHA-256 hash and stored under `data/{doc_id}/` (gitignored). Retrieval uses BM25 + Voyage semantic search → RRF → Voyage reranking → top-5 chunks fed to Claude Sonnet with an XML-structured system prompt.

**Tech Stack:** FastAPI, Anthropic SDK (Claude Sonnet 4.6 for chat, Claude Haiku 4.5 for CCH + judge), voyageai (voyage-finance-2 embeddings + rerank-2), faiss-cpu, rank_bm25, pdfplumber, SQLite (stdlib), react-pdf (frontend)

---

## File Map

```
repos/10k-analyzer/
├── backend/
│   ├── main.py                        # FastAPI app + all route handlers
│   ├── config.py                      # Pydantic-settings config (env vars)
│   ├── models.py                      # Pydantic request/response models
│   ├── requirements.txt
│   ├── ingest/
│   │   ├── __init__.py
│   │   ├── pdf_extractor.py           # pdfplumber → list of {page_number, text}
│   │   ├── section_detector.py        # filing type detection + section boundary regex
│   │   ├── chunker.py                 # section chunking with overlap
│   │   ├── cch.py                     # Claude Haiku CCH with prompt caching
│   │   ├── embedder.py                # Voyage voyage-finance-2 embed/query
│   │   └── pipeline.py                # orchestrates full ingest flow
│   ├── store/
│   │   ├── __init__.py
│   │   ├── chunk_store.py             # SQLite CRUD for chunks + BM25 blob
│   │   └── vector_store.py            # FAISS index save/load/search
│   ├── retrieval/
│   │   ├── __init__.py
│   │   ├── search.py                  # dual search (semantic + BM25)
│   │   ├── rrf.py                     # Reciprocal Rank Fusion
│   │   └── reranker.py                # Voyage rerank-2
│   ├── generation/
│   │   ├── __init__.py
│   │   └── chat.py                    # Claude Sonnet SSE streaming
│   ├── evals/
│   │   ├── __init__.py
│   │   ├── tracer.py                  # SQLite trace + feedback logging
│   │   ├── judge.py                   # Claude Haiku LLM-as-judge
│   │   └── eval_queries.json          # 20 canonical analyst questions
│   └── tests/
│       ├── conftest.py
│       ├── test_section_detector.py
│       ├── test_chunker.py
│       ├── test_rrf.py
│       └── test_tracer.py
├── app/
│   ├── api/
│   │   ├── upload/route.ts            # MODIFY: thin proxy → FastAPI /ingest
│   │   ├── chat/route.ts              # MODIFY: thin proxy → FastAPI /chat (SSE)
│   │   ├── feedback/route.ts          # NEW: thin proxy → FastAPI /feedback
│   │   └── pdf/
│   │       └── [docId]/
│   │           └── route.ts           # NEW: thin proxy → FastAPI /pdf/{doc_id}
├── components/
│   ├── pdf-viewer.tsx                 # NEW: react-pdf modal with page nav + highlight
│   ├── message-bubble.tsx             # MODIFY: clickable **[Page N]** + thumbs up/down
│   └── chat-interface.tsx             # MODIFY: custom streaming hook + pdf-viewer state
├── data/                              # gitignored - all doc stores + evals.sqlite live here
└── .env.local.example                 # MODIFY: add VOYAGE_API_KEY
```

---

## Task 1: Project Scaffolding

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/config.py`
- Create: `backend/models.py`
- Create: `backend/main.py`
- Create: `backend/ingest/__init__.py`
- Create: `backend/store/__init__.py`
- Create: `backend/retrieval/__init__.py`
- Create: `backend/generation/__init__.py`
- Create: `backend/evals/__init__.py`
- Create: `backend/tests/conftest.py`
- Modify: `.gitignore`
- Modify: `.env.local.example` (or create if missing)

- [ ] **Step 1: Create requirements.txt**

```
fastapi==0.115.6
uvicorn[standard]==0.34.0
anthropic==0.49.0
voyageai==0.3.5
faiss-cpu==1.10.0
rank_bm25==0.2.2
pdfplumber==0.11.4
pydantic==2.11.4
pydantic-settings==2.8.2
python-multipart==0.0.20
numpy==2.2.5
pytest==8.3.5
pytest-asyncio==0.25.3
httpx==0.28.1
```

Save to `backend/requirements.txt`.

- [ ] **Step 2: Create config.py**

```python
# backend/config.py
from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    anthropic_api_key: str
    voyage_api_key: str
    data_dir: Path = Path(__file__).parent.parent / "data"
    fastapi_port: int = 8000

    model_config = {"env_file": "../.env.local", "extra": "ignore"}


settings = Settings()
```

- [ ] **Step 3: Create models.py**

```python
# backend/models.py
from pydantic import BaseModel
from typing import Optional


class IngestResponse(BaseModel):
    doc_id: str
    filename: str
    total_chunks: int
    filing_type: str
    already_processed: bool


class Message(BaseModel):
    role: str
    content: str


class Citation(BaseModel):
    page: int
    section: str
    anchor_text: str
    doc_id: str


class ChatRequest(BaseModel):
    doc_id: str
    messages: list[Message]


class FeedbackRequest(BaseModel):
    trace_id: str
    rating: str
    comment: Optional[str] = None
```

- [ ] **Step 4: Create main.py skeleton**

```python
# backend/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config import settings

app = FastAPI(title="10-K Analyzer API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)
settings.data_dir.mkdir(parents=True, exist_ok=True)
```

- [ ] **Step 5: Create all `__init__.py` files**

Run:
```bash
touch backend/ingest/__init__.py backend/store/__init__.py \
      backend/retrieval/__init__.py backend/generation/__init__.py \
      backend/evals/__init__.py
```

- [ ] **Step 6: Create conftest.py**

```python
# backend/tests/conftest.py
import pytest
from pathlib import Path
import tempfile

@pytest.fixture
def tmp_data_dir(tmp_path):
    return tmp_path
```

- [ ] **Step 7: Add data/ to .gitignore**

Open `repos/10k-analyzer/.gitignore` and append:
```
# local document store - never commit
/data/
```

- [ ] **Step 8: Create/update .env.local.example**

```
ANTHROPIC_API_KEY=your_key_here
VOYAGE_API_KEY=your_key_here
```

Save as `repos/10k-analyzer/.env.local.example`.

- [ ] **Step 9: Install Python dependencies and verify FastAPI starts**

```bash
cd repos/10k-analyzer/backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Create `repos/10k-analyzer/.env.local` with real keys, then:
```bash
uvicorn main:app --port 8000 --reload
```

Expected: `Application startup complete.` at `http://localhost:8000`

- [ ] **Step 10: Commit**

```bash
git add backend/ .gitignore .env.local.example
git commit -m "feat: scaffold FastAPI backend structure"
```

---

## Task 2: PDF Extractor + Section Detector

**Files:**
- Create: `backend/ingest/pdf_extractor.py`
- Create: `backend/ingest/section_detector.py`
- Create: `backend/tests/test_section_detector.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_section_detector.py
import pytest
from ingest.section_detector import detect_filing_type, detect_sections, FilingType


PAGES_10K = [
    {"page_number": 1, "text": "UNITED STATES SECURITIES AND EXCHANGE COMMISSION\nFORM 10-K\nANNUAL REPORT"},
    {"page_number": 2, "text": "ITEM 1. BUSINESS\nWe are a technology company."},
    {"page_number": 5, "text": "ITEM 1A. RISK FACTORS\nOur business faces risks."},
    {"page_number": 10, "text": "ITEM 7. MANAGEMENT'S DISCUSSION AND ANALYSIS\nRevenue increased."},
]

PAGES_10Q = [
    {"page_number": 1, "text": "FORM 10-Q\nQUARTERLY REPORT PURSUANT TO SECTION 13"},
    {"page_number": 2, "text": "PART I. FINANCIAL INFORMATION\nItem 1. Financial Statements"},
    {"page_number": 8, "text": "ITEM 2. MANAGEMENT'S DISCUSSION AND ANALYSIS"},
    {"page_number": 12, "text": "PART II. OTHER INFORMATION"},
]


def test_detect_10k():
    assert detect_filing_type(PAGES_10K) == FilingType.K10


def test_detect_10q():
    assert detect_filing_type(PAGES_10Q) == FilingType.Q10


def test_detect_sections_10k_finds_item1():
    sections = detect_sections(PAGES_10K, FilingType.K10)
    names = [s["name"] for s in sections]
    assert any("BUSINESS" in n.upper() or "ITEM 1" in n.upper() for n in names)


def test_detect_sections_has_page_metadata():
    sections = detect_sections(PAGES_10K, FilingType.K10)
    for s in sections:
        assert "page_start" in s
        assert "page_end" in s
        assert "text" in s
        assert s["page_start"] <= s["page_end"]


def test_fallback_single_section_when_no_headers():
    pages = [{"page_number": 1, "text": "Some text without any section headers."}]
    sections = detect_sections(pages, FilingType.K10)
    assert len(sections) == 1
    assert sections[0]["name"] == "Document"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && python -m pytest tests/test_section_detector.py -v
```

Expected: `ModuleNotFoundError: No module named 'ingest.section_detector'`

- [ ] **Step 3: Implement pdf_extractor.py**

```python
# backend/ingest/pdf_extractor.py
import pdfplumber
from pathlib import Path


def extract_pages(pdf_path: Path) -> list[dict]:
    """Returns list of {page_number: int (1-indexed), text: str}."""
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            pages.append({"page_number": i + 1, "text": text})
    return pages
```

- [ ] **Step 4: Implement section_detector.py**

```python
# backend/ingest/section_detector.py
import re
from enum import Enum


class FilingType(str, Enum):
    K10 = "10-K"
    Q10 = "10-Q"


_K10_HEADERS = [
    r"ITEM\s+1[.\s]+BUSINESS",
    r"ITEM\s+1A[.\s]+RISK\s+FACTORS",
    r"ITEM\s+1B[.\s]+UNRESOLVED\s+STAFF\s+COMMENTS",
    r"ITEM\s+2[.\s]+PROPERTIES",
    r"ITEM\s+3[.\s]+LEGAL\s+PROCEEDINGS",
    r"ITEM\s+4[.\s]+MINE\s+SAFETY",
    r"ITEM\s+5[.\s]+MARKET",
    r"ITEM\s+7[.\s]+MANAGEMENT",
    r"ITEM\s+7A[.\s]+QUANTITATIVE",
    r"ITEM\s+8[.\s]+FINANCIAL\s+STATEMENTS",
    r"ITEM\s+9A[.\s]+CONTROLS",
    r"ITEM\s+10[.\s]+DIRECTORS",
    r"ITEM\s+11[.\s]+EXECUTIVE",
    r"ITEM\s+12[.\s]+SECURITY",
    r"ITEM\s+13[.\s]+CERTAIN",
    r"ITEM\s+14[.\s]+PRINCIPAL",
    r"ITEM\s+15[.\s]+EXHIBITS",
]

_Q10_HEADERS = [
    r"PART\s+I[.\s]+FINANCIAL\s+INFORMATION",
    r"ITEM\s+1[.\s]+FINANCIAL\s+STATEMENTS",
    r"ITEM\s+2[.\s]+MANAGEMENT",
    r"ITEM\s+3[.\s]+QUANTITATIVE",
    r"ITEM\s+4[.\s]+CONTROLS",
    r"PART\s+II[.\s]+OTHER\s+INFORMATION",
    r"ITEM\s+1A[.\s]+RISK",
    r"ITEM\s+6[.\s]+EXHIBITS",
]


def detect_filing_type(pages: list[dict]) -> FilingType:
    text = " ".join(p["text"] for p in pages[:5]).upper()
    if "FORM 10-Q" in text or "QUARTERLY REPORT" in text:
        return FilingType.Q10
    return FilingType.K10


def detect_sections(pages: list[dict], filing_type: FilingType) -> list[dict]:
    patterns = _K10_HEADERS if filing_type == FilingType.K10 else _Q10_HEADERS
    compiled = [re.compile(p, re.IGNORECASE) for p in patterns]
    page_map = {p["page_number"]: p["text"] for p in pages}

    starts: list[tuple[int, str]] = []
    seen: set[str] = set()

    for page in pages:
        for pattern in compiled:
            m = pattern.search(page["text"])
            if m:
                name = m.group(0).strip()
                if name not in seen:
                    seen.add(name)
                    starts.append((page["page_number"], name))
                break

    starts.sort(key=lambda x: x[0])

    if not starts:
        return [{
            "name": "Document",
            "page_start": pages[0]["page_number"],
            "page_end": pages[-1]["page_number"],
            "text": "\n".join(p["text"] for p in pages),
        }]

    sections = []
    last_page = pages[-1]["page_number"]
    for i, (start_page, name) in enumerate(starts):
        end_page = starts[i + 1][0] - 1 if i + 1 < len(starts) else last_page
        text = "\n".join(page_map.get(p, "") for p in range(start_page, end_page + 1))
        sections.append({"name": name, "page_start": start_page, "page_end": end_page, "text": text})

    return sections
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd backend && python -m pytest tests/test_section_detector.py -v
```

Expected: 5 PASSED

- [ ] **Step 6: Commit**

```bash
git add backend/ingest/pdf_extractor.py backend/ingest/section_detector.py \
        backend/tests/test_section_detector.py
git commit -m "feat: pdf extractor and section detector with tests"
```

---

## Task 3: Chunker

**Files:**
- Create: `backend/ingest/chunker.py`
- Create: `backend/tests/test_chunker.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_chunker.py
from ingest.chunker import chunk_sections


SECTIONS = [
    {
        "name": "Item 1A – Risk Factors",
        "page_start": 5,
        "page_end": 10,
        "text": ("Risk factors paragraph one. " * 100) + "\n\n" + ("Risk factors paragraph two. " * 100),
    },
    {
        "name": "Item 7 – MD&A",
        "page_start": 20,
        "page_end": 25,
        "text": "Short section text.",
    },
]


def test_chunks_have_required_fields():
    chunks = chunk_sections(SECTIONS)
    for c in chunks:
        assert "chunk_id" in c
        assert "section" in c
        assert "page_start" in c
        assert "page_end" in c
        assert "text" in c
        assert "anchor_text" in c
        assert "chunk_index" in c


def test_anchor_text_is_120_chars_max():
    chunks = chunk_sections(SECTIONS)
    for c in chunks:
        assert len(c["anchor_text"]) <= 120


def test_chunk_index_is_sequential():
    chunks = chunk_sections(SECTIONS)
    for i, c in enumerate(chunks):
        assert c["chunk_index"] == i


def test_large_section_produces_multiple_chunks():
    chunks = chunk_sections(SECTIONS)
    item1a_chunks = [c for c in chunks if "Risk Factors" in c["section"]]
    assert len(item1a_chunks) > 1


def test_short_section_produces_one_chunk():
    chunks = chunk_sections(SECTIONS)
    mda_chunks = [c for c in chunks if "MD&A" in c["section"]]
    assert len(mda_chunks) == 1


def test_section_metadata_preserved():
    chunks = chunk_sections(SECTIONS)
    risk_chunk = next(c for c in chunks if "Risk Factors" in c["section"])
    assert risk_chunk["page_start"] == 5
    assert risk_chunk["page_end"] == 10
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && python -m pytest tests/test_chunker.py -v
```

Expected: `ModuleNotFoundError: No module named 'ingest.chunker'`

- [ ] **Step 3: Implement chunker.py**

```python
# backend/ingest/chunker.py
import uuid

CHUNK_CHARS = 3200   # ~800 tokens at 4 chars/token
OVERLAP_CHARS = 400  # ~100 tokens


def _split_text(text: str) -> list[str]:
    start = 0
    chunks = []
    while start < len(text):
        end = start + CHUNK_CHARS
        if end >= len(text):
            chunks.append(text[start:])
            break
        boundary = text.rfind("\n\n", start, end)
        if boundary <= start:
            boundary = text.rfind("\n", start, end)
        if boundary <= start:
            boundary = end
        chunks.append(text[start:boundary])
        start = boundary - OVERLAP_CHARS
    return [c.strip() for c in chunks if c.strip()]


def chunk_sections(sections: list[dict]) -> list[dict]:
    """
    Returns chunks with fields:
      chunk_id, section, page_start, page_end, text, anchor_text, chunk_index
    """
    chunks = []
    for section in sections:
        for text in _split_text(section["text"]):
            chunks.append({
                "chunk_id": str(uuid.uuid4()),
                "section": section["name"],
                "page_start": section["page_start"],
                "page_end": section["page_end"],
                "text": text,
                "anchor_text": text[:120],
                "chunk_index": len(chunks),
            })
    return chunks
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && python -m pytest tests/test_chunker.py -v
```

Expected: 6 PASSED

- [ ] **Step 5: Commit**

```bash
git add backend/ingest/chunker.py backend/tests/test_chunker.py
git commit -m "feat: section chunker with overlap and tests"
```

---

## Task 4: Chunk Store + Vector Store

**Files:**
- Create: `backend/store/chunk_store.py`
- Create: `backend/store/vector_store.py`

- [ ] **Step 1: Implement chunk_store.py**

```python
# backend/store/chunk_store.py
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
```

- [ ] **Step 2: Implement vector_store.py**

```python
# backend/store/vector_store.py
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
```

- [ ] **Step 3: Smoke test chunk_store manually**

```bash
cd backend && python -c "
from pathlib import Path
import tempfile, os
from store.chunk_store import get_db, save_chunks, save_bm25, load_bm25, load_chunks

with tempfile.TemporaryDirectory() as d:
    db = get_db(Path(d))
    chunks = [{'chunk_id':'abc','section':'Item 1','page_start':1,'page_end':2,
               'text':'risk factors here','anchor_text':'risk factors','cch_text':'context risk','chunk_index':0}]
    save_chunks(db, 'doc1', chunks)
    save_bm25(db, 'doc1', chunks)
    bm25 = load_bm25(db, 'doc1')
    loaded = load_chunks(db)
    assert len(loaded) == 1
    assert loaded[0]['section'] == 'Item 1'
    print('chunk_store OK')
"
```

Expected: `chunk_store OK`

- [ ] **Step 4: Commit**

```bash
git add backend/store/chunk_store.py backend/store/vector_store.py
git commit -m "feat: SQLite chunk store and FAISS vector store"
```

---

## Task 5: CCH Generator

**Files:**
- Create: `backend/ingest/cch.py`

- [ ] **Step 1: Implement cch.py**

```python
# backend/ingest/cch.py
import anthropic
from config import settings

_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

_SYSTEM = (
    "You are a financial document analyst. Given a document excerpt and a chunk from it, "
    "write exactly 2 sentences describing the context: which document, which section, "
    "and what specific financial topic is covered. Be precise and concise."
)


def generate_cch_batch(doc_text: str, chunks: list[dict], filename: str) -> list[dict]:
    """
    Adds 'cch_text' key to each chunk: '{2-sentence context}\n\n{chunk text}'.
    Sends the full document (truncated to 50k chars) with prompt caching on the first
    call; subsequent calls pay only the cache read rate (~10% of input tokens).
    """
    enriched = []
    doc_block = {
        "type": "text",
        "text": f"<document filename='{filename}'>\n{doc_text[:50000]}\n</document>",
        "cache_control": {"type": "ephemeral"},
    }

    for chunk in chunks:
        chunk_block = {
            "type": "text",
            "text": (
                f"<chunk section='{chunk['section']}' "
                f"pages='{chunk['page_start']}-{chunk['page_end']}'>\n"
                f"{chunk['text']}\n</chunk>\n\n"
                "Write 2 sentences of context for this chunk."
            ),
        }
        response = _client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=150,
            system=_SYSTEM,
            messages=[{"role": "user", "content": [doc_block, chunk_block]}],
        )
        context = response.content[0].text.strip()
        enriched.append({**chunk, "cch_text": f"{context}\n\n{chunk['text']}"})

    return enriched
```

- [ ] **Step 2: Manual test with a real API call (requires ANTHROPIC_API_KEY)**

```bash
cd backend && python -c "
import os
from ingest.cch import generate_cch_batch

chunks = [{'chunk_id':'x','section':'Item 1A','page_start':5,'page_end':6,
           'text':'We face risks from competition and macroeconomic factors.',
           'anchor_text':'We face risks','chunk_index':0}]
result = generate_cch_batch('Annual report content here.', chunks, 'test.pdf')
assert 'cch_text' in result[0]
print('CCH OK:', result[0]['cch_text'][:100])
"
```

Expected: `CCH OK:` followed by a 2-sentence context summary.

- [ ] **Step 3: Commit**

```bash
git add backend/ingest/cch.py
git commit -m "feat: CCH generator with Haiku + prompt caching"
```

---

## Task 6: Voyage Embedder

**Files:**
- Create: `backend/ingest/embedder.py`

- [ ] **Step 1: Implement embedder.py**

```python
# backend/ingest/embedder.py
import numpy as np
import voyageai
from config import settings

_client = voyageai.Client(api_key=settings.voyage_api_key)
MODEL = "voyage-finance-2"
BATCH_SIZE = 128


def embed_chunks(chunks: list[dict]) -> np.ndarray:
    """
    Embeds each chunk's 'cch_text'. Returns L2-normalized float32 array
    of shape (n_chunks, embedding_dim) for use with FAISS IndexFlatIP.
    """
    texts = [c["cch_text"] for c in chunks]
    embeddings = []
    for i in range(0, len(texts), BATCH_SIZE):
        result = _client.embed(texts[i : i + BATCH_SIZE], model=MODEL, input_type="document")
        embeddings.extend(result.embeddings)
    vectors = np.array(embeddings, dtype=np.float32)
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    return vectors / norms


def embed_query(query: str) -> np.ndarray:
    """Returns L2-normalized float32 array of shape (1, embedding_dim)."""
    result = _client.embed([query], model=MODEL, input_type="query")
    vec = np.array(result.embeddings[0], dtype=np.float32)
    return (vec / np.linalg.norm(vec)).reshape(1, -1)
```

- [ ] **Step 2: Smoke test with a real API call (requires VOYAGE_API_KEY)**

```bash
cd backend && python -c "
from ingest.embedder import embed_query, embed_chunks
import numpy as np

q = embed_query('What are the risk factors?')
assert q.shape == (1, 1024) or q.shape[1] > 0, 'unexpected shape'
print('embed_query shape:', q.shape)

chunks = [{'cch_text': 'Risk factors section. The company faces competitive pressure.'}]
v = embed_chunks(chunks)
print('embed_chunks shape:', v.shape)
norm = np.linalg.norm(v[0])
assert abs(norm - 1.0) < 1e-5, f'not normalized: {norm}'
print('Embedder OK')
"
```

Expected: `Embedder OK`

- [ ] **Step 3: Commit**

```bash
git add backend/ingest/embedder.py
git commit -m "feat: Voyage voyage-finance-2 embedder"
```

---

## Task 7: Ingest Pipeline + Endpoint

**Files:**
- Create: `backend/ingest/pipeline.py`
- Modify: `backend/main.py`

- [ ] **Step 1: Implement pipeline.py**

```python
# backend/ingest/pipeline.py
import hashlib
from pathlib import Path
from config import settings
from ingest.pdf_extractor import extract_pages
from ingest.section_detector import detect_filing_type, detect_sections
from ingest.chunker import chunk_sections
from ingest.cch import generate_cch_batch
from ingest.embedder import embed_chunks
from store.chunk_store import get_db, save_chunks, save_bm25, chunk_count
from store.vector_store import save_index


def compute_doc_id(pdf_bytes: bytes) -> str:
    return hashlib.sha256(pdf_bytes).hexdigest()


def is_processed(doc_id: str) -> bool:
    d = settings.data_dir / doc_id
    return (d / "chunks.sqlite").exists() and (d / "vectors.faiss").exists()


def ingest_document(pdf_bytes: bytes, filename: str) -> dict:
    doc_id = compute_doc_id(pdf_bytes)

    if is_processed(doc_id):
        doc_dir = settings.data_dir / doc_id
        db = get_db(doc_dir)
        n = chunk_count(db)
        db.close()
        return {
            "doc_id": doc_id, "filename": filename,
            "total_chunks": n, "filing_type": "cached",
            "already_processed": True,
        }

    doc_dir = settings.data_dir / doc_id
    doc_dir.mkdir(parents=True, exist_ok=True)

    pdf_path = doc_dir / "original.pdf"
    pdf_path.write_bytes(pdf_bytes)

    pages = extract_pages(pdf_path)
    filing_type = detect_filing_type(pages)
    sections = detect_sections(pages, filing_type)
    chunks = chunk_sections(sections)

    full_text = "\n".join(p["text"] for p in pages)
    chunks = generate_cch_batch(full_text, chunks, filename)

    vectors = embed_chunks(chunks)

    doc_dir_store = settings.data_dir / doc_id
    db = get_db(doc_dir_store)
    save_chunks(db, doc_id, chunks)
    save_bm25(db, doc_id, chunks)
    db.close()
    save_index(vectors, doc_dir_store / "vectors.faiss")

    return {
        "doc_id": doc_id, "filename": filename,
        "total_chunks": len(chunks), "filing_type": filing_type.value,
        "already_processed": False,
    }
```

- [ ] **Step 2: Add ingest route to main.py**

Append to `backend/main.py`:
```python
from fastapi import UploadFile, File, HTTPException
from models import IngestResponse
from ingest.pipeline import ingest_document


@app.post("/ingest", response_model=IngestResponse)
async def ingest(file: UploadFile = File(...)):
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")
    pdf_bytes = await file.read()
    return ingest_document(pdf_bytes, file.filename or "upload.pdf")
```

- [ ] **Step 3: Test ingest endpoint with a real PDF**

Start the server (`uvicorn main:app --port 8000 --reload` from `backend/`), then:
```bash
curl -X POST http://localhost:8000/ingest \
  -F "file=@/path/to/sample_10k.pdf"
```

Expected JSON:
```json
{"doc_id":"<sha256>","filename":"sample_10k.pdf","total_chunks":142,"filing_type":"10-K","already_processed":false}
```

Re-upload the same file:
```bash
curl -X POST http://localhost:8000/ingest \
  -F "file=@/path/to/sample_10k.pdf"
```

Expected: same `doc_id`, `"already_processed": true`, instant response.

- [ ] **Step 4: Commit**

```bash
git add backend/ingest/pipeline.py backend/main.py
git commit -m "feat: ingest pipeline with dedup and POST /ingest endpoint"
```

---

## Task 8: Dual Search + RRF + Reranker

**Files:**
- Create: `backend/retrieval/search.py`
- Create: `backend/retrieval/rrf.py`
- Create: `backend/retrieval/reranker.py`
- Create: `backend/tests/test_rrf.py`

- [ ] **Step 1: Write failing RRF tests**

```python
# backend/tests/test_rrf.py
from retrieval.rrf import reciprocal_rank_fusion


def test_chunk_in_both_lists_scores_higher():
    semantic = [(0, 0.9), (1, 0.8), (2, 0.7)]
    bm25     = [(2, 5.0), (0, 4.0), (3, 3.0)]
    results = reciprocal_rank_fusion(semantic, bm25)
    result_ids = [r[0] for r in results]
    # chunk 0 appears rank-1 semantic and rank-2 bm25 → should beat chunk 2 or 1 alone
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && python -m pytest tests/test_rrf.py -v
```

Expected: `ModuleNotFoundError: No module named 'retrieval.rrf'`

- [ ] **Step 3: Implement rrf.py**

```python
# backend/retrieval/rrf.py
_K = 60


def reciprocal_rank_fusion(
    semantic_results: list[tuple[int, float]],
    bm25_results: list[tuple[int, float]],
    top_k: int = 20,
) -> list[tuple[int, float]]:
    """
    Merges two ranked lists via RRF. Returns up to top_k (chunk_index, rrf_score) pairs.
    score(chunk) = Σ 1 / (K + rank)  across all lists where chunk appears.
    """
    scores: dict[int, float] = {}
    for rank, (idx, _) in enumerate(semantic_results):
        scores[idx] = scores.get(idx, 0.0) + 1.0 / (_K + rank + 1)
    for rank, (idx, _) in enumerate(bm25_results):
        scores[idx] = scores.get(idx, 0.0) + 1.0 / (_K + rank + 1)
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
```

- [ ] **Step 4: Run RRF tests to verify they pass**

```bash
cd backend && python -m pytest tests/test_rrf.py -v
```

Expected: 4 PASSED

- [ ] **Step 5: Implement search.py**

```python
# backend/retrieval/search.py
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

    # Semantic search
    faiss_index = load_index(doc_dir / "vectors.faiss")
    query_vec = embed_query(query)
    semantic_results = search_index(faiss_index, query_vec, TOP_K)

    # BM25 search
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
```

- [ ] **Step 6: Implement reranker.py**

```python
# backend/retrieval/reranker.py
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
```

- [ ] **Step 7: Commit**

```bash
git add backend/retrieval/search.py backend/retrieval/rrf.py \
        backend/retrieval/reranker.py backend/tests/test_rrf.py
git commit -m "feat: dual search, RRF, and Voyage reranker with tests"
```

---

## Task 9: Chat Generation + Chat Endpoint

**Files:**
- Create: `backend/generation/chat.py`
- Modify: `backend/main.py`

- [ ] **Step 1: Implement generation/chat.py**

```python
# backend/generation/chat.py
import anthropic
from typing import Generator
from config import settings
from models import Message

_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
MODEL = "claude-sonnet-4-6"

_ROLE = """<role>
You are a senior investment banking analyst specializing in SEC filings.
For every factual claim, cite the source with a bold page marker: **[Page N]**.
If the context does not contain enough information to answer the question,
respond: "The document does not contain enough information to answer this question."
Keep answers concise — 3 to 5 sentences unless the question requires more detail.
Answer based ONLY on the content within the <context> tags below.
</role>"""


def _build_system(chunks: list[dict]) -> str:
    lines = []
    for c in chunks:
        lines.append(
            f"[Section: {c['section']} | Pages {c['page_start']}–{c['page_end']}]\n{c['text']}"
        )
    context = "\n\n".join(lines)
    return f"{_ROLE}\n\n<context>\n{context}\n</context>"


def stream_response(messages: list[Message], chunks: list[dict]) -> Generator[str, None, None]:
    system = _build_system(chunks)
    api_messages = [{"role": m.role, "content": m.content} for m in messages]
    with _client.messages.stream(
        model=MODEL,
        max_tokens=1024,
        system=system,
        messages=api_messages,
    ) as stream:
        yield from stream.text_stream
```

- [ ] **Step 2: Add chat route to main.py**

Append to `backend/main.py`:
```python
import json
import time
from fastapi.responses import StreamingResponse
from models import ChatRequest
from retrieval.search import dual_search
from retrieval.rrf import reciprocal_rank_fusion
from retrieval.reranker import rerank
from generation.chat import stream_response


@app.post("/chat")
async def chat(request: ChatRequest):
    doc_dir = settings.data_dir / request.doc_id
    if not doc_dir.exists():
        raise HTTPException(status_code=404, detail="Document not found. Please upload first.")

    query = request.messages[-1].content
    t0 = int(time.time() * 1000)

    semantic, bm25, all_chunks = dual_search(request.doc_id, query)
    rrf = reciprocal_rank_fusion(semantic, bm25)
    candidates = [all_chunks[idx] for idx, _ in rrf]
    top_chunks = rerank(query, candidates)

    citations = [
        {
            "page": c["page_start"],
            "section": c["section"],
            "anchor_text": c["anchor_text"],
            "doc_id": request.doc_id,
        }
        for c in top_chunks
    ]

    collected: list[str] = []

    def generate():
        # First event: citations metadata
        yield f"data: {json.dumps({'type': 'citations', 'value': citations})}\n\n"
        # Stream tokens
        for token in stream_response(request.messages, top_chunks):
            collected.append(token)
            yield f"data: {json.dumps({'type': 'token', 'value': token})}\n\n"
        # Done event
        yield "data: {\"type\": \"done\"}\n\n"
        # Log trace (best-effort, after stream)
        from evals.tracer import log_trace
        log_trace(
            doc_id=request.doc_id,
            query=query,
            conversation_history=[m.dict() for m in request.messages],
            retrieved_chunks=top_chunks,
            response="".join(collected),
            latency_ms=int(time.time() * 1000) - t0,
        )

    return StreamingResponse(generate(), media_type="text/event-stream")
```

- [ ] **Step 3: Add PDF serving route to main.py**

Append to `backend/main.py`:
```python
from fastapi.responses import FileResponse


@app.get("/pdf/{doc_id}")
async def serve_pdf(doc_id: str):
    pdf_path = settings.data_dir / doc_id / "original.pdf"
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="PDF not found.")
    return FileResponse(pdf_path, media_type="application/pdf")
```

- [ ] **Step 4: Test chat endpoint manually**

With the server running and a document ingested (Task 7 Step 3), run:
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"doc_id":"<your_doc_id>","messages":[{"role":"user","content":"What are the main risk factors?"}]}' \
  --no-buffer
```

Expected: SSE stream starting with `data: {"type":"citations",...}` followed by `data: {"type":"token",...}` lines.

- [ ] **Step 5: Commit**

```bash
git add backend/generation/chat.py backend/main.py
git commit -m "feat: Claude Sonnet SSE streaming chat with citations"
```

---

## Task 10: Evals — Tracer + LLM Judge + Feedback Endpoint

**Files:**
- Create: `backend/evals/tracer.py`
- Create: `backend/evals/judge.py`
- Create: `backend/evals/eval_queries.json`
- Create: `backend/tests/test_tracer.py`
- Modify: `backend/main.py`

- [ ] **Step 1: Write failing tracer tests**

```python
# backend/tests/test_tracer.py
import pytest
from pathlib import Path
from unittest.mock import patch


@pytest.fixture
def patched_settings(tmp_data_dir):
    with patch("evals.tracer.settings") as mock:
        mock.data_dir = tmp_data_dir
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && python -m pytest tests/test_tracer.py -v
```

Expected: `ModuleNotFoundError: No module named 'evals.tracer'`

- [ ] **Step 3: Implement tracer.py**

```python
# backend/evals/tracer.py
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
```

- [ ] **Step 4: Run tracer tests to verify they pass**

```bash
cd backend && python -m pytest tests/test_tracer.py -v
```

Expected: 2 PASSED

- [ ] **Step 5: Implement judge.py**

```python
# backend/evals/judge.py
import anthropic
import json
import uuid
from datetime import datetime, timezone
from config import settings
from evals.tracer import get_eval_db

_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

_JUDGE_PROMPT = """You are an evaluation judge for a financial document Q&A system.

<query>{query}</query>
<context>{context}</context>
<response>{response}</response>

Score the response on three dimensions. Reply with ONLY valid JSON — no prose.
{{
  "grounded": 0 or 1,
  "relevant": 1 to 5,
  "concise": 1 to 5
}}
grounded=1 means every factual claim has a [Page N] citation traceable to the context.
relevant=5 means the response directly and fully addresses the query.
concise=5 means appropriately brief (3-5 sentences)."""


def score_unscored_traces(limit: int = 50):
    """Scores up to `limit` traces that have no llm_scores entry yet."""
    db = get_eval_db()
    rows = db.execute("""
        SELECT t.* FROM traces t
        LEFT JOIN llm_scores s ON s.trace_id = t.id
        WHERE s.id IS NULL
        LIMIT ?
    """, (limit,)).fetchall()

    for row in rows:
        chunks = json.loads(row["retrieved_chunks"])
        context = "\n".join(
            f"[Page {c.get('page_start')}] {c.get('text', '')}" for c in chunks
        )[:4000]
        prompt = _JUDGE_PROMPT.format(
            query=row["query"], context=context, response=row["response"]
        )
        resp = _client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=100,
            messages=[{"role": "user", "content": prompt}],
        )
        try:
            scores = json.loads(resp.content[0].text)
            db.execute(
                "INSERT INTO llm_scores VALUES (?,?,?,?,?,?)",
                (
                    str(uuid.uuid4()), row["id"],
                    scores.get("grounded"), scores.get("relevant"), scores.get("concise"),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            db.commit()
        except (json.JSONDecodeError, KeyError):
            pass

    db.close()
```

- [ ] **Step 6: Create eval_queries.json**

```json
[
  "What are the top 3 risk factors disclosed by the company?",
  "Summarize revenue guidance for the next fiscal period.",
  "What is the company's current debt structure and key covenants?",
  "Describe any material litigation or legal proceedings.",
  "What were the primary drivers of revenue growth year-over-year?",
  "What is management's assessment of liquidity and capital resources?",
  "What are the company's main business segments and their performance?",
  "Has the company made any significant acquisitions or divestitures?",
  "What are the key assumptions in the goodwill impairment analysis?",
  "What is the company's effective tax rate and significant deferred tax items?",
  "Describe the company's stock repurchase program and dividend policy.",
  "What off-balance-sheet arrangements are disclosed?",
  "What are the critical accounting policies and estimates?",
  "How does the company describe competition in its markets?",
  "What cybersecurity risks has the company disclosed?",
  "What is the capital expenditure guidance or recent trend?",
  "Are there any related party transactions disclosed?",
  "What is the geographic breakdown of revenue?",
  "What pension or post-retirement benefit obligations exist?",
  "What were the significant changes in working capital this period?"
]
```

Save to `backend/evals/eval_queries.json`.

- [ ] **Step 7: Add feedback route to main.py**

Append to `backend/main.py`:
```python
from models import FeedbackRequest
from evals.tracer import log_feedback


@app.post("/feedback")
async def feedback(request: FeedbackRequest):
    log_feedback(request.trace_id, request.rating, request.comment)
    return {"status": "ok"}
```

- [ ] **Step 8: Commit**

```bash
git add backend/evals/tracer.py backend/evals/judge.py \
        backend/evals/eval_queries.json backend/tests/test_tracer.py \
        backend/main.py
git commit -m "feat: eval tracer, LLM judge, feedback endpoint with tests"
```

---

## Task 11: Next.js Proxy Routes

**Files:**
- Modify: `app/api/upload/route.ts`
- Modify: `app/api/chat/route.ts`
- Create: `app/api/feedback/route.ts`
- Create: `app/api/pdf/[docId]/route.ts`

- [ ] **Step 1: Replace app/api/upload/route.ts**

```typescript
// app/api/upload/route.ts
import { NextRequest, NextResponse } from 'next/server'

export async function POST(request: NextRequest) {
  const formData = await request.formData()
  const response = await fetch('http://localhost:8000/ingest', {
    method: 'POST',
    body: formData,
  })
  const data = await response.json()
  if (!response.ok) {
    return NextResponse.json(data, { status: response.status })
  }
  return NextResponse.json(data)
}
```

- [ ] **Step 2: Replace app/api/chat/route.ts**

```typescript
// app/api/chat/route.ts
import { NextRequest } from 'next/server'

export async function POST(request: NextRequest) {
  const body = await request.json()
  const response = await fetch('http://localhost:8000/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: 'Unknown error' }))
    return new Response(JSON.stringify(err), { status: response.status })
  }
  return new Response(response.body, {
    headers: { 'Content-Type': 'text/event-stream', 'Cache-Control': 'no-cache' },
  })
}
```

- [ ] **Step 3: Create app/api/feedback/route.ts**

```typescript
// app/api/feedback/route.ts
import { NextRequest, NextResponse } from 'next/server'

export async function POST(request: NextRequest) {
  const body = await request.json()
  const response = await fetch('http://localhost:8000/feedback', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  return NextResponse.json(await response.json())
}
```

- [ ] **Step 4: Create app/api/pdf/[docId]/route.ts**

```typescript
// app/api/pdf/[docId]/route.ts
import { NextRequest } from 'next/server'

export async function GET(
  _request: NextRequest,
  { params }: { params: { docId: string } }
) {
  const response = await fetch(`http://localhost:8000/pdf/${params.docId}`)
  if (!response.ok) {
    return new Response('PDF not found', { status: 404 })
  }
  return new Response(response.body, {
    headers: { 'Content-Type': 'application/pdf' },
  })
}
```

- [ ] **Step 5: Update upload-dropzone.tsx to use doc_id**

Open `components/upload-dropzone.tsx`. Find the `handleFileProcessed` call after a successful upload and update it to pass `doc_id` from the response. The existing code calls `onFileProcessed(documentContext, fileName)` — change to pass the `doc_id` returned from FastAPI:

Locate the fetch call to `/api/upload` and update the success handler:
```typescript
const data = await response.json()
// data = { doc_id, filename, total_chunks, filing_type, already_processed }
onFileProcessed(data.doc_id, data.filename)
```

Update `app/page.tsx` so `handleFileProcessed(docId: string, fileName: string)` stores `docId` in state instead of the raw document text. Pass `docId` down to `chat-interface.tsx`.

- [ ] **Step 6: Commit**

```bash
git add app/api/upload/route.ts app/api/chat/route.ts \
        app/api/feedback/route.ts "app/api/pdf/[docId]/route.ts" \
        components/upload-dropzone.tsx app/page.tsx
git commit -m "feat: Next.js proxy routes for ingest, chat, feedback, and PDF"
```

---

## Task 12: PDF Viewer Component + Citation Rendering

**Files:**
- Create: `components/pdf-viewer.tsx`
- Modify: `components/message-bubble.tsx`
- Modify: `components/chat-interface.tsx`

- [ ] **Step 1: Install react-pdf**

```bash
cd repos/10k-analyzer
pnpm add react-pdf
```

- [ ] **Step 2: Create components/pdf-viewer.tsx**

```typescript
// components/pdf-viewer.tsx
'use client'
import { useState } from 'react'
import { Document, Page, pdfjs } from 'react-pdf'
import 'react-pdf/dist/Page/TextLayer.css'
import 'react-pdf/dist/Page/AnnotationLayer.css'

pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.js`

interface PdfViewerProps {
  docId: string
  page: number
  anchorText: string
  onClose: () => void
}

export function PdfViewer({ docId, page, anchorText, onClose }: PdfViewerProps) {
  const pdfUrl = `/api/pdf/${docId}`

  return (
    <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center">
      <div className="bg-white rounded-xl shadow-2xl flex flex-col w-[820px] max-h-[92vh]">
        <div className="flex items-center justify-between px-5 py-3 border-b">
          <div>
            <span className="font-semibold text-sm">Page {page}</span>
            {anchorText && (
              <p className="text-xs text-muted-foreground mt-0.5 max-w-[680px] truncate">
                "{anchorText}"
              </p>
            )}
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 text-xl leading-none"
            aria-label="Close"
          >
            ✕
          </button>
        </div>
        <div className="overflow-auto flex-1 flex justify-center py-4">
          <Document file={pdfUrl}>
            <Page
              pageNumber={page}
              width={760}
              customTextRenderer={({ str }) => {
                const anchor = anchorText.slice(0, 30).toLowerCase()
                if (anchor && str.toLowerCase().includes(anchor.slice(0, 15))) {
                  return `<mark style="background:#fef08a;border-radius:2px">${str}</mark>`
                }
                return str
              }}
            />
          </Document>
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 3: Update components/message-bubble.tsx**

Replace the existing file with this version that adds clickable `**[Page N]**` citations and thumbs-up/down buttons:

```typescript
// components/message-bubble.tsx
'use client'
import ReactMarkdown from 'react-markdown'
import { FileText, User, ThumbsUp, ThumbsDown } from 'lucide-react'

interface Citation {
  page: number
  section: string
  anchor_text: string
  doc_id: string
}

interface MessageBubbleProps {
  role: 'user' | 'assistant'
  content: string
  citations?: Citation[]
  traceId?: string
  onPageClick?: (citation: Citation) => void
  onFeedback?: (traceId: string, rating: 'up' | 'down') => void
}

function CitationButton({
  page,
  citation,
  onPageClick,
}: {
  page: number
  citation: Citation
  onPageClick: (c: Citation) => void
}) {
  return (
    <button
      onClick={() => onPageClick(citation)}
      className="inline font-bold text-primary underline underline-offset-2 hover:opacity-75 cursor-pointer mx-0.5"
    >
      [Page {page}]
    </button>
  )
}

export function MessageBubble({
  role,
  content,
  citations = [],
  traceId,
  onPageClick,
  onFeedback,
}: MessageBubbleProps) {
  const citationMap = Object.fromEntries(citations.map((c) => [c.page, c]))

  const renderContent = () => {
    if (role === 'user') return <p className="text-sm">{content}</p>

    const parts = content.split(/(\*\*\[Page \d+\]\*\*)/g)
    return (
      <div className="text-sm prose prose-sm max-w-none">
        {parts.map((part, i) => {
          const match = part.match(/\*\*\[Page (\d+)\]\*\*/)
          if (match) {
            const page = parseInt(match[1], 10)
            const citation = citationMap[page]
            if (citation && onPageClick) {
              return (
                <CitationButton key={i} page={page} citation={citation} onPageClick={onPageClick} />
              )
            }
            return <strong key={i}>[Page {page}]</strong>
          }
          return (
            <ReactMarkdown key={i} components={{ p: ({ children }) => <span>{children}</span> }}>
              {part}
            </ReactMarkdown>
          )
        })}
      </div>
    )
  }

  if (role === 'user') {
    return (
      <div className="flex justify-end gap-2">
        <div className="bg-primary text-primary-foreground rounded-2xl rounded-tr-sm px-4 py-2 max-w-[75%]">
          {renderContent()}
        </div>
        <div className="w-7 h-7 rounded-full bg-muted flex items-center justify-center shrink-0 mt-1">
          <User className="w-4 h-4" />
        </div>
      </div>
    )
  }

  return (
    <div className="flex gap-2">
      <div className="w-7 h-7 rounded-full bg-primary/10 flex items-center justify-center shrink-0 mt-1">
        <FileText className="w-4 h-4 text-primary" />
      </div>
      <div className="flex flex-col gap-1 max-w-[80%]">
        <div className="bg-muted rounded-2xl rounded-tl-sm px-4 py-3">
          {renderContent()}
        </div>
        {traceId && onFeedback && (
          <div className="flex gap-2 pl-1">
            <button
              onClick={() => onFeedback(traceId, 'up')}
              className="text-muted-foreground hover:text-green-600 transition-colors"
              aria-label="Helpful"
            >
              <ThumbsUp className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={() => onFeedback(traceId, 'down')}
              className="text-muted-foreground hover:text-red-500 transition-colors"
              aria-label="Not helpful"
            >
              <ThumbsDown className="w-3.5 h-3.5" />
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Update components/chat-interface.tsx**

Replace the existing file to use a custom SSE streaming hook, pass `docId`, render `PdfViewer`, and wire feedback:

```typescript
// components/chat-interface.tsx
'use client'
import { useState, useRef, useEffect, useCallback } from 'react'
import { Send, Upload } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { MessageBubble } from './message-bubble'
import { PdfViewer } from './pdf-viewer'

interface Citation {
  page: number
  section: string
  anchor_text: string
  doc_id: string
}

interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  citations?: Citation[]
  traceId?: string
}

interface ChatInterfaceProps {
  docId: string
  fileName: string
  onReset: () => void
}

export function ChatInterface({ docId, fileName, onReset }: ChatInterfaceProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [viewer, setViewer] = useState<Citation | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const sendFeedback = useCallback(async (traceId: string, rating: 'up' | 'down') => {
    await fetch('/api/feedback', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ trace_id: traceId, rating }),
    })
  }, [])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim() || isLoading) return

    const userMessage: ChatMessage = { role: 'user', content: input }
    const updatedMessages = [...messages, userMessage]
    setMessages(updatedMessages)
    setInput('')
    setIsLoading(true)

    const assistantMessage: ChatMessage = { role: 'assistant', content: '' }
    setMessages((prev) => [...prev, assistantMessage])

    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          doc_id: docId,
          messages: updatedMessages.map((m) => ({ role: m.role, content: m.content })),
        }),
      })

      const reader = response.body!.getReader()
      const decoder = new TextDecoder()
      let citations: Citation[] = []
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() ?? ''

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          const raw = line.slice(6).trim()
          if (!raw) continue
          try {
            const event = JSON.parse(raw)
            if (event.type === 'citations') {
              citations = event.value
              setMessages((prev) => {
                const next = [...prev]
                next[next.length - 1] = { ...next[next.length - 1], citations }
                return next
              })
            } else if (event.type === 'token') {
              setMessages((prev) => {
                const next = [...prev]
                const last = next[next.length - 1]
                next[next.length - 1] = { ...last, content: last.content + event.value }
                return next
              })
            }
          } catch {
            // malformed event — skip
          }
        }
      }
    } finally {
      setIsLoading(false)
    }
  }

  const STARTERS = [
    'What are the main risk factors?',
    'Summarize the revenue trends.',
    'What is the debt structure?',
  ]

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b">
        <span className="text-sm font-medium truncate max-w-[300px]">{fileName}</span>
        <Button variant="ghost" size="sm" onClick={onReset}>
          <Upload className="w-4 h-4 mr-1" /> Upload New
        </Button>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
        {messages.length === 0 && (
          <div className="flex flex-col items-center gap-3 mt-12 text-muted-foreground">
            <p className="text-sm">Ask a question about this filing.</p>
            <div className="flex flex-wrap gap-2 justify-center">
              {STARTERS.map((s) => (
                <button
                  key={s}
                  onClick={() => setInput(s)}
                  className="text-xs border rounded-full px-3 py-1 hover:bg-muted transition-colors"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}
        {messages.map((m, i) => (
          <MessageBubble
            key={i}
            role={m.role}
            content={m.content}
            citations={m.citations}
            traceId={m.traceId}
            onPageClick={setViewer}
            onFeedback={sendFeedback}
          />
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <form onSubmit={handleSubmit} className="px-4 py-3 border-t flex gap-2">
        <Input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about the filing..."
          disabled={isLoading}
          className="flex-1"
        />
        <Button type="submit" disabled={isLoading || !input.trim()}>
          <Send className="w-4 h-4" />
        </Button>
      </form>

      {/* PDF Viewer Modal */}
      {viewer && (
        <PdfViewer
          docId={viewer.doc_id}
          page={viewer.page}
          anchorText={viewer.anchor_text}
          onClose={() => setViewer(null)}
        />
      )}
    </div>
  )
}
```

- [ ] **Step 5: Update app/page.tsx to use docId instead of documentContext**

Open `app/page.tsx`. Replace the `documentContext` state with `docId`:

```typescript
// app/page.tsx
'use client'
import { useState } from 'react'
import { UploadDropzone } from '@/components/upload-dropzone'
import { ChatInterface } from '@/components/chat-interface'

export default function Home() {
  const [view, setView] = useState<'upload' | 'chat'>('upload')
  const [docId, setDocId] = useState('')
  const [fileName, setFileName] = useState('')

  function handleFileProcessed(id: string, name: string) {
    setDocId(id)
    setFileName(name)
    setView('chat')
  }

  function handleReset() {
    setDocId('')
    setFileName('')
    setView('upload')
  }

  return (
    <main className="h-screen flex flex-col">
      {view === 'upload' ? (
        <UploadDropzone onFileProcessed={handleFileProcessed} />
      ) : (
        <ChatInterface docId={docId} fileName={fileName} onReset={handleReset} />
      )}
    </main>
  )
}
```

- [ ] **Step 6: Update upload-dropzone.tsx onFileProcessed signature**

In `components/upload-dropzone.tsx`, update the `onFileProcessed` prop type and the fetch success handler:

Find the prop type and update to:
```typescript
onFileProcessed: (docId: string, fileName: string) => void
```

Find the fetch response handler and update to:
```typescript
const data = await response.json()
// data shape: { doc_id, filename, total_chunks, filing_type, already_processed }
onFileProcessed(data.doc_id, data.filename)
```

- [ ] **Step 7: Commit**

```bash
git add components/pdf-viewer.tsx components/message-bubble.tsx \
        components/chat-interface.tsx app/page.tsx \
        components/upload-dropzone.tsx
git commit -m "feat: PDF viewer, clickable citations, feedback buttons, SSE chat"
```

---

## Task 13: Smoke Test + Startup Instructions

**Files:**
- Create: `DEVELOPMENT.md` (only if user requests docs; skip otherwise)

- [ ] **Step 1: Start both services**

Terminal 1 — FastAPI:
```bash
cd repos/10k-analyzer/backend
source .venv/bin/activate   # Windows: .venv\Scripts\activate
uvicorn main:app --port 8000 --reload
```

Terminal 2 — Next.js:
```bash
cd repos/10k-analyzer
pnpm dev
```

- [ ] **Step 2: Upload a 10-K PDF**

Open `http://localhost:3000`. Drag and drop a 10-K PDF. Expect the upload spinner, then transition to the chat view. The doc_id in the title confirms the ingest completed.

- [ ] **Step 3: Ask a question and verify citations**

Type: `What are the main risk factors?`

Verify:
- Response streams token by token
- Response contains `**[Page N]**` markers rendered as bold clickable links
- Clicking a page link opens the PDF viewer modal at that page
- Page text matching the `anchor_text` is highlighted in yellow

- [ ] **Step 4: Test conversational memory**

Ask a follow-up: `Can you expand on the first one?`

Verify the response is contextually relevant to the previous risk factor answer (not starting from scratch).

- [ ] **Step 5: Test thumbs-up feedback**

Click the thumbs-up on any response. Verify `POST /api/feedback` returns `{"status":"ok"}` (check browser DevTools → Network).

- [ ] **Step 6: Test deduplication**

Upload the same PDF again. Verify the response is instant and `already_processed: true` in the network response.

- [ ] **Step 7: Run all backend tests**

```bash
cd repos/10k-analyzer/backend
python -m pytest tests/ -v
```

Expected: All tests pass.

- [ ] **Step 8: Final commit**

```bash
git add .
git commit -m "feat: complete 10-K analyzer backend with RAG, evals, and PDF viewer"
```

---

## Spec Coverage Check

| Spec Requirement | Task |
|---|---|
| Page number citations in bold | Task 12 (message-bubble citation renderer) |
| Clickable page → opens PDF at page + highlights | Tasks 12 (pdf-viewer + citationMap) |
| Hallucination guard | Task 9 (system prompt + XML role block) |
| Brief answers (3-5 sentences) | Task 9 (system prompt) |
| Conversational memory | Task 9 (full messages[] passed every turn) |
| Hybrid RAG (semantic + BM25 + RRF + Voyage rerank) | Tasks 8, 9 |
| Content-addressed dedup (SHA-256) | Task 7 |
| CCH with Haiku + prompt caching | Task 5 |
| voyage-finance-2 embeddings + rerank-2 | Tasks 6, 8 |
| Filing type detection (10-K vs 10-Q) | Task 2 |
| Evals: trace logging | Task 10 |
| Evals: LLM-as-judge (hamel.dev) | Task 10 |
| Evals: human feedback (thumbs up/down) | Tasks 10, 12 |
| Evals: canonical query set | Task 10 |
| Chunks stored locally, gitignored | Task 1 |
| XML-separated system prompt | Task 9 |
