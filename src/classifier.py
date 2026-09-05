"""4-tier cascade orchestrator. AI is the last resort, not the first tool.

Runs preprocessing, then Tier 1 (keyword), Tier 2 (embedding), and only on
double escalation, Tier 3/4 (Gemini then Groq via LLMClient).
"""

import time

from pydantic import BaseModel

from src import tier_embedding, tier_keyword
from src.llm_client import LLMClient
from src.models import RootCause, Transaction
from src.preprocessing import enrich


class CascadeResult(BaseModel):
    root_cause: RootCause
    tier_used: str | None  # "keyword" | "embedding" | "gemini" | "groq" | None
    reasoning: str
    cost_estimate_usd: float
    latency_ms: int


async def classify(transaction: Transaction, llm_client: LLMClient) -> tuple[Transaction, CascadeResult]:
    start = time.monotonic()
    enriched = enrich(transaction)

    keyword_hit = tier_keyword.classify(enriched.raw_error_message)
    if keyword_hit is not None:
        latency_ms = int((time.monotonic() - start) * 1000)
        return enriched, CascadeResult(
            root_cause=keyword_hit,
            tier_used="keyword",
            reasoning=f"Tier 1 keyword match for {keyword_hit.value}",
            cost_estimate_usd=0.0,
            latency_ms=latency_ms,
        )

    embedding_hit = tier_embedding.classify(enriched.raw_error_message)
    if embedding_hit is not None:
        latency_ms = int((time.monotonic() - start) * 1000)
        return enriched, CascadeResult(
            root_cause=embedding_hit,
            tier_used="embedding",
            reasoning=f"Tier 2 embedding match for {embedding_hit.value} above similarity threshold",
            cost_estimate_usd=0.0,
            latency_ms=latency_ms,
        )

    llm_result = await llm_client.classify(enriched.raw_error_message, enriched.bank_code)
    latency_ms = int((time.monotonic() - start) * 1000)
    return enriched, CascadeResult(
        root_cause=llm_result.root_cause,
        tier_used=llm_result.provider_used,
        reasoning=llm_result.reasoning,
        cost_estimate_usd=llm_result.cost_estimate_usd,
        latency_ms=latency_ms,
    )
