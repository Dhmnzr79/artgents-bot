# PERF-9 — Qwen embeddings blind holdout gold protocol

## Status

`HOLDOUT_GOLD_FROZEN_PENDING_COMMIT`. This checkpoint creates and validates the
questions and human-authored gold only. No lexical, BM25, embedding, hybrid,
reranking, LLM, provider, network, or runtime execution is allowed against these
60 questions before the freeze commit exists.

## Model policy

Only Chinese models are allowed in this bot. The sole embedding candidate for
the next checkpoint is Alibaba Qwen `text-embedding-v4` (Qwen3-Embedding
series). An OpenAI-compatible SDK may be used only as the DashScope API
transport format; it does not authorize an OpenAI model or any Western embedding
model. Names such as `text-embedding-3-small`, `text-embedding-3-large`,
OpenAI, Cohere, Voyage, Gemini, and Jina are not candidates.

## Independence rules

1. The 60 synthetic query wordings were authored before running any retrieval
   candidate against them.
2. Gold was authored from the canonical `clients/demo/md/**` documents, not
   from candidate rankings.
3. The query index contains no topic, service, expected document, or other
   oracle hint. It contains only scenario ID, scenario class, and wording.
4. Gold is stored separately and intentionally contains no query text.
5. Thresholds and hybrid weights must not be tuned on this holdout. Any tuning
   needs a separate development set and a second untouched holdout.
6. The query and gold files must be committed before the evaluator imports or
   reads the query file.

## Gold meaning

- `allowed_retrieval_md_refs` is the complete set of one-document retrieval
  answers accepted for this checkpoint.
- `forbidden_retrieval_md_refs` pins plausible but unsafe semantic stretches.
- `fallback_required=true` means that selecting one narrow MD document is not
  accepted. A wider/full package or honest unsupported-answer path is safe.
- Boundary-sensitive rows evaluate retrieval relevance only. They never bypass
  the existing Medical Boundary or authorize personalised medical advice.

## Next gate

Provider/network calls remain zero at this checkpoint. Calling Alibaba
DashScope/Qwen, downloading any model, or generating embeddings requires a
separate explicit owner LIVE/network GO after this gold freeze is committed.
That later run must pin the model name, dimension, endpoint region, input hashes,
output hashes, token usage, duration, and cost without storing contacts, SID,
questions, answers, or other PII in provider-call audit logs.
