# Roadmap

What a 6-month version of this would look like, if given the runway.

## 1. Real Razorpay test-mode data instead of synthetic

The synthetic generator's distribution is a reasonable guess biased toward
bank timeouts and network errors, matching publicly reported NPCI failure
patterns, but it is still a guess. Wiring this into Razorpay's test-mode
APIs would validate whether the synthetic distribution and the keyword and
embedding vocabularies actually match how real upstream error messages look,
or whether they need retuning.

## 2. A learning loop instead of a static policy table

The retry policy right now is six hardcoded rows. Given real historical
outcomes per merchant, a genuinely useful next step is a per-merchant model
that adjusts `expected_recovery_rate` and even `intervals_seconds` from
actual observed patterns instead of one fixed table for every merchant on
the platform.

## 3. Running the classifier and audit log inside a TEE

Merchant payment data is PII. Real production data would need verifiable
inference guarantees, something like AWS Nitro Enclaves for the classifier
and audit log. This project uses synthetic data, so a TEE would have been
pure overhead for the buildathon, but it is a real requirement before any
of this touches actual transaction data.

## 4. Interventions beyond retry

Retrying is not the only lever. WhatsApp nudges for insufficient-balance
failures, alternate-rail suggestions when UPI itself is the problem, and
promise-to-pay flows for B2B receivables are all interventions a real
recovery product would need that a batch retry simulation does not cover.
