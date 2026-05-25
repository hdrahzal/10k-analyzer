# backend/main.py
import json
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from config import settings
from models import IngestResponse, ChatRequest, FeedbackRequest
from ingest.pipeline import ingest_document
from retrieval.search import dual_search
from retrieval.rrf import reciprocal_rank_fusion
from retrieval.reranker import rerank
from generation.chat import stream_response
from evals.tracer import log_feedback


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(title="10-K Analyzer API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)


@app.post("/ingest", response_model=IngestResponse)
async def ingest(file: UploadFile = File(...)):
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")
    pdf_bytes = await file.read()
    return ingest_document(pdf_bytes, file.filename or "upload.pdf")


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
        yield f"data: {json.dumps({'type': 'citations', 'value': citations})}\n\n"
        for token in stream_response(request.messages, top_chunks):
            collected.append(token)
            yield f"data: {json.dumps({'type': 'token', 'value': token})}\n\n"
        yield "data: {\"type\": \"done\"}\n\n"
        from evals.tracer import log_trace
        log_trace(
            doc_id=request.doc_id,
            query=query,
            conversation_history=[m.model_dump() for m in request.messages],
            retrieved_chunks=top_chunks,
            response="".join(collected),
            latency_ms=int(time.time() * 1000) - t0,
        )

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.get("/pdf/{doc_id}")
async def serve_pdf(doc_id: str):
    pdf_path = settings.data_dir / doc_id / "original.pdf"
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="PDF not found.")
    return FileResponse(pdf_path, media_type="application/pdf")


@app.post("/feedback")
async def feedback(request: FeedbackRequest):
    log_feedback(request.trace_id, request.rating, request.comment)
    return {"status": "ok"}
