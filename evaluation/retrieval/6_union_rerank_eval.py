import importlib
import json
from pathlib import Path

import numpy as np


# ============================================================
# Recursive Cache
# ============================================================

cache_module = importlib.import_module(
    "src.retrieval_cache"
)

load_recursive_chunks = (
    cache_module.load_or_create_chunks
)

load_recursive_embeddings = (
    cache_module.load_or_create_corpus_embeddings
)

load_answerable_benchmark = (
    cache_module.load_answerable_benchmark
)

load_benchmark_embeddings = (
    cache_module.load_or_create_benchmark_embeddings
)


# ============================================================
# Heading-aware Chunker
# ============================================================

heading_chunker = importlib.import_module(
    "src.ingestion.3_heading_recursive_chunker"
)

load_heading_chunks = (
    heading_chunker.load_or_create_chunks
)


# ============================================================
# Heading-aware Eval Utilities
# ============================================================

heading_eval = importlib.import_module(
    "evaluation.retrieval.5_heading_eval"
)

load_heading_embeddings = (
    heading_eval.load_or_create_heading_embeddings
)

build_heading_bm25 = (
    heading_eval.build_heading_bm25
)


# ============================================================
# BM25
# ============================================================

bm25_module = importlib.import_module(
    "src.retrieval.1_bm25_retriever"
)

tokenize = bm25_module.tokenize


# ============================================================
# Dense
# ============================================================

dense_module = importlib.import_module(
    "src.retrieval.2_dense_retriever"
)

cosine_similarity = (
    dense_module.cosine_similarity
)


# ============================================================
# Recursive BM25
# ============================================================

hybrid_module = importlib.import_module(
    "src.retrieval.3_hybrid_retriever"
)

build_recursive_bm25 = (
    hybrid_module.build_bm25
)


# ============================================================
# Reranker
# ============================================================

rerank_module = importlib.import_module(
    "src.retrieval.4_rerank_retriever"
)

rerank = rerank_module.rerank


# ============================================================
# 复用之前的 Eval Metric
# ============================================================

rerank_eval = importlib.import_module(
    "evaluation.retrieval.4_rerank_eval"
)

evaluate_top5 = (
    rerank_eval.evaluate_top5
)

build_rerank_trace = (
    rerank_eval.build_rerank_trace
)


# ============================================================
# 配置
# ============================================================

SOURCE_TOP_K = 20
FINAL_K = 5

PROJECT_ROOT = Path(__file__).resolve().parents[2]

RUN_DIR = (
    PROJECT_ROOT
    / "evaluation"
    / "runs"
    / "retrieval"
    / "e5_union_rerank"
)


# ============================================================
# Raw Union
# ============================================================

def build_raw_union_candidates(
    query,
    query_vector,
    chunk_vectors,
    bm25,
):
    """
    BM25 Top20
    +
    Dense Top20
    ↓
    Union 去重
    ↓
    不经过 RRF
    不截断回 Top20
    """

    # --------------------------------------------------------
    # BM25 Top20
    # --------------------------------------------------------

    bm25_scores = bm25.get_scores(
        tokenize(query)
    )

    bm25_indices = np.argsort(
        bm25_scores
    )[::-1][:SOURCE_TOP_K]


    # --------------------------------------------------------
    # Dense Top20
    # --------------------------------------------------------

    dense_scores = cosine_similarity(
        query_vector,
        chunk_vectors,
    )

    dense_indices = np.argsort(
        dense_scores
    )[::-1][:SOURCE_TOP_K]


    # --------------------------------------------------------
    # Raw Union
    #
    # 保留 BM25 顺序，
    # 再补入 Dense 中未重复的 Chunk。
    #
    # 最终 Reranker 会重新排序，
    # 所以这里的 Union 顺序不承担最终排名职责。
    # --------------------------------------------------------

    union_indices = list(
        dict.fromkeys(
            [
                int(index)
                for index
                in bm25_indices
            ]
            +
            [
                int(index)
                for index
                in dense_indices
            ]
        )
    )


    return {
        "bm25_indices": [
            int(index)
            for index in bm25_indices
        ],

        "dense_indices": [
            int(index)
            for index in dense_indices
        ],

        "union_indices":
            union_indices,
    }


# ============================================================
# 单个 Pipeline
# ============================================================

