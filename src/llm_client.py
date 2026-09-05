"""Tier 3 (Gemini) and Tier 4 (Groq fallback) LLM classification.

Only reached for messages the keyword and embedding tiers could not confidently
classify. Gemini is primary. On timeout, rate limit, or any Gemini error, the
same request goes to Groq. If both fail, the caller gets UNKNOWN with no
further fallback.
"""

import asyncio
import json
import os
import time

from google import genai
from google.genai import types as genai_types
from groq import AsyncGroq
from pydantic import BaseModel, ValidationError

from src.models import RootCause

GEMINI_MODEL = "gemini-3.6-flash"  # gemini-2.0-flash retired, see FAILURE_LOG
GROQ_MODEL = "openai/gpt-oss-120b"  # llama-3.3-70b-versatile retired by Groq, see FAILURE_LOG
GEMINI_COST_PER_CALL_USD = 0.0001
GROQ_COST_PER_CALL_USD = 0.0
REQUEST_TIMEOUT_SECONDS = 10


class LLMClassification(BaseModel):
    root_cause: RootCause
    reasoning: str


class ClassificationResult(BaseModel):
    root_cause: RootCause
    reasoning: str
    provider_used: str | None
    latency_ms: int
    cost_estimate_usd: float


ROOT_CAUSE_VALUES = [c.value for c in RootCause if c != RootCause.UNKNOWN]

PROMPT_TEMPLATE = """A UPI payment transaction failed with this raw error message from
the upstream bank or PSP: "{error_message}"

Bank code involved: {bank_code}

Classify the root cause into exactly one of these categories:
{categories}

Respond with JSON only, in this exact shape:
{{"root_cause": "<one of the categories above>", "reasoning": "<one sentence>"}}
"""


def _build_prompt(error_message: str, bank_code: str) -> str:
    return PROMPT_TEMPLATE.format(
        error_message=error_message,
        bank_code=bank_code,
        categories=", ".join(ROOT_CAUSE_VALUES),
    )


def _parse_llm_json(raw_text: str) -> LLMClassification:
    data = json.loads(raw_text)
    return LLMClassification.model_validate(data)


class LLMClient:
    def __init__(self) -> None:
        gemini_key = os.environ["GEMINI_API_KEY"]
        groq_key = os.environ["GROQ_API_KEY"]
        self._gemini = genai.Client(api_key=gemini_key)
        self._groq = AsyncGroq(api_key=groq_key)

    async def _call_gemini(self, prompt: str) -> LLMClassification:
        response = await asyncio.wait_for(
            self._gemini.aio.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
                config=genai_types.GenerateContentConfig(
                    response_mime_type="application/json",
                    http_options=genai_types.HttpOptions(
                        timeout=REQUEST_TIMEOUT_SECONDS * 1000
                    ),
                ),
            ),
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        return _parse_llm_json(response.text)

    async def _call_groq(self, prompt: str) -> LLMClassification:
        response = await asyncio.wait_for(
            self._groq.chat.completions.create(
                model=GROQ_MODEL,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
            ),
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        return _parse_llm_json(response.choices[0].message.content)

    async def classify(self, error_message: str, bank_code: str) -> ClassificationResult:
        prompt = _build_prompt(error_message, bank_code)
        start = time.monotonic()

        try:
            result = await self._call_gemini(prompt)
            latency_ms = int((time.monotonic() - start) * 1000)
            return ClassificationResult(
                root_cause=result.root_cause,
                reasoning=result.reasoning,
                provider_used="gemini",
                latency_ms=latency_ms,
                cost_estimate_usd=GEMINI_COST_PER_CALL_USD,
            )
        except (Exception, ValidationError) as gemini_error:
            gemini_failure_reason = str(gemini_error)

        try:
            result = await self._call_groq(prompt)
            latency_ms = int((time.monotonic() - start) * 1000)
            return ClassificationResult(
                root_cause=result.root_cause,
                reasoning=result.reasoning,
                provider_used="groq",
                latency_ms=latency_ms,
                cost_estimate_usd=GROQ_COST_PER_CALL_USD,
            )
        except (Exception, ValidationError) as groq_error:
            latency_ms = int((time.monotonic() - start) * 1000)
            return ClassificationResult(
                root_cause=RootCause.UNKNOWN,
                reasoning=(
                    f"Both providers failed. Gemini: {gemini_failure_reason}. "
                    f"Groq: {groq_error}."
                ),
                provider_used=None,
                latency_ms=latency_ms,
                cost_estimate_usd=0.0,
            )
