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
        next_start = boundary - OVERLAP_CHARS
        start = next_start if next_start > start else boundary
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
