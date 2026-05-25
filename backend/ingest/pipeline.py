import hashlib
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

    db = get_db(doc_dir)
    save_chunks(db, doc_id, chunks)
    save_bm25(db, doc_id, chunks)
    db.close()
    save_index(vectors, doc_dir / "vectors.faiss")

    return {
        "doc_id": doc_id, "filename": filename,
        "total_chunks": len(chunks), "filing_type": filing_type.value,
        "already_processed": False,
    }