def run_union_rerank(
    query,
    query_vector,
    chunks,
    chunk_vectors,
    bm25,
    gold_evidence,
):
    """
    Raw Union
    ↓
    Reranker
    ↓
    Top5
    """

    candidate_result = (
        build_raw_union_candidates(
            query=query,
            query_vector=query_vector,
            chunk_vectors=chunk_vectors,
            bm25=bm25,
        )
    )


    union_indices = (
        candidate_result[
            "union_indices"
        ]
    )


    # --------------------------------------------------------
    # Rerank
    # --------------------------------------------------------

    rerank_results = rerank(
        query=query,
        candidate_indices=union_indices,
        chunks=chunks,
        top_n=FINAL_K,
    )


    # --------------------------------------------------------
    # Metrics
    # --------------------------------------------------------

    metrics = evaluate_top5(
        rerank_results,
        gold_evidence,
    )


    # --------------------------------------------------------
    # Trace
    # --------------------------------------------------------

    reranked_top5 = (
        build_rerank_trace(
            rerank_results,
            gold_evidence,
        )
    )


    return {
        "bm25_candidate_count":
            len(
                candidate_result[
                    "bm25_indices"
                ]
            ),

        "dense_candidate_count":
            len(
                candidate_result[
                    "dense_indices"
                ]
            ),

        "union_candidate_count":
            len(union_indices),

        "union_candidate_chunk_ids": [
            chunks[index]["chunk_id"]
            for index
            in union_indices
        ],

        "metrics":
            metrics,

        "reranked_top5":
            reranked_top5,
    }


# ============================================================
# Metric Summary
# ============================================================

def summarize(
    traces,
    pipeline_key,
):
    count = len(traces)

    if count == 0:
        return {}


    result = {
        "question_count":
            count
    }


    # --------------------------------------------------------
    # Hit Rate
    # --------------------------------------------------------

    for k in [1, 3, 5]:

        result[
            f"hit_rate_at_{k}"
        ] = (
            sum(
                trace[
                    pipeline_key
                ]["metrics"][
                    f"hit_at_{k}"
                ]
                for trace
                in traces
            )
            / count
        )


    # --------------------------------------------------------
    # Recall
    # --------------------------------------------------------

    for k in [1, 3, 5]:

        result[
            f"recall_at_{k}"
        ] = (
            sum(
                trace[
                    pipeline_key
                ]["metrics"][
                    f"recall_at_{k}"
                ]
                for trace
                in traces
            )
            / count
        )


    # --------------------------------------------------------
    # MRR
    # --------------------------------------------------------

    result[
        "mrr_at_5"
    ] = (
        sum(
            trace[
                pipeline_key
            ]["metrics"][
                "rr_at_5"
            ]
            for trace
            in traces
        )
        / count
    )


    return result


# ============================================================
# Candidate Count Summary
# ============================================================

def summarize_candidate_count(
    traces,
    pipeline_key,
):
    sizes = [
        trace[
            pipeline_key
        ][
            "union_candidate_count"
        ]
        for trace
        in traces
    ]


    return {
        "avg":
            (
                sum(sizes)
                / len(sizes)
            ),

        "min":
            min(sizes),

        "max":
            max(sizes),
    }


# ============================================================
# Main
# ============================================================

