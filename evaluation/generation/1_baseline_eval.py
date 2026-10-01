import importlib
import json
import statistics
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

RUN_DIR = ROOT / "evaluation" / "runs" / "generation" / "e1_generation_baseline"

OUTPUTS_PATH = RUN_DIR / "outputs.jsonl"
CONTEXTS_PATH = ROOT / "cache" / "generation_contexts.jsonl"
GOLD_PATH = ROOT / "cache" / "gold_answer_points_reviewed.jsonl"

TRACE_PATH = RUN_DIR / "eval_trace.jsonl"
SUMMARY_PATH = RUN_DIR / "summary.json"

EVALUATOR_VERSION = "v1"

metrics = importlib.import_module("evaluation.generation.0_generation_metrics")
judge = importlib.import_module("evaluation.generation.0_generation_judge")


def load_jsonl(path):
    with path.open("r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def save_jsonl(path, rows):
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def mean(values):
    values = [v for v in values if v is not None]
    return statistics.mean(values) if values else None


def evaluate_one(output, context_row, gold_row):
    question = output["question"]
    answer = output["answer"]
    contexts = context_row.get("contexts", [])

    start = time.perf_counter()

    # 1. Generated Answer → Atomic Claims
    claim_result = judge.extract_atomic_claims(question, answer)
    claims = claim_result["claims"]

    # 2. Answer Correctness
    if output["answerable"]:
        correctness = judge.judge_answer_correctness(
            question,
            gold_row["atomic_facts"],
            answer,
        )
    else:
        correctness = {
            "score": None,
            "label": "N/A",
            "results": [],
            "model": None,
            "usage": None,
        }

    # 3. Faithfulness + Citation
    evidence = judge.judge_evidence(claims, contexts)

    elapsed = time.perf_counter() - start

    return {
        "evaluator_version": EVALUATOR_VERSION,
        "id": output["id"],
        "question": question,
        "answerable": output["answerable"],
        "generator_model": output["model"],

        "generated_answer": answer,
        "generated_citations": output.get("citations", []),
        "parse_success": output["parse_success"],

        "gold_answer": gold_row.get("gold_answer") if gold_row else None,
        "gold_answer_points": gold_row.get("atomic_facts", []) if gold_row else [],

        "generated_claims": claims,

        "answer_correctness": correctness,

        "faithfulness": {
            "faithfulness": evidence["faithfulness"],
            "unsupported_claim_rate": evidence["unsupported_claim_rate"],
        },

        "citation": {
            "citation_accuracy": evidence["citation_accuracy"],
            "citation_coverage": evidence["citation_coverage"],
        },

        "claim_splitter": {
            "model": claim_result["model"],
            "usage": claim_result["usage"],
        },

        "evidence_judge": {
            "model": evidence["model"],
            "usage": evidence["usage"],
            "results": evidence["results"],
            "logic_error_count": evidence["logic_error_count"],
        },

        "evaluation_time_sec": elapsed,
    }


def main():
    outputs = load_jsonl(OUTPUTS_PATH)
    contexts = {row["id"]: row for row in load_jsonl(CONTEXTS_PATH)}
    gold = {row["id"]: row for row in load_jsonl(GOLD_PATH)}

    print(f"Evaluator: {EVALUATOR_VERSION}")
    print(f"Generator: {outputs[0]['model']}")
    print(f"Questions: {len(outputs)}")
    print()

    trace = []
    start = time.perf_counter()

    for i, output in enumerate(outputs, start=1):
        question_id = output["id"]
        print(f"[{i}/{len(outputs)}] {question_id} evaluating...")

        result = evaluate_one(
            output,
            contexts[question_id],
            gold.get(question_id),
        )

        trace.append(result)

        print(
            f"  correctness={result['answer_correctness']['score']} "
            f"faithfulness={result['faithfulness']['faithfulness']} "
            f"citation={result['citation']['citation_accuracy']} "
            f"time={result['evaluation_time_sec']:.2f}s"
        )

    wall_time = time.perf_counter() - start

    save_jsonl(TRACE_PATH, trace)

    deterministic = metrics.summarize_outputs(outputs)
    deterministic.pop("row_metrics", None)

    answerable = [row for row in trace if row["answerable"]]

    correctness_scores = [
        row["answer_correctness"]["score"]
        for row in answerable
    ]

    faithfulness_scores = [
        row["faithfulness"]["faithfulness"]
        for row in trace
    ]

    unsupported_rates = [
        row["faithfulness"]["unsupported_claim_rate"]
        for row in trace
    ]

    citation_accuracy = [
        row["citation"]["citation_accuracy"]
        for row in trace
    ]

    citation_coverage = [
        row["citation"]["citation_coverage"]
        for row in trace
    ]

    labels = [
        row["answer_correctness"]["label"]
        for row in answerable
    ]

    summary = {
        "experiment": "e1_g0_naive_baseline",
        "evaluator_version": EVALUATOR_VERSION,
        "generator_model": outputs[0]["model"],

        "questions": len(outputs),

        "deterministic": deterministic,

        "semantic": {
            "answer_correctness": {
                "avg_score": mean(correctness_scores),
                "correct": labels.count("CORRECT"),
                "partial": labels.count("PARTIAL"),
                "wrong": labels.count("WRONG"),
            },

            "faithfulness": {
                "avg_score": mean(faithfulness_scores),
                "avg_unsupported_claim_rate": mean(unsupported_rates),
            },

            "citation": {
                "avg_accuracy": mean(citation_accuracy),
                "avg_coverage": mean(citation_coverage),
            },
        },

        "performance": {
            "wall_time_sec": wall_time,
            "avg_time_per_question_sec": wall_time / len(outputs),
            "throughput_questions_per_min": len(outputs) / wall_time * 60,
        },
    }

    with SUMMARY_PATH.open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print()
    print("=" * 60)
    print(f"Answer Correctness: {summary['semantic']['answer_correctness']['avg_score']}")
    print(f"Faithfulness: {summary['semantic']['faithfulness']['avg_score']}")
    print(f"Unsupported Rate: {summary['semantic']['faithfulness']['avg_unsupported_claim_rate']}")
    print(f"Citation Accuracy: {summary['semantic']['citation']['avg_accuracy']}")
    print(f"Citation Coverage: {summary['semantic']['citation']['avg_coverage']}")
    print(f"Wall Time: {wall_time:.2f}s")
    print(f"Throughput: {summary['performance']['throughput_questions_per_min']:.2f} questions/min")


if __name__ == "__main__":
    main()