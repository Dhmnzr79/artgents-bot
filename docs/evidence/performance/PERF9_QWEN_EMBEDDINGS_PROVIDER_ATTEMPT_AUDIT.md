# PERF-9 — Qwen embeddings provider attempt audit

This append-only audit contains operational metadata only. It must never contain API keys,
questions, document text, answers, contacts, SID, or other PII.

## Attempt 1 — native API rejected

- Attempt ID: `perf9-qwen-dev-2026-08-01-01`
- Phase: development calibration
- Requested model: Alibaba Qwen `text-embedding-v4`
- Dimension/output: `1024`, `dense&sparse`
- Endpoint family: workspace-specific native DashScope API, Singapore
- Calls attempted: **1**
- Calls completed: **0**
- Provider input tokens billed/observed: **0**
- Result: HTTP 403 before an embedding response; the remaining 39 planned calls were not made
- Ledger state: `failed_consumed`; the attempt ID cannot be replayed

The failure does not evaluate embedding quality. The configured workspace/key is proven usable by
the existing bot through Alibaba's OpenAI-compatible DashScope endpoint, but native-only features
(`text_type`, Qwen sparse output) are not available to this workspace configuration. No permission
bypass is attempted.

## Corrected method before Attempt 2

The evaluator uses the same Alibaba Qwen `text-embedding-v4` through the configured
workspace-specific OpenAI-compatible DashScope endpoint. It requests dense 1024-dimensional
vectors and verifies the observed response model exactly. The second candidate combines Qwen dense
rank with the existing local lexical rank by weighted reciprocal-rank fusion. Local lexical search
is an algorithm, not an LLM; all model inference remains Chinese/Qwen-only.
