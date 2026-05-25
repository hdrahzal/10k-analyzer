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
    The full document (truncated to 50k chars) is sent with cache_control on every
    call; Anthropic's ephemeral prompt cache means only the first call pays full
    input cost, subsequent calls pay the cache read rate (~10% of input tokens).
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
