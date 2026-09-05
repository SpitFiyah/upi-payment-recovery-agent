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
MOCK_PROVIDER = "mock"


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


def _mock_classify(error_message: str) -> LLMClassification:
    message = error_message.lower()
    if any(term in message for term in ("timeout", "timed out", "server busy", "slow")):
        root_cause = RootCause.BANK_TIMEOUT
        reasoning = "Mock fallback inferred bank timeout from the error text"
    elif any(term in message for term in ("insufficient", "balance", "low funds")):
        root_cause = RootCause.INSUFFICIENT_BALANCE
        reasoning = "Mock fallback inferred insufficient balance from the error text"
    elif any(term in message for term in ("mandate", "autopay", "e-mandate")):
        root_cause = RootCause.MANDATE_ERROR
        reasoning = "Mock fallback inferred mandate error from the error text"
    elif any(term in message for term in ("limit", "exceeded", "maximum")):
        root_cause = RootCause.LIMIT_EXCEEDED
        reasoning = "Mock fallback inferred a limit breach from the error text"
    elif any(term in message for term in ("network", "connection", "reset", "unreachable")):
        root_cause = RootCause.NETWORK_ERROR
        reasoning = "Mock fallback inferred a network issue from the error text"
    else:
        root_cause = RootCause.UNKNOWN
        reasoning = "Mock fallback could not infer a confident root cause"

    return LLMClassification(root_cause=root_cause, reasoning=reasoning)


class LLMClient:
    def __init__(self) -> None:
        self._demo_mode = os.getenv("DEMO_MODE", "0") == "1"
        gemini_key = os.getenv("GEMINI_API_KEY")
        groq_key = os.getenv("GROQ_API_KEY")
        if not gemini_key and not groq_key:
            self._demo_mode = True
        self._gemini = genai.Client(api_key=gemini_key) if gemini_key and not self._demo_mode else None
        self._groq = AsyncGroq(api_key=groq_key) if groq_key and not self._demo_mode else None

    async def _call_mock(self, error_message: str) -> LLMClassification:
        await asyncio.sleep(0.02)
        return _mock_classify(error_message)

    async def _call_gemini(self, prompt: str) -> LLMClassification:
        if self._gemini is None:
            raise RuntimeError("Gemini is unavailable")
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
        if self._groq is None:
            raise RuntimeError("Groq is unavailable")
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

        if self._demo_mode:
            result = await self._call_mock(error_message)
            latency_ms = int((time.monotonic() - start) * 1000)
            return ClassificationResult(
                root_cause=result.root_cause,
                reasoning=result.reasoning,
                provider_used=MOCK_PROVIDER,
                latency_ms=latency_ms,
                cost_estimate_usd=0.0,
            )

        gemini_failure_reason: str | None = None

        if self._gemini is not None:
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

        if self._groq is not None:
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

        result = await self._call_mock(error_message)
        latency_ms = int((time.monotonic() - start) * 1000)
        return ClassificationResult(
            root_cause=result.root_cause,
            reasoning=result.reasoning,
            provider_used=MOCK_PROVIDER,
            latency_ms=latency_ms,
            cost_estimate_usd=0.0,
        )
