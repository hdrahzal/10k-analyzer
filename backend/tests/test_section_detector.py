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
