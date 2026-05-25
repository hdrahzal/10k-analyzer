import anthropic
import json
import uuid
from datetime import datetime, timezone
from config import settings
from evals.tracer import get_eval_db

_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

_JUDGE_PROMPT = """You are an evaluation judge for a financial document Q&A system.

<query>{query}</query>
<context>{context}</context>
<response>{response}</response>

Score the response on three dimensions. Reply with ONLY valid JSON - no prose.
{{
  "grounded": 0 or 1,
  "relevant": 1 to 5,
  "concise": 1 to 5
}}
grounded=1 means every factual claim has a [Page N] citation traceable to the context.
relevant=5 means the response directly and fully addresses the query.
concise=5 means appropriately brief (3-5 sentences)."""


def score_unscored_traces(limit: int = 50):
    """Scores up to `limit` traces that have no llm_scores entry yet."""
    db = get_eval_db()
    rows = db.execute("""
        SELECT t.* FROM traces t
        LEFT JOIN llm_scores s ON s.trace_id = t.id
        WHERE s.id IS NULL
        LIMIT ?
    """, (limit,)).fetchall()

    for row in rows:
        chunks = json.loads(row["retrieved_chunks"])
        context = "\n".join(
            f"[Page {c.get('page_start')}] {c.get('text', '')}" for c in chunks
        )[:4000]
        prompt = _JUDGE_PROMPT.format(
            query=row["query"], context=context, response=row["response"]
        )
        resp = _client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=100,
            messages=[{"role": "user", "content": prompt}],
        )
        try:
            scores = json.loads(resp.content[0].text)
            db.execute(
                "INSERT INTO llm_scores VALUES (?,?,?,?,?,?)",
                (
                    str(uuid.uuid4()), row["id"],
                    scores.get("grounded"), scores.get("relevant"), scores.get("concise"),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            db.commit()
        except (json.JSONDecodeError, KeyError):
            pass

    db.close()
