from __future__ import annotations

import json
import math
import re
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import get_settings
from app.schemas.chat import ChatRequest
from app.services.document_ingestion import DocumentIngestionService
from app.services.embeddings import EmbeddingService
from app.services.inference import InferenceGateway
from app.services.legal_engine import LegalEngine
from app.services.legal_section_classifier import LegalSectionClassifier
from app.services.retriever import Retriever
from app.services.vector_store import FaissVectorStore


BENCHMARK_PATH = PROJECT_ROOT / "docs" / "research_benchmark.json"
OUTPUT_PATH = PROJECT_ROOT / "docs" / "NyayaSetu_Research_Evaluation_Results.json"


def precision_recall_f1(tp: int, fp: int, fn: int) -> dict[str, float]:
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
    }


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.lower()).strip()


def contains_keywords(answer: str, keywords: list[str]) -> tuple[bool, list[str]]:
    normalized = normalize_text(answer)
    missing = [keyword for keyword in keywords if normalize_text(keyword) not in normalized]
    return len(missing) == 0, missing


def mrr_from_rank(rank: int | None) -> float:
    if not rank or rank <= 0:
        return 0.0
    return round(1.0 / rank, 4)


def macro_metrics(y_true: list[str], y_pred: list[str]) -> dict[str, float]:
    labels = sorted(set(y_true) | set(y_pred))
    f1_scores: list[float] = []
    precision_scores: list[float] = []
    recall_scores: list[float] = []

    for label in labels:
        tp = sum(1 for truth, pred in zip(y_true, y_pred, strict=False) if truth == label and pred == label)
        fp = sum(1 for truth, pred in zip(y_true, y_pred, strict=False) if truth != label and pred == label)
        fn = sum(1 for truth, pred in zip(y_true, y_pred, strict=False) if truth == label and pred != label)
        scores = precision_recall_f1(tp, fp, fn)
        precision_scores.append(scores["precision"])
        recall_scores.append(scores["recall"])
        f1_scores.append(scores["f1"])

    accuracy = sum(1 for truth, pred in zip(y_true, y_pred, strict=False) if truth == pred) / len(y_true)
    return {
        "accuracy": round(accuracy, 4),
        "macro_precision": round(sum(precision_scores) / len(precision_scores), 4),
        "macro_recall": round(sum(recall_scores) / len(recall_scores), 4),
        "macro_f1": round(sum(f1_scores) / len(f1_scores), 4),
    }


