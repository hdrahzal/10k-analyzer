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
