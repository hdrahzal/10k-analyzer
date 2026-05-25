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
