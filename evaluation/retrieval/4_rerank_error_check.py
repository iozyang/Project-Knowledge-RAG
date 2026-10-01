import importlib
import json
import re
from pathlib import Path


# ============================================================
# 导入 Cache
# ============================================================

cache_module = importlib.import_module(
    "src.retrieval_cache"
)

load_or_create_chunks = (
    cache_module.load_or_create_chunks
)

load_answerable_benchmark = (
    cache_module.load_answerable_benchmark
)


# ============================================================
# 路径
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

RERANK_TRACE_PATH = (
    PROJECT_ROOT
    / "evaluation"
    / "runs"
    / "retrieval"
    / "e3_rerank_ab"
    / "trace.jsonl"
)

RUN_DIR = (
    PROJECT_ROOT
    / "evaluation"
    / "runs"
    / "retrieval"
    / "e3_rerank_error_analysis"
)


# ============================================================
# 文本归一化
# ============================================================

def normalize_text(text):

    return re.sub(
        r"\s+",
        " ",
        text,
    ).strip()


# ============================================================
# Gold Evidence Match
# ============================================================

def find_matched_evidence(
    chunk,
    gold_evidence,
):

    matched_ids = []

    chunk_text = normalize_text(
        chunk["content"]
    )

    chunk_file = Path(
        chunk["source"]
    ).name


    for evidence in gold_evidence:

        if chunk_file != evidence["document"]:
            continue

        evidence_text = normalize_text(
            evidence["evidence"]
        )

        if evidence_text in chunk_text:

            matched_ids.append(
                evidence["evidence_id"]
            )


    return matched_ids


# ============================================================
# 加载 Reranker Trace
# ============================================================

def load_rerank_trace():

    traces = []

    with RERANK_TRACE_PATH.open(
        "r",
        encoding="utf-8",
    ) as f:

        for line in f:

            if line.strip():

                traces.append(
                    json.loads(line)
                )

    return traces


# ============================================================
# Main
# ============================================================

