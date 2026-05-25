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
