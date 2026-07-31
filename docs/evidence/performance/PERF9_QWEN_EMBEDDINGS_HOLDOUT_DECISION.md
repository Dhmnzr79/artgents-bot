# PERF-9 — Qwen embeddings blind holdout decision

## Verdict

`QWEN_EMBEDDINGS_HOLDOUT_FAIL_NO_RUNTIME_CANDIDATE`

Alibaba Qwen `text-embedding-v4` substantially improves semantic ranking over the original plain
token-overlap retrieval, but the independently frozen holdout rejects both tested runtime shapes.
Qwen dense produced four critical false-narrow decisions. Qwen dense plus local lexical
reciprocal-rank fusion produced two while falling back on 75% of questions. The binding safety bar
is zero critical false narrowing, so neither candidate is authorised for Scoped Composer.

## What this means in product language

- Embeddings understand paraphrases better, but they still confuse small facts that sound alike.
- They cannot reliably tell “this page discusses anaesthesia” from “the clinic includes general
  anaesthesia by default”, an unsupported commercial claim.
- Adding the current lexical rank did not fix this and made ordinary retrieval less useful.
- Existing exact sources (catalogue, offer, doctor, contact, current service document) remain the
  first authority. Retrieval must stay auxiliary and conservative.

## Boundaries

No bot runtime, client pack, Composer, Verifier, session, widget, or route was changed. This result
does not measure answer quality or latency because no scoped prompt was sent to Composer. It only
measures evidence retrieval. Thresholds and weights were frozen at `9273630` before the single
holdout run and were not retuned afterwards.

## Next justified experiment

Do not replace FullContext with embeddings-only retrieval. If retrieval work continues, evaluate a
Chinese Qwen reranker (`qwen3-rerank`) over conservative top-K evidence plus explicit unsupported /
broad-query fallback rules, using a new development set and a second untouched holdout. That is a
new owner-approved milestone. Until then FullContext remains the safe production path and no
retrieval speedup exists.
