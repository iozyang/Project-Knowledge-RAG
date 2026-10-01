import asyncio
import importlib
import json
import statistics
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

RUN_DIR = (
    ROOT
    / "evaluation"
    / "runs"
    / "generation"
    / "e3_prompt_optimized"
)

OUTPUTS_PATH = RUN_DIR / "outputs.jsonl"
CONTEXTS_PATH = ROOT / "cache" / "generation_contexts.jsonl"
GOLD_PATH = ROOT / "cache" / "gold_answer_points_reviewed.jsonl"

TRACE_PATH = RUN_DIR / "eval_trace.jsonl"
SUMMARY_PATH = RUN_DIR / "summary.json"

EVALUATOR_VERSION = "v2"
MAX_CONCURRENCY = 3

judge = importlib.import_module(
    "evaluation.generation.0_generation_judge_async"
)

metrics = importlib.import_module(
    "evaluation.generation.0_generation_metrics"
)


def load_jsonl(path):
    with path.open("r", encoding="utf-8") as f:
        return [
            json.loads(line)
            for line in f
            if line.strip()
        ]


def save_jsonl(path, rows):
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(
                json.dumps(
                    row,
                    ensure_ascii=False,
                )
                + "\n"
            )


def mean(values):
    values = [
        value
        for value in values
        if value is not None
    ]

    return (
        statistics.mean(values)
        if values
        else None
    )


def add_usage(total, usage):
    if not usage:
        return

    total["input_tokens"] += (
        usage.get("input_tokens", 0)
        or 0
    )

    total["output_tokens"] += (
        usage.get("output_tokens", 0)
        or 0
    )

    total["total_tokens"] += (
        usage.get("total_tokens", 0)
        or 0
    )


def count_evaluation_tokens(trace):
    total = {
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
    }

    for row in trace:
        add_usage(
            total,
            row.get(
                "claim_splitter",
                {},
            ).get("usage"),
        )

        add_usage(
            total,
            row.get(
                "answer_correctness",
                {},
            ).get("usage"),
        )

        add_usage(
            total,
            row.get(
                "evidence_judge",
                {},
            ).get("usage"),
        )

    return total


async def evaluate_one(
    output,
    context_row,
    gold_row,
    semaphore,
):
    async with semaphore:
        question = output["question"]
        answer = output["answer"]

        contexts = context_row.get(
            "contexts",
            [],
        )

        start = time.perf_counter()

        # ====================================================
        # 1. Claim Splitter
        # ====================================================

        claim_result = (
            await judge.extract_atomic_claims(
                question,
                answer,
            )
        )

        claims = claim_result["claims"]

        # ====================================================
        # 2. Answer Correctness
        # ====================================================

        if output["answerable"]:
            correctness = (
                await judge.judge_answer_correctness(
                    question,
                    gold_row["atomic_facts"],
                    answer,
                )
            )
        else:
            correctness = {
                "score": None,
                "label": "N/A",
                "results": [],
                "model": None,
                "usage": None,
            }

        # ====================================================
        # 3. Evidence Judge
        # ====================================================

        evidence = (
            await judge.judge_evidence(
                claims,
                contexts,
            )
        )

        elapsed = (
            time.perf_counter()
            - start
        )

        # ====================================================
        # Trace
        # ====================================================

        return {
            "evaluator_version": (
                EVALUATOR_VERSION
            ),

            "id": output["id"],
            "question": question,
            "answerable": output["answerable"],

            "generator_model": (
                output["model"]
            ),

            "generated_answer": answer,

            "generated_citations": (
                output.get(
                    "citations",
                    [],
                )
            ),

            "parse_success": (
                output["parse_success"]
            ),

            "gold_answer": (
                gold_row.get(
                    "gold_answer"
                )
                if gold_row
                else None
            ),

            "gold_answer_points": (
                gold_row.get(
                    "atomic_facts",
                    [],
                )
                if gold_row
                else []
            ),

            "generated_claims": claims,

            "answer_correctness": (
                correctness
            ),

            "faithfulness": {
                "faithfulness": (
                    evidence[
                        "faithfulness"
                    ]
                ),

                "unsupported_claim_rate": (
                    evidence[
                        "unsupported_claim_rate"
                    ]
                ),
            },

            "citation": {
                "citation_accuracy": (
                    evidence[
                        "citation_accuracy"
                    ]
                ),

                "citation_coverage": (
                    evidence[
                        "citation_coverage"
                    ]
                ),
            },

            "claim_splitter": {
                "model": (
                    claim_result[
                        "model"
                    ]
                ),

                "usage": (
                    claim_result[
                        "usage"
                    ]
                ),
            },

            "evidence_judge": {
                "model": (
                    evidence[
                        "model"
                    ]
                ),

                "usage": (
                    evidence[
                        "usage"
                    ]
                ),

                "results": (
                    evidence[
                        "results"
                    ]
                ),

                "logic_error_count": (
                    evidence[
                        "logic_error_count"
                    ]
                ),
            },

            "evaluation_time_sec": (
                elapsed
            ),
        }


