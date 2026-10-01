import json
from pathlib import Path


# ============================================================
# Paths
# ============================================================

ROOT = Path(__file__).resolve().parents[1]

BENCHMARK_PATH = (
    ROOT
    / "benchmark"
    / "benchmark_v1.jsonl"
)

TRACE_PATH = (
    ROOT
    / "evaluation"
    / "runs"
    / "retrieval"
    / "e4_heading_rerank_ab"
    / "trace.jsonl"
)

CHUNKS_PATH = (
    ROOT
    / "cache"
    / "heading_corpus_chunks.jsonl"
)

OUTPUT_PATH = (
    ROOT
    / "cache"
    / "generation_contexts.jsonl"
)


FINAL_K = 5


# ============================================================
# JSONL
# ============================================================

def load_jsonl(path):
    rows = []

    with path.open(
        "r",
        encoding="utf-8",
    ) as f:

        for line in f:
            line = line.strip()

            if not line:
                continue

            rows.append(
                json.loads(line)
            )

    return rows


# ============================================================
# Load
# ============================================================

def load_benchmark():

    if not BENCHMARK_PATH.exists():
        raise FileNotFoundError(
            f"找不到 Benchmark:\n{BENCHMARK_PATH}"
        )

    return load_jsonl(
        BENCHMARK_PATH
    )


def load_trace():

    if not TRACE_PATH.exists():
        raise FileNotFoundError(
            f"找不到 Heading Reranker Trace:\n{TRACE_PATH}"
        )

    rows = load_jsonl(
        TRACE_PATH
    )

    return {
        row["id"]: row
        for row in rows
    }


def load_chunks():

    if not CHUNKS_PATH.exists():
        raise FileNotFoundError(
            f"找不到 Heading Chunk Cache:\n{CHUNKS_PATH}"
        )

    chunks = load_jsonl(
        CHUNKS_PATH
    )

    return {
        chunk["chunk_id"]: chunk
        for chunk in chunks
    }


# ============================================================
# Build Answerable Context
# ============================================================

def build_answerable_contexts(
    question_id,
    trace_row,
    chunk_lookup,
):

    pipeline = trace_row.get(
        "rrf_top20_rerank_top5"
    )

    if not pipeline:
        raise RuntimeError(
            f"{question_id} 缺少 "
            "rrf_top20_rerank_top5"
        )


    reranked_top5 = pipeline.get(
        "reranked_top5",
        []
    )


    if len(reranked_top5) != FINAL_K:
        raise RuntimeError(
            f"{question_id} 的 reranked_top5 "
            f"数量不是 {FINAL_K}："
            f"{len(reranked_top5)}"
        )


    contexts = []


    for item in reranked_top5:

        chunk_id = item["chunk_id"]


        if chunk_id not in chunk_lookup:
            raise RuntimeError(
                f"{question_id}: "
                f"找不到 chunk_id = {chunk_id}"
            )


        chunk = chunk_lookup[
            chunk_id
        ]


        contexts.append(
            {
                "source_id":
                    f"S{item['rank']}",

                "rank":
                    item["rank"],

                "chunk_id":
                    chunk_id,

                "source":
                    item["source"],

                "heading_path":
                    chunk.get(
                        "heading_path",
                        "",
                    ),

                "content":
                    chunk["content"],

                "rerank_score":
                    item.get(
                        "rerank_score"
                    ),
            }
        )


    return contexts


# ============================================================
# Validation
# ============================================================

def validate_cache(rows):

    if len(rows) != 50:
        raise RuntimeError(
            f"应有 50 题，实际 {len(rows)}"
        )


    ids = [
        row["id"]
        for row in rows
    ]


    if len(ids) != len(set(ids)):
        raise RuntimeError(
            "存在重复 question id"
        )


    answerable_rows = [
        row
        for row in rows
        if row["answerable"]
    ]

    unanswerable_rows = [
        row
        for row in rows
        if not row["answerable"]
    ]


    if len(answerable_rows) != 45:
        raise RuntimeError(
            "Answerable 数量不是 45："
            f"{len(answerable_rows)}"
        )


    if len(unanswerable_rows) != 5:
        raise RuntimeError(
            "Unanswerable 数量不是 5："
            f"{len(unanswerable_rows)}"
        )


    # Answerable 必须有固定 Top5
    for row in answerable_rows:

        if len(row["contexts"]) != FINAL_K:
            raise RuntimeError(
                f"{row['id']} "
                "Context 数量不是 5"
            )


    # Unanswerable 必须无 Context
    for row in unanswerable_rows:

        if row["contexts"]:
            raise RuntimeError(
                f"{row['id']} "
                "是 unanswerable，"
                "但 contexts 非空"
            )


# ============================================================
# Main
# ============================================================

def main():

    print()
    print("=" * 70)
    print(
        "PREPARE GENERATION CONTEXT CACHE"
    )
    print("=" * 70)


    benchmark = load_benchmark()

    trace_lookup = load_trace()

    chunk_lookup = load_chunks()


    print(
        f"Benchmark questions: "
        f"{len(benchmark)}"
    )

    print(
        f"Retrieval traces: "
        f"{len(trace_lookup)}"
    )

    print(
        f"Heading chunks: "
        f"{len(chunk_lookup)}"
    )


    rows = []


    for question in benchmark:

        question_id = question["id"]

        answerable = question[
            "answerable"
        ]


        # ====================================================
        # Answerable
        # ====================================================

        if answerable:

            if question_id not in trace_lookup:
                raise RuntimeError(
                    f"{question_id} 是 answerable，"
                    "但 Retrieval Trace 中不存在"
                )


            contexts = (
                build_answerable_contexts(
                    question_id=
                        question_id,

                    trace_row=
                        trace_lookup[
                            question_id
                        ],

                    chunk_lookup=
                        chunk_lookup,
                )
            )


        # ====================================================
        # Unanswerable
        #
        # 当前 Generation Benchmark 定义：
        #
        # No Evidence
        # → contexts = []
        # → 测试 Generator Abstention
        # ====================================================

        else:

            contexts = []


        # ====================================================
        # Cache Record
        # ====================================================

        rows.append(
            {
                "id":
                    question_id,

                "question":
                    question["question"],

                "question_type":
                    question[
                        "question_type"
                    ],

                "difficulty":
                    question[
                        "difficulty"
                    ],

                "answerable":
                    answerable,

                "hop_type":
                    question[
                        "hop_type"
                    ],

                "contexts":
                    contexts,
            }
        )


    # ========================================================
    # Validate
    # ========================================================

    validate_cache(
        rows
    )


    # ========================================================
    # Save
    # ========================================================

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )


    with OUTPUT_PATH.open(
        "w",
        encoding="utf-8",
    ) as f:

        for row in rows:

            f.write(
                json.dumps(
                    row,
                    ensure_ascii=False,
                )
                + "\n"
            )


    # ========================================================
    # Summary
    # ========================================================

    answerable_count = sum(
        row["answerable"]
        for row in rows
    )

    unanswerable_count = (
        len(rows)
        - answerable_count
    )


    print()
    print("=" * 70)
    print("DONE")
    print("=" * 70)

    print(
        f"Total:        {len(rows)}"
    )

    print(
        f"Answerable:   {answerable_count}"
    )

    print(
        f"Unanswerable: {unanswerable_count}"
    )

    print(
        f"Answerable contexts: "
        f"{FINAL_K} each"
    )

    print(
        "Unanswerable contexts: 0"
    )

    print()

    print(
        f"Saved:\n{OUTPUT_PATH}"
    )


if __name__ == "__main__":
    main()