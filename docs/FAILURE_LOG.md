# Failure Log

## FAILURE 1: 2026-09-05 Groq retired llama-3.3-70b-versatile

**What happened:** Spec called for Groq's Llama 3.3 70B as the Tier 4 fallback model.
Live call returned a 404: "The model `llama-3.3-70b-versatile` does not exist or you
do not have access to it." Listed Groq's actual model catalog and the Llama 3.3 line
is gone entirely, only prompt-guard variants remain under the llama name.

**Impact:** Tier 4 fallback would have failed on every single call, meaning any
transaction where Gemini also failed would silently end up UNKNOWN even though a
working fallback provider existed.

**Fix:** Asked Chandan directly rather than guessing. Picked openai/gpt-oss-120b,
closest capability tier to the original pick and still on Groq's free tier.

**Measured improvement:** Groq fallback path now returns valid classifications
instead of 404s, confirmed in a live smoke test.

**Still unsolved:** Model catalogs on both providers move fast. No pinned model
version guarantee, next redeploy could hit this again.

## FAILURE 2: 2026-09-05 Gemini 2.0 Flash retired

**What happened:** Live call to gemini-2.0-flash returned a 404: "This model
models/gemini-2.0-flash is no longer available. Please update your code to use
models/gemini-3.6-flash." Same class of issue as Failure 1, just on the primary
provider instead of the fallback.

**Impact:** Every Tier 3 call would have failed over to Tier 4 (Groq), meaning the
"LLM primary" path in the architecture would never actually run, defeating the whole
point of having a fast, cheap primary model.

**Fix:** Switched GEMINI_MODEL to gemini-3.6-flash per Google's own error message.
Not treated as a judgment call since the API dictated the exact replacement.

**Measured improvement:** Live smoke test call 1 above landed on Gemini
(provider_used=gemini, latency 3743ms, cost $0.0001), confirming the primary path
now actually gets exercised.

**Still unsolved:** None, this one had a single correct answer.

## FAILURE 3: 2026-09-05 GenerateContentConfig rejected a top-level timeout field

**What happened:** First LLM client draft passed `timeout=10000` directly into
`genai_types.GenerateContentConfig(...)`. Pydantic raised
`extra_forbidden: Extra inputs are not permitted`, because timeout belongs under a
nested `http_options` object, not as a top-level config field.

**Impact:** Every single Gemini call failed before it left the process, so all
traffic silently fell through to Groq during the first round of live testing. Looked
like an API-side outage until the traceback was read carefully.

**Fix:** Moved the timeout into `genai_types.HttpOptions(timeout=...)` passed as
`config.http_options`, and added `asyncio.wait_for` around both provider calls as a
belt-and-suspenders timeout that does not depend on SDK internals.

**Measured improvement:** Gemini calls succeed now, confirmed via direct
`_call_gemini` smoke test before re-testing the full `classify()` path.

**Still unsolved:** None.
