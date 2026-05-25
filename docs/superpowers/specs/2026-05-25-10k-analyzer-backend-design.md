# 10-K Analyzer Backend Design
**Date:** 2026-05-25
**Status:** Approved

---

## 1. Architecture Overview

Two processes run side by side:

**Next.js (port 3000)** — existing frontend, unchanged except:
- `/api/upload` and `/api/chat` become thin proxies forwarding to FastAPI
- `react-pdf` added for the in-app PDF viewer with text-layer highlighting
- Thumbs-up/down feedback buttons added to each AI response bubble

**FastAPI (port 8000)** — new Python service owning all backend logic.

### API Endpoints

| Endpoint | Method | Purpose |
|---|---|---|
| `/ingest` | POST | Receive PDF, hash it, process + embed if new, return `doc_id` |
| `/chat` | POST | Query + `doc_id` + history → streamed answer with citations |
| `/pdf/{doc_id}/page/{page}` | GET | Serve original PDF page for viewer |
| `/feedback` | POST | Record human thumbs-up/down on a response |

### Storage Layout

All under `repos/10k-analyzer/data/` — gitignored.

```
data/
  {doc_id}/           # doc_id = SHA-256 of PDF bytes
    original.pdf
    chunks.sqlite     # chunk text, metadata, serialized BM25 index
    vectors.faiss     # FAISS index of Voyage embeddings
  evals.sqlite        # traces + LLM scores + human feedback (all docs)
  eval_queries.json   # 20 canonical analyst questions for regression evals
```

---

## 2. Ingestion Pipeline

Triggered by `POST /ingest`. Steps run in order; Step 1 short-circuits the rest if the document is already processed.

### Step 1 — Deduplication
SHA-256 hash the PDF bytes. If `data/{hash}/chunks.sqlite` exists, return `{ doc_id: hash }` immediately — no reprocessing.

### Step 2 — Filing Type Detection
Scan the first 5 pages of extracted text for markers:
- 10-K: `"FORM 10-K"`, `"annual report"`, `"Item 1A"`, `"Item 7"`
- 10-Q: `"FORM 10-Q"`, `"quarterly report"`, `"Part I"`, `"Part II"`

Result determines which `sec-parser` section schema to apply.

### Step 3 — Section-Aware Chunking
Use `pdfplumber` to extract text page-by-page, then detect section boundaries using regex patterns matching standard 10-K item headers (`Item\s+1A`, `Item\s+7`, `PART\s+II`, etc.) and 10-Q part headers. Each matched header starts a new section. Split each section into chunks of ~800 tokens with 100-token overlap, breaking at paragraph boundaries.

Note: `sec-parser` (alphanome) targets SEC EDGAR HTML, not user-uploaded PDFs — `pdfplumber` + regex is the correct approach for uploaded PDF files.

Each chunk carries:
```json
{
  "chunk_id": "uuid",
  "doc_id": "sha256hash",
  "section": "Item 7 – MD&A",
  "page_start": 42,
  "page_end": 43,
  "text": "...",
  "anchor_text": "first 120 characters of chunk for frontend highlight search"
}
```

### Step 4 — Contextual Chunk Headers (CCH)
For each chunk, call `claude-haiku-4-5-20251001` to generate a 2-sentence context summary prepended to the chunk before embedding.

**Prompt caching:** The full document text is passed with `"cache_control": {"type": "ephemeral"}` on the first call. All subsequent chunk CCH calls reuse the cached document — only the specific chunk text changes per call. Reduces CCH generation cost by ~85% on a typical 10-K.

Example CCH output:
> "This chunk is from the MD&A section of Apple's FY2024 10-K, discussing year-over-year Services revenue growth. It contains management's commentary on subscription attach rates and geographic expansion."

### Step 5 — Voyage Embedding + Index Build
- Embed each `{CCH context}\n{chunk text}` string using `voyage-finance-2`
- Store vectors in a FAISS `IndexFlatIP` (inner product / cosine similarity after L2 normalization)
- Store chunk text + metadata in `chunks.sqlite`
- Build a `rank_bm25` BM25 index over raw chunk text, serialize to `chunks.sqlite` as a blob

**Estimated processing time:** ~2 minutes for a 150-chunk 10-K (dominated by Haiku CCH calls).

---

## 3. Retrieval Pipeline

Triggered per query inside `POST /chat`.

### Step 1 — Dual Search (parallel)
- **Semantic:** Embed query with `voyage-finance-2` → FAISS cosine search over CCH-enriched embeddings → top 20 chunks by cosine similarity
- **BM25:** Deserialize BM25 index from SQLite → score all chunks against query tokens (raw chunk text) → top 20 chunks by BM25 score

The two searches are complementary: semantic search benefits from the rich CCH context in the embeddings; BM25 benefits from exact term matching in the raw text (e.g., ticker symbols, specific financial line items).

