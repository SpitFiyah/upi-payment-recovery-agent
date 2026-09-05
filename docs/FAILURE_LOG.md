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

## FAILURE 4: 2026-09-05 Gemini failed on every single batch run despite working standalone

**What happened:** A lone `_call_gemini` smoke test succeeds reliably. But every full
200-transaction batch run so far, at both 10 and 3 concurrent LLM calls, shows 0%
of the ~20 LLM-tier classifications landing on Gemini and 100% falling to Groq.
Lowering concurrency from 10 to 3 changed the split from 0/20 to 1/20 gemini,
not enough to call it a concurrency problem.

**Impact:** None on correctness, since Groq caught every one of them and the
batch completed cleanly. But it means the "LLM primary" path in the architecture
has not actually been exercised in a full run yet, only in isolated single calls,
so the panel's Q1 claim about Gemini being primary is honest on paper but not
demonstrated in the numbers this batch produced.

**Fix:** None applied. This looks like a rate limit or quota ceiling on the
gemini-3.6-flash free tier for this specific API key, most likely exhausted by
the volume of manual testing done earlier tonight while debugging Failures 1
through 3. Not something the code can work around without adding retry-with-
backoff logic on the Gemini call itself, which was judged out of scope for
tonight given the deadline.

**Measured improvement:** None yet.

**Still unsolved:** Gemini's real-world hit rate in the demo batch is 0%, Groq is
carrying 100% of LLM-tier traffic. Worth trying a fresh API key or waiting out
the quota window before recording the pitch video, so the video can show at
least one genuine Gemini success rather than only Groq.