def main():

    print()
    print("=" * 70)
    print(
        "E5 RAW UNION -> RERANK EVALUATION"
    )
    print("=" * 70)


    # ========================================================
    # 1. Recursive Corpus
    # ========================================================

    recursive_chunks = (
        load_recursive_chunks()
    )

    recursive_vectors = (
        load_recursive_embeddings(
            recursive_chunks
        )
    )


    print()
    print(
        f"Recursive chunks: "
        f"{len(recursive_chunks)}"
    )

    print(
        f"Recursive embeddings: "
        f"{recursive_vectors.shape}"
    )


    # ========================================================
    # 2. Heading-aware Corpus
    # ========================================================

    heading_chunks = (
        load_heading_chunks()
    )

    heading_vectors = (
        load_heading_embeddings(
            heading_chunks
        )
    )


    print()
    print(
        f"Heading chunks: "
        f"{len(heading_chunks)}"
    )

    print(
        f"Heading embeddings: "
        f"{heading_vectors.shape}"
    )


    # ========================================================
    # 3. Benchmark
    # ========================================================

    questions = (
        load_answerable_benchmark()
    )


    question_ids, query_vectors = (
        load_benchmark_embeddings(
            questions
        )
    )


    query_vector_map = {

        question_id:
            query_vectors[index]

        for index, question_id
        in enumerate(question_ids)
    }


    print()
    print(
        f"Benchmark questions: "
        f"{len(questions)}"
    )

    print(
        f"Benchmark embeddings: "
        f"{query_vectors.shape}"
    )


    # ========================================================
    # 4. BM25 Index
    # ========================================================

    print()
    print(
        "Building Recursive BM25..."
    )

    recursive_bm25 = (
        build_recursive_bm25(
            recursive_chunks
        )
    )


    print(
        "Building Heading-aware BM25..."
    )

    heading_bm25 = (
        build_heading_bm25(
            heading_chunks
        )
    )


    # ========================================================
    # 5. Evaluation
    # ========================================================

    traces = []


    for number, question in enumerate(
        questions,
        start=1,
    ):

        question_id = (
            question["id"]
        )

        query = (
            question["question"]
        )

        gold_evidence = (
            question["gold_evidence"]
        )

        query_vector = (
            query_vector_map[
                question_id
            ]
        )


        print()
        print("=" * 70)

        print(
            f"[{number}/{len(questions)}] "
            f"{question_id}"
        )

        print(
            query
        )


        # ====================================================
        # A. Recursive Raw Union
        # ====================================================

        print()
        print(
            "  Recursive Raw Union "
            "-> Rerank Top5"
        )


        recursive_result = (
            run_union_rerank(
                query=query,

                query_vector=
                    query_vector,

                chunks=
                    recursive_chunks,

                chunk_vectors=
                    recursive_vectors,

                bm25=
                    recursive_bm25,

                gold_evidence=
                    gold_evidence,
            )
        )


        print(
            "    Union candidates: "
            f"{recursive_result['union_candidate_count']}"
        )

        print(
            "    Recall@5: "
            f"{recursive_result['metrics']['recall_at_5']:.3f}"
        )


        # ====================================================
        # B. Heading Raw Union
        # ====================================================

        print()
        print(
            "  Heading Raw Union "
            "-> Rerank Top5"
        )


        heading_result = (
            run_union_rerank(
                query=query,

                query_vector=
                    query_vector,

                chunks=
                    heading_chunks,

                chunk_vectors=
                    heading_vectors,

                bm25=
                    heading_bm25,

                gold_evidence=
                    gold_evidence,
            )
        )


        print(
            "    Union candidates: "
            f"{heading_result['union_candidate_count']}"
        )

        print(
            "    Recall@5: "
            f"{heading_result['metrics']['recall_at_5']:.3f}"
        )


        # ====================================================
        # Trace
        # ====================================================

        traces.append(
            {
                "id":
                    question_id,

                "question":
                    query,

                "question_type":
                    question[
                        "question_type"
                    ],

                "hop_type":
                    question[
                        "hop_type"
                    ],

                "gold_evidence_ids": [
                    evidence[
                        "evidence_id"
                    ]
                    for evidence
                    in gold_evidence
                ],

                "recursive_raw_union_rerank_top5":
                    recursive_result,

                "heading_raw_union_rerank_top5":
                    heading_result,
            }
        )


    # ========================================================
    # 6. Groups
    # ========================================================

    single_traces = [
        trace
        for trace in traces
        if trace["hop_type"]
        == "single"
    ]


    multi_traces = [
        trace
        for trace in traces
        if trace["hop_type"]
        == "multi"
    ]


    cross_document_traces = [
        trace
        for trace in traces
        if trace["question_type"]
        == "cross_document"
    ]


    # ========================================================
    # 7. Pipeline Keys
    # ========================================================

    recursive_key = (
        "recursive_raw_union_rerank_top5"
    )

    heading_key = (
        "heading_raw_union_rerank_top5"
    )


    # ========================================================
    # 8. Summary
    # ========================================================

    summary = {

        "experiment":
            "E5-Raw-Union-Rerank",

        "benchmark_question_count":
            len(questions),

        "source_top_k":
            SOURCE_TOP_K,

        "final_k":
            FINAL_K,

        "fusion":
            "raw_union_no_rrf",


        # ====================================================
        # Recursive
        # ====================================================

        "recursive": {

            "chunking":
                "recursive_character_500_o100",

            "chunk_count":
                len(
                    recursive_chunks
                ),

            "retrieval_input":
                "content",

            "reranker_input":
                "content",

            "union_candidate_count":
                summarize_candidate_count(
                    traces,
                    recursive_key,
                ),

            "overall":
                summarize(
                    traces,
                    recursive_key,
                ),

            "single":
                summarize(
                    single_traces,
                    recursive_key,
                ),

            "multi":
                summarize(
                    multi_traces,
                    recursive_key,
                ),

            "cross_document":
                summarize(
                    cross_document_traces,
                    recursive_key,
                ),
        },


        # ====================================================
        # Heading-aware
        # ====================================================

        "heading": {

            "chunking":
                (
                    "heading-aware + "
                    "recursive500_o100"
                ),

            "chunk_count":
                len(
                    heading_chunks
                ),

            "retrieval_input":
                "heading_path + content",

            "reranker_input":
                "heading_path + content",

            "union_candidate_count":
                summarize_candidate_count(
                    traces,
                    heading_key,
                ),

            "overall":
                summarize(
                    traces,
                    heading_key,
                ),

            "single":
                summarize(
                    single_traces,
                    heading_key,
                ),

            "multi":
                summarize(
                    multi_traces,
                    heading_key,
                ),

            "cross_document":
                summarize(
                    cross_document_traces,
                    heading_key,
                ),
        },
    }


    # ========================================================
    # 9. Save
    # ========================================================

    RUN_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )


    # --------------------------------------------------------
    # Trace
    # --------------------------------------------------------

    with (
        RUN_DIR
        / "trace.jsonl"
    ).open(
        "w",
        encoding="utf-8",
    ) as f:

        for trace in traces:

            f.write(
                json.dumps(
                    trace,
                    ensure_ascii=False,
                )
                + "\n"
            )


    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    with (
        RUN_DIR
        / "summary.json"
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


    # ========================================================
    # 10. Console Summary
    # ========================================================

    print()
    print("=" * 70)
    print(
        "RAW UNION -> RERANK RESULT"
    )
    print("=" * 70)


    # --------------------------------------------------------
    # Candidate Count
    # --------------------------------------------------------

    print()
    print("[CANDIDATE COUNT]")


    recursive_count = (
        summary[
            "recursive"
        ][
            "union_candidate_count"
        ]
    )

    heading_count = (
        summary[
            "heading"
        ][
            "union_candidate_count"
        ]
    )


    print()
    print(
        "Recursive:"
    )

    print(
        f"  Avg: "
        f"{recursive_count['avg']:.2f}"
    )

    print(
        f"  Min: "
        f"{recursive_count['min']}"
    )

    print(
        f"  Max: "
        f"{recursive_count['max']}"
    )


    print()
    print(
        "Heading-aware:"
    )

    print(
        f"  Avg: "
        f"{heading_count['avg']:.2f}"
    )

    print(
        f"  Min: "
        f"{heading_count['min']}"
    )

    print(
        f"  Max: "
        f"{heading_count['max']}"
    )


    # --------------------------------------------------------
    # Metrics
    # --------------------------------------------------------

    for group_name in [
        "overall",
        "single",
        "multi",
        "cross_document",
    ]:

        print()
        print("=" * 70)

        print(
            f"[{group_name.upper()}]"
        )

        print("=" * 70)


        for pipeline_name in [
            "recursive",
            "heading",
        ]:

            result = (
                summary[
                    pipeline_name
                ][
                    group_name
                ]
            )


            print()
            print(
                pipeline_name
            )

            print(
                f"  Questions: "
                f"{result['question_count']}"
            )

            print(
                "  Hit Rate@1: "
                f"{result['hit_rate_at_1']:.4f}"
            )

            print(
                "  Hit Rate@3: "
                f"{result['hit_rate_at_3']:.4f}"
            )

            print(
                "  Hit Rate@5: "
                f"{result['hit_rate_at_5']:.4f}"
            )

            print(
                "  Recall@1:   "
                f"{result['recall_at_1']:.4f}"
            )

            print(
                "  Recall@3:   "
                f"{result['recall_at_3']:.4f}"
            )

            print(
                "  Recall@5:   "
                f"{result['recall_at_5']:.4f}"
            )

            print(
                "  MRR@5:      "
                f"{result['mrr_at_5']:.4f}"
            )


    print()

    print(
        f"结果已保存到: "
        f"{RUN_DIR}"
    )


if __name__ == "__main__":
    main()