# FINAL_RETRIEVAL_RELEVANCE_DECISION / PERF-8 Phase 1

## Verdict

**`EMBEDDINGS_EVALUATION_JUSTIFIED`.** No retrieval candidate evaluated in this milestone is
authorized for runtime use. Scoped Composer remains blocked.

This is an offline, local research result. It changes neither the bot's answers nor its latency.

## Scope and inherited-WIP handling

PERF-8 was resumed from five untracked files left by an interrupted Claude session. The inherited
gold file had an earlier filesystem timestamp than the runner/result, but untracked-file chronology
is not cryptographic evidence. The files were therefore treated as untrusted WIP, independently
reviewed, corrected where their semantic contract was unsafe, hashed before the final run, and
reported as an **exploratory development-set comparison**, not a holdout PASS.

The final runner records and verifies both the gold SHA256 and query-index SHA256 before and after
the comparison. Both remained unchanged during the final run.

## Gold contract

The versioned gold contains 49 retrieval-dependent scenarios inherited from the 118-scenario
PERF-7C matrix. Query wording is kept separately in a retrieval-executor query index. Each gold row
contains:

- `required_md_refs`;
- `allowed_retrieval_md_refs`;
- `forbidden_retrieval_md_refs`;
- `fallback_required`;
- an authority-based rationale.

Four inherited labels were corrected during independent review:

- `s011` and `s013`: a broad prosthetics catalogue answer spans five documents, while every tested
  retriever emits at most one; accepting one service page would falsely narrow the answer, so full
  fallback is required;
- `s015`: only the general teeth-treatment overview is sufficient; a caries or pulpitis page alone
  would be too narrow;
- `s081`: only the implantation-contraindications document directly establishes the requested
  relationship between gum treatment and implantation.

The five external-treatment-plan questions require fallback. The consultation document says that
the clinic's doctor composes a treatment plan; it does not claim that the clinic audits, verifies or
provides a second opinion on a plan produced elsewhere.

## Candidates

| Candidate | Mechanism | Status |
|---|---|---|
| A | Current PERF-7 token-overlap decision, mirrored at the Builder's ten-hit acceptance shape | Unsafe baseline |
| B | IDF-weighted query coverage, topic bonus and strict coverage/margin gate | Exploratory development-set prototype |
| C | In-memory SQLite FTS5/BM25 with strict relevance/margin gate | Exploratory development-set prototype |
| D | Local embeddings | `NOT_EVALUATED` — no repository-configured offline model artifact |

Candidate B and C thresholds were selected after aggregate inspection of this same development
matrix. Their results therefore cannot demonstrate generalization and cannot authorize runtime
wiring. Candidate B also receives synthetic `allowed_topics` copied from the PERF-7C matrix, not
topics produced by a measured Planner run; its result may therefore be optimistic. These
limitations are intentionally part of the machine-readable result.

## Final offline metrics

| Metric | A | B | C |
|---|---:|---:|---:|
| Scenarios | 49 | 49 | 49 |
| Critical false narrow | **11** | 0 | 0 |
| Correct outcomes | 19 | 23 | 24 |
| Safe over-fallback | 19 | 26 | 25 |
| Fallback rate | 53.1% | **87.8%** | **85.7%** |
| Relevant recall@1 | 37.5% | 18.8% | 21.9% |
| Relevant recall@3 | 56.3% | 84.4% | 65.6% |
| Raw unrelated top candidate | 32 | 29 | 33 |
| Average accepted-document token estimate | 546 | 457 | 503 |

Timing is diagnostic only. The runner now measures paragraph-index, weighted-table and FTS5 build
time explicitly and labels each as one non-binding local observation. Per-query timings exclude
those one-time build costs.

## Known PERF-7C defects

Candidate A reproduces all ten previously identified unrelated confident selections:
`s051`, `s053`–`s056`, `s083`–`s084`, `s099`–`s101`. Candidate B and C conservatively fall back on
all ten in the final run. Candidate A has one additional critical false narrowing elsewhere in the
49-scenario retrieval subset.

## Decision

The current lexical baseline is unsafe. B and C can suppress observed critical errors only with an
85–88% fallback rate and gates fitted on this same development set. That is not evidence of a useful
or safe Scoped Composer retriever.

The next justified experiment is an **offline embeddings/hybrid comparison against a newly
committed holdout gold that is frozen before retrieval execution**. It requires a separate owner GO
for model/dependency selection and, if a provider is used, a separate LIVE/network authorization.
It must not reuse this development matrix as its only success oracle.

## Boundaries

- NO runtime wiring.
- NO Scoped Composer switch.
- NO Builder/index/contract product change.
- NO client-pack change.
- NO Composer answer generation.
- NO LLM/provider/network call.
- NO speedup claim.

**STOP before embeddings evaluation and before any production retrieval implementation.**