def main() -> None:
    benchmark = json.loads(BENCHMARK_PATH.read_text(encoding="utf-8"))
    settings = get_settings()
    embeddings = EmbeddingService(settings)
    vector_store = FaissVectorStore(settings)
    retriever = Retriever(settings, embeddings, vector_store)
    legal_engine = LegalEngine(
        settings,
        retriever,
        InferenceGateway(settings),
        DocumentIngestionService(settings),
    )
    classifier = LegalSectionClassifier(retriever)

    # Warm up embedding, retrieval, and classifier paths so latency metrics are not dominated by first-load cost.
    _ = legal_engine.answer_question(ChatRequest(question="How many sections are there in BNS?", language="en"))
    _ = legal_engine.answer_question(ChatRequest(question="What does Section 303 of BNS cover?", language="en"))
    _ = legal_engine.answer_question(ChatRequest(question="What law applies if someone threatens me online?", language="en"))
    _ = classifier.classify("Someone stole my phone from the market.")

    scope_rows: list[dict] = []
    scope_tp = scope_fp = scope_tn = scope_fn = 0
    scope_latencies: list[float] = []
    for item in benchmark["scope_benchmark"]:
        started = time.perf_counter()
        response = legal_engine.answer_question(ChatRequest(question=item["question"], language="en"))
        latency_ms = (time.perf_counter() - started) * 1000
        predicted = bool(response.in_scope)
        expected = bool(item["expected_in_scope"])
        scope_latencies.append(latency_ms)
        if expected and predicted:
            scope_tp += 1
        elif not expected and predicted:
            scope_fp += 1
        elif not expected and not predicted:
            scope_tn += 1
        else:
            scope_fn += 1
        scope_rows.append(
            {
                "id": item["id"],
                "question": item["question"],
                "expected_in_scope": expected,
                "predicted_in_scope": predicted,
                "latency_ms": round(latency_ms, 2),
                "scope_warning": response.scope_warning,
            }
        )

    scope_scores = precision_recall_f1(scope_tp, scope_fp, scope_fn)
    scope_metrics = {
        "accuracy": round((scope_tp + scope_tn) / len(scope_rows), 4),
        "precision": scope_scores["precision"],
        "recall": scope_scores["recall"],
        "f1": scope_scores["f1"],
        "confusion_matrix": {
            "tp": scope_tp,
            "fp": scope_fp,
            "tn": scope_tn,
            "fn": scope_fn,
        },
        "avg_latency_ms": round(sum(scope_latencies) / len(scope_latencies), 2),
    }

    qa_rows: list[dict] = []
    citation_top1_hits = 0
    citation_top3_hits = 0
    official_source_hits = 0
    hallucination_flags = 0
    unsupported_flags = 0
    structural_correct = 0
    exact_mrr_values: list[float] = []
    qa_latencies: list[float] = []
    error_counter: Counter[str] = Counter()

    for item in benchmark["qa_benchmark"]:
        started = time.perf_counter()
        response = legal_engine.answer_question(ChatRequest(question=item["question"], language="en"))
        latency_ms = (time.perf_counter() - started) * 1000
        qa_latencies.append(latency_ms)

        citations = [source.citation for source in response.sources]
        top_citation = citations[0] if citations else None
        expected_citation = item["expected_source_citation"]
        citation_rank = None
        for index, citation in enumerate(citations, start=1):
            if citation == expected_citation:
                citation_rank = index
                break

        top1_hit = top_citation == expected_citation
        top3_hit = citation_rank is not None and citation_rank <= 3
        if top1_hit:
            citation_top1_hits += 1
        if top3_hit:
            citation_top3_hits += 1
        exact_mrr_values.append(mrr_from_rank(citation_rank))

        official_ok = bool(response.sources) and all(
            (source.source_url or "").startswith(("https://www.indiacode.nic.in", "https://legislative.gov.in"))
            for source in response.sources
        )
        if official_ok:
            official_source_hits += 1

        expected_keywords = item.get("expected_keywords", [])
        if expected_keywords:
            answer_ok, missing_keywords = contains_keywords(response.answer, expected_keywords)
        else:
            answer_ok, missing_keywords = True, []
        unsupported = not top3_hit
        hallucinated = False

        if item["type"] == "structural":
            count_ok = str(item["expected_count"]) in response.answer
            structural_correct += 1 if (count_ok and top1_hit) else 0
            hallucinated = not (count_ok and top1_hit)
            if not count_ok:
                error_counter["wrong_structural_answer"] += 1
        else:
            hallucinated = not (top1_hit and answer_ok)
            if not top1_hit:
                error_counter["wrong_top_citation"] += 1
            if not answer_ok:
                error_counter["missing_expected_keywords"] += 1

        if unsupported:
            unsupported_flags += 1
            error_counter["unsupported_answer"] += 1
        if hallucinated:
            hallucination_flags += 1

        qa_rows.append(
            {
                "id": item["id"],
                "question": item["question"],
                "type": item["type"],
                "expected_source_citation": expected_citation,
                "predicted_source_citations": citations[:3],
                "citation_rank": citation_rank,
                "answer": response.answer,
                "reasoning": response.reasoning,
                "top1_hit": top1_hit,
                "top3_hit": top3_hit,
                "answer_keyword_match": answer_ok,
                "missing_keywords": missing_keywords,
                "official_sources_only": official_ok,
                "hallucination_proxy": hallucinated,
                "unsupported_answer": unsupported,
                "latency_ms": round(latency_ms, 2),
            }
        )

    qa_metrics = {
        "top1_citation_accuracy": round(citation_top1_hits / len(qa_rows), 4),
        "top3_citation_recall": round(citation_top3_hits / len(qa_rows), 4),
        "mrr": round(sum(exact_mrr_values) / len(exact_mrr_values), 4),
        "official_source_rate": round(official_source_hits / len(qa_rows), 4),
        "structural_accuracy": round(
            structural_correct / sum(1 for row in benchmark["qa_benchmark"] if row["type"] == "structural"),
            4,
        ),
        "hallucination_rate_proxy": round(hallucination_flags / len(qa_rows), 4),
        "unsupported_claim_rate_proxy": round(unsupported_flags / len(qa_rows), 4),
        "avg_latency_ms": round(sum(qa_latencies) / len(qa_latencies), 2),
        "error_breakdown": dict(error_counter),
    }

    clf_rows: list[dict] = []
    clf_true: list[str] = []
    clf_pred: list[str] = []
    clf_latencies: list[float] = []
    for item in benchmark["classifier_benchmark"]:
        started = time.perf_counter()
        suggestions, reasoning = classifier.classify(item["incident_description"])
        latency_ms = (time.perf_counter() - started) * 1000
        clf_latencies.append(latency_ms)
        predicted_title = suggestions[0].title if suggestions else "No prediction"
        clf_true.append(item["expected_title"])
        clf_pred.append(predicted_title)
        clf_rows.append(
            {
                "id": item["id"],
                "incident_description": item["incident_description"],
                "expected_title": item["expected_title"],
                "predicted_title": predicted_title,
                "predicted_section": suggestions[0].section if suggestions else None,
                "confidence": round(suggestions[0].confidence, 4) if suggestions else None,
                "reasoning": reasoning,
                "correct": predicted_title == item["expected_title"],
                "latency_ms": round(latency_ms, 2),
            }
        )

    classifier_metrics = macro_metrics(clf_true, clf_pred)
    classifier_metrics["avg_latency_ms"] = round(sum(clf_latencies) / len(clf_latencies), 2)

    overall = {
        "benchmark_size": {
            "scope": len(scope_rows),
            "qa": len(qa_rows),
            "classifier": len(clf_rows),
        },
        "research_summary": {
            "hallucination_rate_proxy": qa_metrics["hallucination_rate_proxy"],
            "unsupported_claim_rate_proxy": qa_metrics["unsupported_claim_rate_proxy"],
            "scope_f1": scope_metrics["f1"],
            "retrieval_top3_recall": qa_metrics["top3_citation_recall"],
            "classifier_macro_f1": classifier_metrics["macro_f1"],
        },
    }

    results = {
        "metadata": {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "embedding_model_name": settings.embedding_model_name,
            "inference_provider": settings.inference_provider,
            "vector_index_path": str(settings.vector_index_path),
            "vector_metadata_path": str(settings.vector_metadata_path),
            "legal_corpus_path": str(settings.legal_corpus_path),
        },
        "scope_metrics": scope_metrics,
        "qa_metrics": qa_metrics,
        "classifier_metrics": classifier_metrics,
        "overall": overall,
        "scope_rows": scope_rows,
        "qa_rows": qa_rows,
        "classifier_rows": clf_rows,
    }
    OUTPUT_PATH.write_text(json.dumps(results, ensure_ascii=True, indent=2), encoding="utf-8")
    print(f"Saved evaluation results to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
