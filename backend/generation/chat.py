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
Keep answers concise - 3 to 5 sentences unless the question requires more detail.
Answer based ONLY on the content within the <context> tags below.
</role>"""


def _build_system(chunks: list[dict]) -> str:
    lines = []
    for c in chunks:
        lines.append(
            f"[Section: {c['section']} | Pages {c['page_start']}-{c['page_end']}]\n{c['text']}"
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