def main():

    print()
    print("=" * 70)
    print("RERANK ERROR ANALYSIS")
    print("=" * 70)


    # --------------------------------------------------------
    # 1. Corpus Chunks
    # --------------------------------------------------------

    chunks = load_or_create_chunks()

    chunk_map = {
        chunk["chunk_id"]: chunk
        for chunk in chunks
    }


    # --------------------------------------------------------
    # 2. Benchmark
    # --------------------------------------------------------

    questions = load_answerable_benchmark()

    question_map = {
        question["id"]: question
        for question in questions
    }


    # --------------------------------------------------------
    # 3. Reranker Trace
    # --------------------------------------------------------

    traces = load_rerank_trace()

    print(
        f"Questions: {len(traces)}"
    )


    # --------------------------------------------------------
    # 4. Error Analysis
    # --------------------------------------------------------

    results = []

    evidence_total = 0
    candidate_missed_total = 0
    reranker_missed_total = 0
    final_found_total = 0


    category_count = {
        "complete": 0,
        "candidate_miss": 0,
        "reranker_miss": 0,
        "mixed": 0,
    }


    for trace in traces:

        question_id = trace["id"]

        question = question_map[
            question_id
        ]

        gold_evidence = question[
            "gold_evidence"
        ]

        gold_ids = {
            evidence["evidence_id"]
            for evidence in gold_evidence
        }


        # ====================================================
        # RRF Top20 Candidate
        # ====================================================

        candidate_chunk_ids = (
            trace[
                "rrf_top20_rerank_top5"
            ][
                "candidate_chunk_ids"
            ]
        )


        candidate_found_ids = set()


        for chunk_id in candidate_chunk_ids:

            chunk = chunk_map[
                chunk_id
            ]

            candidate_found_ids.update(
                find_matched_evidence(
                    chunk,
                    gold_evidence,
                )
            )


        # ====================================================
        # Reranker Top5
        # ====================================================

        reranked_top5 = (
            trace[
                "rrf_top20_rerank_top5"
            ][
                "reranked_top5"
            ]
        )


        final_found_ids = set()


        for item in reranked_top5:

            final_found_ids.update(
                item[
                    "matched_evidence_ids"
                ]
            )


        # ====================================================
        # Miss 分类
        # ====================================================

        candidate_missed_ids = (
            gold_ids
            - candidate_found_ids
        )


        # 这些 Evidence 明明在 Top20，
        # 但最终没有进入 Top5
        reranker_missed_ids = (
            candidate_found_ids
            - final_found_ids
        )


        # ====================================================
        # Question Category
        # ====================================================

        if (
            not candidate_missed_ids
            and not reranker_missed_ids
        ):

            category = "complete"


        elif (
            candidate_missed_ids
            and not reranker_missed_ids
        ):

            category = "candidate_miss"


        elif (
            not candidate_missed_ids
            and reranker_missed_ids
        ):

            category = "reranker_miss"


        else:

            category = "mixed"


        category_count[
            category
        ] += 1


        # ====================================================
        # Evidence-level Count
        # ====================================================

        evidence_total += len(
            gold_ids
        )

        candidate_missed_total += len(
            candidate_missed_ids
        )

        reranker_missed_total += len(
            reranker_missed_ids
        )

        final_found_total += len(
            final_found_ids
        )


        # ====================================================
        # 保存单题结果
        # ====================================================

        results.append(
            {
                "id":
                    question_id,

                "question":
                    question["question"],

                "question_type":
                    question["question_type"],

                "hop_type":
                    question["hop_type"],

                "category":
                    category,

                "gold_evidence_ids":
                    sorted(gold_ids),

                "candidate_found_ids":
                    sorted(
                        candidate_found_ids
                    ),

                "final_found_ids":
                    sorted(
                        final_found_ids
                    ),

                "candidate_missed_ids":
                    sorted(
                        candidate_missed_ids
                    ),

                "reranker_missed_ids":
                    sorted(
                        reranker_missed_ids
                    ),
            }
        )


    # --------------------------------------------------------
    # 5. Summary
    # --------------------------------------------------------

    summary = {

        "experiment":
            "E3-Reranker-Error-Analysis",

        "question_count":
            len(results),

        "gold_evidence_count":
            evidence_total,

        "question_categories":
            category_count,

        "evidence_analysis": {

            "final_found":
                final_found_total,

            "candidate_missed":
                candidate_missed_total,

            "reranker_missed":
                reranker_missed_total,

            "final_found_rate":
                (
                    final_found_total
                    / evidence_total
                ),

            "candidate_miss_rate":
                (
                    candidate_missed_total
                    / evidence_total
                ),

            "reranker_miss_rate":
                (
                    reranker_missed_total
                    / evidence_total
                ),
        },
    }


    # --------------------------------------------------------
    # 6. 保存
    # --------------------------------------------------------

    RUN_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )


    with (
        RUN_DIR / "trace.jsonl"
    ).open(
        "w",
        encoding="utf-8",
    ) as f:

        for result in results:

            f.write(
                json.dumps(
                    result,
                    ensure_ascii=False,
                )
                + "\n"
            )


    with (
        RUN_DIR / "summary.json"
    ).open(
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            summary,
            f,
            ensure_ascii=False,
            indent=2,
        )


    # --------------------------------------------------------
    # 7. Console
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("QUESTION-LEVEL")
    print("=" * 70)

    for category, count in category_count.items():

        print(
            f"{category}: {count}"
        )


    print()
    print("=" * 70)
    print("EVIDENCE-LEVEL")
    print("=" * 70)

    print(
        f"Gold Evidence: "
        f"{evidence_total}"
    )

    print(
        f"Final Found: "
        f"{final_found_total}"
    )

    print(
        f"Candidate Miss: "
        f"{candidate_missed_total}"
    )

    print(
        f"Reranker Miss: "
        f"{reranker_missed_total}"
    )


    print()
    print(
        "Final Found Rate: "
        f"{summary['evidence_analysis']['final_found_rate']:.4f}"
    )

    print(
        "Candidate Miss Rate: "
        f"{summary['evidence_analysis']['candidate_miss_rate']:.4f}"
    )

    print(
        "Reranker Miss Rate: "
        f"{summary['evidence_analysis']['reranker_miss_rate']:.4f}"
    )


    print()
    print(
        f"结果已保存到: "
        f"{RUN_DIR}"
    )


if __name__ == "__main__":
    main()