async def main():
    RUN_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    outputs = load_jsonl(
        OUTPUTS_PATH
    )

    contexts = {
        row["id"]: row
        for row in load_jsonl(
            CONTEXTS_PATH
        )
    }

    gold = {
        row["id"]: row
        for row in load_jsonl(
            GOLD_PATH
        )
    }

    semaphore = asyncio.Semaphore(
        MAX_CONCURRENCY
    )

    print(
        "Experiment: "
        "e3_prompt_optimized"
    )

    print(
        f"Evaluator: "
        f"{EVALUATOR_VERSION}"
    )

    print(
        f"Generator: "
        f"{outputs[0]['model']}"
    )

    print(
        f"Questions: "
        f"{len(outputs)}"
    )

    print(
        f"Concurrency: "
        f"{MAX_CONCURRENCY}"
    )

    print()

    start = time.perf_counter()

    tasks = [
        asyncio.create_task(
            evaluate_one(
                output,
                contexts[
                    output["id"]
                ],
                gold.get(
                    output["id"]
                ),
                semaphore,
            )
        )
        for output in outputs
    ]

    trace = []

    for i, task in enumerate(
        asyncio.as_completed(tasks),
        start=1,
    ):
        result = await task
        trace.append(result)

        print(
            f"[{i}/{len(outputs)}] "
            f"{result['id']} OK "
            f"correctness="
            f"{result['answer_correctness']['score']} "
            f"faithfulness="
            f"{result['faithfulness']['faithfulness']} "
            f"citation="
            f"{result['citation']['citation_accuracy']}"
        )

    wall_time = (
        time.perf_counter()
        - start
    )

    trace.sort(
        key=lambda row: row["id"]
    )

    save_jsonl(
        TRACE_PATH,
        trace,
    )

    # ========================================================
    # Deterministic Metrics
    # ========================================================

    deterministic = (
        metrics.summarize_outputs(
            outputs
        )
    )

    deterministic.pop(
        "row_metrics",
        None,
    )

    # ========================================================
    # Semantic Metrics
    # ========================================================

    answerable = [
        row
        for row in trace
        if row["answerable"]
    ]

    correctness_scores = [
        row[
            "answer_correctness"
        ]["score"]
        for row in answerable
    ]

    labels = [
        row[
            "answer_correctness"
        ]["label"]
        for row in answerable
    ]

    faithfulness_scores = [
        row[
            "faithfulness"
        ]["faithfulness"]
        for row in trace
    ]

    unsupported_rates = [
        row[
            "faithfulness"
        ][
            "unsupported_claim_rate"
        ]
        for row in trace
    ]

    citation_accuracy = [
        row[
            "citation"
        ][
            "citation_accuracy"
        ]
        for row in trace
    ]

    citation_coverage = [
        row[
            "citation"
        ][
            "citation_coverage"
        ]
        for row in trace
    ]

    evaluation_tokens = (
        count_evaluation_tokens(
            trace
        )
    )

    # ========================================================
    # Summary
    # ========================================================

    summary = {
        "experiment": (
            "e3_prompt_optimized"
        ),

        "evaluator_version": (
            EVALUATOR_VERSION
        ),

        "generator_model": (
            outputs[0]["model"]
        ),

        "questions": (
            len(outputs)
        ),

        "deterministic": (
            deterministic
        ),

        "semantic": {
            "answer_correctness": {
                "avg_score": mean(
                    correctness_scores
                ),

                "correct": (
                    labels.count(
                        "CORRECT"
                    )
                ),

                "partial": (
                    labels.count(
                        "PARTIAL"
                    )
                ),

                "wrong": (
                    labels.count(
                        "WRONG"
                    )
                ),
            },

            "faithfulness": {
                "avg_score": mean(
                    faithfulness_scores
                ),

                "avg_unsupported_claim_rate": mean(
                    unsupported_rates
                ),
            },

            "citation": {
                "avg_accuracy": mean(
                    citation_accuracy
                ),

                "avg_coverage": mean(
                    citation_coverage
                ),
            },
        },

        "performance": {
            "wall_time_sec": (
                wall_time
            ),

            "avg_time_per_question_sec": (
                wall_time
                / len(outputs)
            ),

            "throughput_questions_per_min": (
                len(outputs)
                / wall_time
                * 60
            ),
        },

        "evaluation_tokens": (
            evaluation_tokens
        ),
    }

    with SUMMARY_PATH.open(
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            summary,
            f,
            ensure_ascii=False,
            indent=2,
        )

    # ========================================================
    # Console Summary
    # ========================================================

    print()
    print("=" * 60)

    print(
        f"Answer Correctness: "
        f"{summary['semantic']['answer_correctness']['avg_score']}"
    )

    print(
        f"Faithfulness: "
        f"{summary['semantic']['faithfulness']['avg_score']}"
    )

    print(
        f"Unsupported Rate: "
        f"{summary['semantic']['faithfulness']['avg_unsupported_claim_rate']}"
    )

    print(
        f"Citation Accuracy: "
        f"{summary['semantic']['citation']['avg_accuracy']}"
    )

    print(
        f"Citation Coverage: "
        f"{summary['semantic']['citation']['avg_coverage']}"
    )

    print()

    print(
        f"Wall Time: "
        f"{wall_time:.2f}s"
    )

    print(
        f"Throughput: "
        f"{summary['performance']['throughput_questions_per_min']:.2f} "
        f"questions/min"
    )

    print()

    print("Evaluation Tokens")

    print(
        f"  Input: "
        f"{evaluation_tokens['input_tokens']}"
    )

    print(
        f"  Output: "
        f"{evaluation_tokens['output_tokens']}"
    )

    print(
        f"  Total: "
        f"{evaluation_tokens['total_tokens']}"
    )

    print()

    print(
        f"Trace: "
        f"{TRACE_PATH}"
    )

    print(
        f"Summary: "
        f"{SUMMARY_PATH}"
    )

    await judge.client.close()


if __name__ == "__main__":
    asyncio.run(main())