### Step 2 — Reciprocal Rank Fusion (RRF)
Merge both ranked lists:
```
rrf_score(chunk) = 1/(k + semantic_rank) + 1/(k + bm25_rank)   # k=60
```
Produces a unified ranking of up to 40 candidates. Chunks that appear in both lists score higher.

### Step 3 — Voyage Reranking
Pass top 20 RRF candidates + original query to `voyageai.rerank()` (`rerank-2` model). Take top 5 by rerank score.

### Step 4 — Context Assembly
The 5 chunks are formatted with section and page labels, then injected into the `<context>` block of the system prompt (see Section 4).

### Step 5 — Citation Metadata
Alongside the streamed response, the endpoint returns a `citations` array:
```json
[
  { "page": 42, "section": "Item 7 – MD&A", "anchor_text": "...", "doc_id": "..." },
  ...
]
```
The frontend parses `**[Page 42]**` markers in the response text and renders them as clickable buttons. On click, the `react-pdf` viewer opens to that page and highlights `anchor_text` via the pdf.js text-layer search API.

---

## 4. Generation & Chat

### System Prompt
XML tags separate the analyst role from the retrieved document context so Claude clearly distinguishes its persona/rules from the source material:

```xml
<role>
You are a senior investment banking analyst specializing in SEC filings.
For every factual claim, cite the source with a bold page marker: **[Page N]**.
If the context does not contain enough information to answer the question,
respond: "The document does not contain enough information to answer this question."
Keep answers concise — 3 to 5 sentences unless the question requires more detail.
Answer based ONLY on the content within the <context> tags below.
</role>

<context>
[Section: Item 7 – MD&A | Pages 42–43]
{chunk text}

[Section: Item 1A – Risk Factors | Pages 18–19]
{chunk text}
...
</context>
```

### Conversational Memory
Full `messages[]` array passed to Claude on every turn (Anthropic messages API standard pattern). No summarization required for typical analyst sessions (10–20 turns). Frontend's `useChat` hook tracks history; backend receives and forwards the full array.

### Model
`claude-sonnet-4-6` for all chat responses.

### Streaming
`StreamingResponse` via FastAPI with Anthropic SDK streaming client. Frontend `useChat` hook handles SSE natively — no changes needed.

### Hallucination Guard
Enforced at the prompt level: retrieved chunk content is the only context provided. The system prompt explicitly forbids answering outside that context. No post-hoc filtering needed.

---

## 5. Evals (hamel.dev methodology)

### Trace Logging
Every `/chat` request writes to `data/evals.sqlite` before streaming:

**`traces` table:**
```sql
id, doc_id, session_id, timestamp,
query TEXT,
conversation_history JSON,
retrieved_chunks JSON,   -- [{chunk_id, page, section, semantic_rank, bm25_rank, rrf_score, rerank_score}]
response TEXT,
latency_ms INTEGER,
model TEXT,
embedding_model TEXT
```

### LLM-as-Judge (automated)
Background job (triggered manually or on schedule) reads unscored traces and calls `claude-haiku-4-5-20251001` with a structured rubric per trace:

| Dimension | Scale | Description |
|---|---|---|
| Grounded | 0/1 | Every claim traceable to a cited chunk |
| Relevant | 1–5 | Answer addresses the question |
| Concise | 1–5 | Appropriately brief |

Results written to **`llm_scores`** table linked to `traces.id`.

### Human Feedback
`POST /feedback` accepts `{ trace_id, rating: "up"|"down", comment? }`.
Written to **`human_feedback`** table linked to `traces.id`.
Frontend renders thumbs-up/down on each AI response bubble.

### Regression Eval Set
`data/eval_queries.json` — 20 canonical analyst questions seeded at init time:
- "What are the top 3 risk factors?"
- "Summarize revenue guidance for next fiscal year"
- "What is the company's current debt structure?"
- "Describe any material litigation or legal proceedings"
- *(+ 16 more covering standard 10-K/10-Q sections)*

Used to run retrieval + generation regression checks when the pipeline changes.

---

## 6. Key Dependencies

| Package | Purpose |
|---|---|
| `fastapi` + `uvicorn` | Python API server |
| `anthropic` | Claude Haiku (CCH) + Claude Sonnet (chat) |
| `voyageai` | `voyage-finance-2` embeddings + `rerank-2` reranking |
| `pdfplumber` | PDF text extraction + section detection |
| `rank_bm25` | BM25 index |
| `faiss-cpu` | Vector similarity search |
| `sqlite3` (stdlib) | Chunk metadata + eval storage |
| `react-pdf` | Frontend PDF viewer with text layer |

### Environment Variables
```
ANTHROPIC_API_KEY=
VOYAGE_API_KEY=
DATA_DIR=./data          # default, overridable
FASTAPI_PORT=8000
```

---

## 7. What Is Not in Scope

- Authentication / user accounts
- Multi-user sessions (single analyst at a time)
- Cloud deployment / containerization
- Multi-document library (next iteration)
- Coordinate-based PDF highlighting (text-search highlighting chosen instead)
