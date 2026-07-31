"""PERF-9 controlled Qwen text-embedding-v4 retrieval evaluation.

Default execution is a dry-run. Network transport is reachable only with ``--live`` and the exact
committed attempt ID. Development calibration and the blind holdout are separate phases so the
holdout cannot influence score thresholds. This module is research-only and is never imported by
the bot runtime.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Sequence

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import CHAT_BASE_URL
from core.target_lexical_paragraph_index import build_target_lexical_paragraph_index


MODEL = "text-embedding-v4"
DIMENSION = 1024
OUTPUT_TYPE = "dense&sparse"
QUERY_INSTRUCT = (
    "Given a Russian-language patient question about a dental clinic, retrieve the relevant "
    "clinic knowledge-base passage."
)
HYBRID_DENSE_WEIGHT = 0.75
MAX_BATCH_SIZE = 10
TIMEOUT_SECONDS = 60.0
LIVE_AUTHORIZED_ATTEMPT_ID: str | None = "perf9-qwen-dev-2026-08-01-01"

MD_ROOT = ROOT / "clients" / "demo" / "md"
DEV_GOLD_PATH = Path(__file__).with_name("perf8_retrieval_relevance_gold_v2.json")
DEV_QUERY_PATH = Path(__file__).with_name("perf8_retrieval_relevance_query_index.json")
HOLDOUT_GOLD_PATH = Path(__file__).with_name("perf9_qwen_embeddings_holdout_gold_v1.json")
HOLDOUT_QUERY_PATH = Path(__file__).with_name("perf9_qwen_embeddings_holdout_queries_v1.json")
DEV_RESULT_PATH = Path(__file__).with_name("perf9_qwen_dev_calibration_result.json")
CANDIDATE_CONFIG_PATH = Path(__file__).with_name("perf9_qwen_candidate_config_v1.json")
HOLDOUT_RESULT_PATH = Path(__file__).with_name("perf9_qwen_holdout_result.json")
LEDGER_ROOT = ROOT / ".perf9_embedding_ledger" / "attempts"


class Perf9EvaluationError(RuntimeError):
    def __init__(self, code: str, value: object = None) -> None:
        self.code = code
        self.value = value
        super().__init__(f"{code}: {value!r}")


@dataclass(frozen=True, slots=True)
class EmbeddingVector:
    dense: tuple[float, ...]
    sparse: tuple[tuple[int, float], ...]


@dataclass(frozen=True, slots=True)
class CorpusInput:
    item_id: str
    document_ref: str
    text: str


@dataclass(frozen=True, slots=True)
class RankedDocument:
    document_ref: str
    score: float


Transport = Callable[[Sequence[str], str], tuple[tuple[EmbeddingVector, ...], int]]


def _json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _stable_payload_hash(payload: object) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _native_endpoint(compatible_base_url: str | None) -> str:
    value = (compatible_base_url or "").strip().rstrip("/")
    lowered = value.lower()
    if not value or not ("aliyuncs.com" in lowered or "dashscope" in lowered):
        raise Perf9EvaluationError("qwen_base_url_required", value)
    suffix = "/compatible-mode/v1"
    if not lowered.endswith(suffix):
        raise Perf9EvaluationError("qwen_compatible_base_url_invalid", value)
    return value[: -len(suffix)] + "/api/v1/services/embeddings/text-embedding/text-embedding"


def _api_key() -> str:
    # Deliberately no OPENAI_API_KEY fallback: this experiment is Alibaba/Qwen-only.
    value = (os.getenv("DASHSCOPE_API_KEY") or os.getenv("CHAT_API_KEY") or "").strip()
    if not value:
        raise Perf9EvaluationError("dashscope_api_key_missing")
    return value


def _build_corpus_inputs() -> tuple[CorpusInput, ...]:
    index = build_target_lexical_paragraph_index(MD_ROOT)
    rows: list[CorpusInput] = []
    for paragraph in index.paragraphs:
        parts = [paragraph.document_path]
        if paragraph.heading:
            parts.append(paragraph.heading)
        parts.append(paragraph.text)
        rows.append(
            CorpusInput(
                item_id=paragraph.paragraph_id,
                document_ref=paragraph.document_path,
                text="\n".join(parts),
            )
        )
    return tuple(rows)


def _post_qwen_batch(texts: Sequence[str], text_type: str) -> tuple[tuple[EmbeddingVector, ...], int]:
    if text_type not in {"query", "document"}:
        raise Perf9EvaluationError("qwen_text_type_invalid", text_type)
    if not texts or len(texts) > MAX_BATCH_SIZE:
        raise Perf9EvaluationError("qwen_batch_size_invalid", len(texts))
    parameters: dict[str, Any] = {
        "dimension": DIMENSION,
        "output_type": OUTPUT_TYPE,
        "text_type": text_type,
    }
    if text_type == "query":
        parameters["instruct"] = QUERY_INSTRUCT
    payload = {
        "model": MODEL,
        "input": {"texts": list(texts)},
        "parameters": parameters,
    }
    request = urllib.request.Request(
        _native_endpoint(CHAT_BASE_URL),
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {_api_key()}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            body = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise Perf9EvaluationError("qwen_transport_failed", type(exc).__name__) from exc
    if int(body.get("status_code") or 0) != 200:
        raise Perf9EvaluationError("qwen_provider_error", body.get("code") or "unknown")
    raw_vectors = body.get("output", {}).get("embeddings")
    if not isinstance(raw_vectors, list) or len(raw_vectors) != len(texts):
        raise Perf9EvaluationError("qwen_vector_count_mismatch", len(raw_vectors or ()))
    ordered = sorted(raw_vectors, key=lambda row: int(row.get("text_index", -1)))
    vectors: list[EmbeddingVector] = []
    for row in ordered:
        dense = tuple(float(value) for value in row.get("embedding") or ())
        if len(dense) != DIMENSION or not all(math.isfinite(value) for value in dense):
            raise Perf9EvaluationError("qwen_dense_vector_invalid", len(dense))
        sparse = tuple(
            sorted(
                (
                    (int(item["index"]), float(item["value"]))
                    for item in (row.get("sparse_embedding") or ())
                ),
                key=lambda item: item[0],
            )
        )
        if not sparse or not all(math.isfinite(value) for _, value in sparse):
            raise Perf9EvaluationError("qwen_sparse_vector_invalid")
        vectors.append(EmbeddingVector(dense=dense, sparse=sparse))
    return tuple(vectors), int(body.get("usage", {}).get("total_tokens") or 0)


def _embed_all(
    texts: Sequence[str], text_type: str, transport: Transport
) -> tuple[tuple[EmbeddingVector, ...], int, int]:
    vectors: list[EmbeddingVector] = []
    total_tokens = 0
    calls = 0
    for start in range(0, len(texts), MAX_BATCH_SIZE):
        batch = texts[start : start + MAX_BATCH_SIZE]
        batch_vectors, batch_tokens = transport(batch, text_type)
        if len(batch_vectors) != len(batch):
            raise Perf9EvaluationError("transport_vector_count_mismatch")
        vectors.extend(batch_vectors)
        total_tokens += batch_tokens
        calls += 1
    return tuple(vectors), total_tokens, calls


def _sparse_cosine(left: tuple[tuple[int, float], ...], right: tuple[tuple[int, float], ...]) -> float:
    left_map = dict(left)
    right_map = dict(right)
    dot = sum(value * right_map.get(index, 0.0) for index, value in left_map.items())
    left_norm = math.sqrt(sum(value * value for value in left_map.values()))
    right_norm = math.sqrt(sum(value * value for value in right_map.values()))
    return dot / (left_norm * right_norm) if left_norm and right_norm else 0.0


def _rank_documents(
    corpus: Sequence[CorpusInput],
    corpus_vectors: Sequence[EmbeddingVector],
    query_vector: EmbeddingVector,
    *,
    dense_weight: float,
) -> tuple[RankedDocument, ...]:
    matrix = np.asarray([vector.dense for vector in corpus_vectors], dtype=np.float32)
    query = np.asarray(query_vector.dense, dtype=np.float32)
    matrix_norms = np.linalg.norm(matrix, axis=1)
    query_norm = float(np.linalg.norm(query))
    dense_scores = (matrix @ query) / np.maximum(matrix_norms * query_norm, 1e-12)
    best: dict[str, float] = {}
    for index, row in enumerate(corpus):
        sparse_score = _sparse_cosine(corpus_vectors[index].sparse, query_vector.sparse)
        score = dense_weight * float(dense_scores[index]) + (1.0 - dense_weight) * sparse_score
        if row.document_ref not in best or score > best[row.document_ref]:
            best[row.document_ref] = score
    return tuple(
        RankedDocument(document_ref=document_ref, score=score)
        for document_ref, score in sorted(best.items(), key=lambda item: (-item[1], item[0]))
    )


def _decision(ranking: Sequence[RankedDocument], min_score: float, min_margin: float) -> str | None:
    if not ranking:
        return None
    second = ranking[1].score if len(ranking) > 1 else 0.0
    if ranking[0].score < min_score or ranking[0].score - second < min_margin:
        return None
    return ranking[0].document_ref


def _verdict(decision: str | None, gold: dict[str, Any]) -> str:
    if decision is None:
        return "match_correct" if gold["fallback_required"] else "safe_over_fallback"
    if not gold["fallback_required"] and decision in gold["allowed_retrieval_md_refs"]:
        return "match_correct"
    return "critical_false_narrow_irrelevant_retrieval"


def _metrics(
    rankings: dict[str, tuple[RankedDocument, ...]],
    gold_rows: Sequence[dict[str, Any]],
    min_score: float,
    min_margin: float,
) -> dict[str, Any]:
    counts = {"critical_false_narrow_count": 0, "match_correct_count": 0, "safe_over_fallback_count": 0, "fallback_count": 0}
    recall1 = 0
    recall3 = 0
    answerable = 0
    for gold in gold_rows:
        ranking = rankings[gold["scenario_id"]]
        decision = _decision(ranking, min_score, min_margin)
        verdict = _verdict(decision, gold)
        if verdict.startswith("critical"):
            counts["critical_false_narrow_count"] += 1
        else:
            counts[f"{verdict}_count"] += 1
        if decision is None:
            counts["fallback_count"] += 1
        if not gold["fallback_required"]:
            answerable += 1
            allowed = set(gold["allowed_retrieval_md_refs"])
            recall1 += int(bool(ranking) and ranking[0].document_ref in allowed)
            recall3 += int(any(row.document_ref in allowed for row in ranking[:3]))
    total = len(gold_rows)
    counts.update(
        fallback_rate=counts["fallback_count"] / total,
        recall_at_1=recall1 / answerable if answerable else 0.0,
        recall_at_3=recall3 / answerable if answerable else 0.0,
        min_score=min_score,
        min_margin=min_margin,
    )
    return counts


def _calibrate(
    rankings: dict[str, tuple[RankedDocument, ...]], gold_rows: Sequence[dict[str, Any]]
) -> dict[str, Any]:
    top_scores = {0.0}
    margins = {0.0}
    for ranking in rankings.values():
        if ranking:
            top_scores.add(round(ranking[0].score, 6))
            second = ranking[1].score if len(ranking) > 1 else 0.0
            margins.add(round(ranking[0].score - second, 6))
    # Explicit all-fallback candidates: safety must remain representable even when no accepted
    # ranking can separate relevant from unsafe development rows.
    top_scores.add(max(top_scores) + 0.000001)
    margins.add(max(margins) + 0.000001)
    candidates: list[dict[str, Any]] = []
    for min_score in sorted(top_scores):
        for min_margin in sorted(margins):
            candidates.append(_metrics(rankings, gold_rows, min_score, min_margin))
    # Safety first, then preserve useful narrow retrieval, then choose the least restrictive tie.
    return min(
        candidates,
        key=lambda row: (
            row["critical_false_narrow_count"],
            row["safe_over_fallback_count"],
            row["fallback_count"],
            row["min_score"],
            row["min_margin"],
        ),
    )


def _rank_all(
    corpus: Sequence[CorpusInput],
    corpus_vectors: Sequence[EmbeddingVector],
    query_ids: Sequence[str],
    query_vectors: Sequence[EmbeddingVector],
    dense_weight: float,
) -> dict[str, tuple[RankedDocument, ...]]:
    return {
        scenario_id: _rank_documents(
            corpus, corpus_vectors, query_vector, dense_weight=dense_weight
        )
        for scenario_id, query_vector in zip(query_ids, query_vectors, strict=True)
    }


def _safe_rankings(rankings: dict[str, tuple[RankedDocument, ...]]) -> dict[str, list[dict[str, Any]]]:
    return {
        scenario_id: [
            {"document_ref": row.document_ref, "score": round(row.score, 6)}
            for row in ranking[:3]
        ]
        for scenario_id, ranking in rankings.items()
    }


def _create_attempt_marker(attempt_id: str, phase: str, manifest_hash: str) -> Path:
    LEDGER_ROOT.mkdir(parents=True, exist_ok=True)
    path = LEDGER_ROOT / f"{attempt_id}.json"
    payload = {
        "schema_version": 1,
        "attempt_id": attempt_id,
        "phase": phase,
        "model": MODEL,
        "dimension": DIMENSION,
        "output_type": OUTPUT_TYPE,
        "input_manifest_hash": manifest_hash,
        "status": "started_consumed",
    }
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    except FileExistsError as exc:
        raise Perf9EvaluationError("attempt_id_already_consumed", attempt_id) from exc
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return path


def _finish_marker(path: Path, *, calls: int, tokens: int, status: str) -> None:
    payload = _json(path)
    payload.update(status=status, provider_calls=calls, provider_input_tokens=tokens)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _run_phase(phase: str, transport: Transport) -> dict[str, Any]:
    if phase == "dev":
        gold_path, query_path = DEV_GOLD_PATH, DEV_QUERY_PATH
    elif phase == "holdout":
        gold_path, query_path = HOLDOUT_GOLD_PATH, HOLDOUT_QUERY_PATH
        if not CANDIDATE_CONFIG_PATH.exists():
            raise Perf9EvaluationError("candidate_config_missing")
    else:
        raise Perf9EvaluationError("phase_invalid", phase)
    gold = _json(gold_path)
    queries = _json(query_path)
    query_by_id = {row["scenario_id"]: row for row in queries["scenarios"]}
    gold_rows = gold["scenarios"]
    query_ids = [row["scenario_id"] for row in gold_rows]
    query_texts = [query_by_id[scenario_id]["synthetic_query"] for scenario_id in query_ids]
    corpus = _build_corpus_inputs()

    started = time.perf_counter()
    corpus_vectors, corpus_tokens, corpus_calls = _embed_all(
        [row.text for row in corpus], "document", transport
    )
    query_vectors, query_tokens, query_calls = _embed_all(query_texts, "query", transport)
    dense_rankings = _rank_all(corpus, corpus_vectors, query_ids, query_vectors, 1.0)
    hybrid_rankings = _rank_all(
        corpus, corpus_vectors, query_ids, query_vectors, HYBRID_DENSE_WEIGHT
    )

    if phase == "dev":
        dense_config = _calibrate(dense_rankings, gold_rows)
        hybrid_config = _calibrate(hybrid_rankings, gold_rows)
    else:
        config = _json(CANDIDATE_CONFIG_PATH)
        dense_config = config["candidates"]["dense"]
        hybrid_config = config["candidates"]["qwen_native_hybrid"]

    result = {
        "schema_version": 1,
        "phase": phase,
        "model": MODEL,
        "dimension": DIMENSION,
        "output_type": OUTPUT_TYPE,
        "query_instruct_sha256": hashlib.sha256(QUERY_INSTRUCT.encode("utf-8")).hexdigest(),
        "hybrid_dense_weight": HYBRID_DENSE_WEIGHT,
        "gold_sha256": _sha256(gold_path),
        "query_index_sha256": _sha256(query_path),
        "corpus_input_manifest_sha256": _stable_payload_hash(
            [(row.item_id, row.document_ref, hashlib.sha256(row.text.encode("utf-8")).hexdigest()) for row in corpus]
        ),
        "scenario_count": len(gold_rows),
        "corpus_paragraph_count": len(corpus),
        "provider_calls": corpus_calls + query_calls,
        "provider_input_tokens": corpus_tokens + query_tokens,
        "duration_ms": round((time.perf_counter() - started) * 1000, 3),
        "candidates": {
            "dense": _metrics(
                dense_rankings,
                gold_rows,
                float(dense_config["min_score"]),
                float(dense_config["min_margin"]),
            ),
            "qwen_native_hybrid": _metrics(
                hybrid_rankings,
                gold_rows,
                float(hybrid_config["min_score"]),
                float(hybrid_config["min_margin"]),
            ),
        },
        "top3": {
            "dense": _safe_rankings(dense_rankings),
            "qwen_native_hybrid": _safe_rankings(hybrid_rankings),
        },
        "contains_query_or_answer_text": False,
    }
    if phase == "holdout":
        result["candidate_config_sha256"] = _sha256(CANDIDATE_CONFIG_PATH)
    if phase == "dev":
        result["candidate_config"] = {
            "schema_version": 1,
            "source_phase": "dev",
            "source_gold_sha256": _sha256(gold_path),
            "model": MODEL,
            "dimension": DIMENSION,
            "output_type": OUTPUT_TYPE,
            "hybrid_dense_weight": HYBRID_DENSE_WEIGHT,
            "candidates": {
                "dense": {key: dense_config[key] for key in ("min_score", "min_margin")},
                "qwen_native_hybrid": {
                    key: hybrid_config[key] for key in ("min_score", "min_margin")
                },
            },
        }
    return result


def _dry_run(phase: str) -> dict[str, Any]:
    if phase == "dev":
        gold_path, query_path = DEV_GOLD_PATH, DEV_QUERY_PATH
    else:
        gold_path, query_path = HOLDOUT_GOLD_PATH, HOLDOUT_QUERY_PATH
    corpus = _build_corpus_inputs()
    queries = _json(query_path)["scenarios"]
    return {
        "status": "dry_run",
        "provider_calls": 0,
        "phase": phase,
        "model": MODEL,
        "dimension": DIMENSION,
        "output_type": OUTPUT_TYPE,
        "corpus_paragraph_count": len(corpus),
        "query_count": len(queries),
        "expected_provider_calls": math.ceil(len(corpus) / MAX_BATCH_SIZE)
        + math.ceil(len(queries) / MAX_BATCH_SIZE),
        "gold_sha256": _sha256(gold_path),
        "query_index_sha256": _sha256(query_path),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("dev", "holdout"), required=True)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--attempt-id")
    args = parser.parse_args(argv)
    if not args.live:
        print(json.dumps(_dry_run(args.phase), indent=2, sort_keys=True))
        return 0
    if not args.attempt_id:
        raise Perf9EvaluationError("attempt_id_required")
    if args.attempt_id != LIVE_AUTHORIZED_ATTEMPT_ID:
        raise Perf9EvaluationError("live_attempt_not_authorized", args.attempt_id)

    dry = _dry_run(args.phase)
    manifest_hash = _stable_payload_hash(dry)
    marker = _create_attempt_marker(args.attempt_id, args.phase, manifest_hash)
    provider_calls_attempted = 0
    provider_input_tokens = 0

    def tracked_transport(
        texts: Sequence[str], text_type: str
    ) -> tuple[tuple[EmbeddingVector, ...], int]:
        nonlocal provider_calls_attempted, provider_input_tokens
        provider_calls_attempted += 1
        vectors, tokens = _post_qwen_batch(texts, text_type)
        provider_input_tokens += tokens
        return vectors, tokens

    try:
        result = _run_phase(args.phase, tracked_transport)
        destination = DEV_RESULT_PATH if args.phase == "dev" else HOLDOUT_RESULT_PATH
        destination.write_text(
            json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        if args.phase == "dev":
            CANDIDATE_CONFIG_PATH.write_text(
                json.dumps(result["candidate_config"], indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        _finish_marker(
            marker,
            calls=int(result["provider_calls"]),
            tokens=int(result["provider_input_tokens"]),
            status="completed",
        )
    except Exception:
        _finish_marker(
            marker,
            calls=provider_calls_attempted,
            tokens=provider_input_tokens,
            status="failed_consumed",
        )
        raise
    print(json.dumps({"status": "completed", "phase": args.phase, "result": str(destination.relative_to(ROOT))}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
