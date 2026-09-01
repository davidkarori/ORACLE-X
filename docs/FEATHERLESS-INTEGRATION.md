# ORACLE X — Featherless Integration

Featherless is the LLM inference layer for Athena, Hades, Hermes and Morpheus.

OpenAI-compatible base URL:

`https://api.featherless.ai/v1`

## Adapter requirements

Create one provider abstraction so agents do not depend directly on SDK/provider implementation details.

Responsibilities:
- authenticate server-side;
- select model;
- submit structured prompts;
- request structured JSON;
- enforce timeouts;
- capture request ID when available;
- capture latency;
- capture token usage when available;
- persist inference trace;
- hash important inputs/outputs.

## Required environment variables

FEATHERLESS_API_KEY
FEATHERLESS_BASE_URL
FEATHERLESS_MODEL_ATHENA
FEATHERLESS_MODEL_HADES
FEATHERLESS_MODEL_HERMES
FEATHERLESS_MODEL_MORPHEUS

Optional:
FEATHERLESS_TEMPERATURE
FEATHERLESS_TIMEOUT_SECONDS

## Headers

Support the provider's recommended identification headers where configured: `HTTP-Referer`, `X-Title`.

## Security

Never expose the key to the browser.

## Determinism

Do not use the LLM for exact financial arithmetic.

## Failure

Timeout, invalid JSON or provider failure must result in an explicit failed agent run and must not authorize execution.
