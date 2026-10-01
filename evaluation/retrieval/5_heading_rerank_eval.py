import importlib
import json
from pathlib import Path

import numpy as np


# ============================================================
# Heading-aware Chunker
# ============================================================

heading_chunker = importlib.import_module(
    "src.ingestion.3_heading_recursive_chunker"
)

load_and_chunk_corpus = (
    heading_chunker.load_and_chunk_corpus
)


# ============================================================
# 复用 Heading Retrieval Eval
# ============================================================

heading_eval = importlib.import_module(
    "evaluation.retrieval.5_heading_eval"
)

load_or_create_heading_embeddings = (
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
# Hybrid / RRF
# ============================================================

hybrid_module = importlib.import_module(
    "src.retrieval.3_hybrid_retriever"
)

reciprocal_rank_fusion = (
    hybrid_module.reciprocal_rank_fusion
)


# ============================================================
# Reranker
# ============================================================

rerank_module = importlib.import_module(
    "src.retrieval.4_rerank_retriever"
)

rerank = rerank_module.rerank


# ============================================================
# 复用原 Reranker Eval 的指标逻辑
# ============================================================

old_rerank_eval = importlib.import_module(
    "evaluation.retrieval.4_rerank_eval"
)

evaluate_top5 = (
    old_rerank_eval.evaluate_top5
)

build_rerank_trace = (
    old_rerank_eval.build_rerank_trace
)

summarize = (
    old_rerank_eval.summarize
)


# ============================================================
# Benchmark Cache
# ============================================================

cache_module = importlib.import_module(
    "src.retrieval_cache"
)

load_answerable_benchmark = (
    cache_module.load_answerable_benchmark
)

load_or_create_benchmark_embeddings = (
    cache_module.load_or_create_benchmark_embeddings
)


# ============================================================
# 配置
# ============================================================

CANDIDATE_K = 20
FINAL_K = 5
RRF_K = 60

PROJECT_ROOT = Path(__file__).resolve().parents[2]

RUN_DIR = (
    PROJECT_ROOT
    / "evaluation"
    / "runs"
    / "retrieval"
    / "e4_heading_rerank_ab"
)


# ============================================================
# Dense Top20
# ============================================================

def dense_top20(
    query_vector,
    chunk_vectors,
):

    scores = cosine_similarity(
        query_vector,
        chunk_vectors,
    )

    indices = np.argsort(
        scores
    )[::-1][:CANDIDATE_K]

    return [
        int(index)
        for index in indices
    ]


# ============================================================
# RRF Top20
# ============================================================

def rrf_top20(
    query,
    query_vector,
    chunk_vectors,
    bm25,
):

    # --------------------------------------------------------
    # BM25 Top20
    # --------------------------------------------------------

    bm25_scores = bm25.get_scores(
        tokenize(query)
    )

    bm25_indices = np.argsort(
        bm25_scores
    )[::-1][:CANDIDATE_K]


    # --------------------------------------------------------
    # Dense Top20
    # --------------------------------------------------------

    dense_scores = cosine_similarity(
        query_vector,
        chunk_vectors,
    )

    dense_indices = np.argsort(
        dense_scores
    )[::-1][:CANDIDATE_K]


    # --------------------------------------------------------
    # RRF
    # --------------------------------------------------------

    fused = reciprocal_rank_fusion(
        bm25_indices,
        dense_indices,
        rrf_k=RRF_K,
    )


    ranked = sorted(
        fused.items(),
        key=lambda item:
            item[1]["rrf_score"],
        reverse=True,
    )


    return [
        int(chunk_index)
        for chunk_index, _
        in ranked[:CANDIDATE_K]
    ]


# ============================================================
# Main
# ============================================================

def main():

    print()
    print("=" * 70)
    print(
        "E4 HEADING-AWARE "
        "RERANKER A/B"
    )
    print("=" * 70)


    # --------------------------------------------------------
    # 1. Heading-aware Chunks
    # --------------------------------------------------------

    documents, chunks = (
        load_and_chunk_corpus()
    )

    print(
        f"Documents: "
        f"{len(documents)}"
    )

    print(
        f"Chunks: "
        f"{len(chunks)}"
    )


    # --------------------------------------------------------
    # 2. Heading Embeddings
    #
    # 第一次没有 Cache 会生成。
    # 以后直接 Cache HIT。
    # --------------------------------------------------------

    chunk_vectors = (
        load_or_create_heading_embeddings(
            chunks
        )
    )

    print(
        f"Heading embeddings: "
        f"{chunk_vectors.shape}"
    )


    # --------------------------------------------------------
    # 3. Benchmark
    # --------------------------------------------------------

    questions = (
        load_answerable_benchmark()
    )

    print(
        f"Questions: "
        f"{len(questions)}"
    )


    # --------------------------------------------------------
    # 4. Benchmark Embeddings
    #
    # 继续复用原有 45 个 Query Embedding
    # --------------------------------------------------------

    question_ids, query_vectors = (
        load_or_create_benchmark_embeddings(
            questions
        )
    )


    query_vector_map = {

        question_id:
            query_vectors[index]

        for index, question_id
        in enumerate(question_ids)
    }


    # --------------------------------------------------------
    # 5. Heading-aware BM25
    #
    # retrieval_text =
    # heading_path + content
    # --------------------------------------------------------

    print(
        "Building heading-aware BM25..."
    )

    bm25 = build_heading_bm25(
        chunks
    )


    # --------------------------------------------------------
    # 6. Evaluation
    # --------------------------------------------------------

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

        query_vector = (
            query_vector_map[
                question_id
            ]
        )


        print()
        print(
            f"[{number}/{len(questions)}] "
            f"{question_id}"
        )


        # ====================================================
        # A. Heading Dense Top20
        # ====================================================

        dense_candidates = dense_top20(
            query_vector,
            chunk_vectors,
        )


        print(
            "  Heading Dense Top20 "
            "-> Rerank Top5"
        )


        dense_rerank_results = rerank(
            query=query,

            candidate_indices=
                dense_candidates,

            chunks=chunks,

            top_n=FINAL_K,
        )


        dense_metrics = evaluate_top5(
            dense_rerank_results,
            question["gold_evidence"],
        )


        # ====================================================
        # B. Heading RRF Top20
        # ====================================================

        rrf_candidates = rrf_top20(
            query=query,

            query_vector=query_vector,

            chunk_vectors=
                chunk_vectors,

            bm25=bm25,
        )


        print(
            "  Heading RRF Top20 "
            "-> Rerank Top5"
        )


        rrf_rerank_results = rerank(
            query=query,

            candidate_indices=
                rrf_candidates,

            chunks=chunks,

            top_n=FINAL_K,
        )


        rrf_metrics = evaluate_top5(
            rrf_rerank_results,
            question["gold_evidence"],
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
                    in question[
                        "gold_evidence"
                    ]
                ],


                # --------------------------------------------
                # Dense20 -> Rerank5
                # --------------------------------------------

                "dense_top20_rerank_top5": {

                    "candidate_chunk_ids": [
                        chunks[index][
                            "chunk_id"
                        ]
                        for index
                        in dense_candidates
                    ],

                    "metrics":
                        dense_metrics,

                    "reranked_top5":
                        build_rerank_trace(
                            dense_rerank_results,
                            question[
                                "gold_evidence"
                            ],
                        ),
                },


                # --------------------------------------------
                # RRF20 -> Rerank5
                # --------------------------------------------

                "rrf_top20_rerank_top5": {

                    "candidate_chunk_ids": [
                        chunks[index][
                            "chunk_id"
                        ]
                        for index
                        in rrf_candidates
                    ],

                    "metrics":
                        rrf_metrics,

                    "reranked_top5":
                        build_rerank_trace(
                            rrf_rerank_results,
                            question[
                                "gold_evidence"
                            ],
                        ),
                },
            }
        )


        print(
            "    Dense Recall@5: "
            f"{dense_metrics['recall_at_5']:.3f}"
        )

        print(
            "    RRF   Recall@5: "
            f"{rrf_metrics['recall_at_5']:.3f}"
        )


    # --------------------------------------------------------
    # 7. 分组
    # --------------------------------------------------------

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


    # --------------------------------------------------------
    # 8. Summary
    # --------------------------------------------------------

    summary = {

        "experiment":
            "E4-Heading-Reranker-AB",

        "chunking":
            (
                "heading-aware + "
                "recursive500_o100"
            ),

        "chunk_count":
            len(chunks),

        "retrieval_input":
            "heading_path + content",

        "reranker_input":
            "heading_path + content",

        "candidate_k":
            CANDIDATE_K,

        "final_k":
            FINAL_K,

        "rrf_k":
            RRF_K,

        "comparison": [
            "dense_top20_rerank_top5",
            "rrf_top20_rerank_top5",
        ],

        "overall":
            summarize(
                traces
            ),

        "single":
            summarize(
                single_traces
            ),

        "multi":
            summarize(
                multi_traces
            ),

        "cross_document":
            summarize(
                cross_document_traces
            ),
    }


    # --------------------------------------------------------
    # 9. 保存
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

        for trace in traces:

            f.write(
                json.dumps(
                    trace,
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
    # 10. Console
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print(
        "HEADING-AWARE "
        "RERANKER A/B RESULT"
    )
    print("=" * 70)


    for group_name in [
        "overall",
        "single",
        "multi",
        "cross_document",
    ]:

        group = summary[
            group_name
        ]


        print()
        print(
            f"[{group_name.upper()}]"
        )

        print(
            f"Questions: "
            f"{group['question_count']}"
        )


        for strategy in [
            "dense_top20_rerank_top5",
            "rrf_top20_rerank_top5",
        ]:

            result = group[
                strategy
            ]


            print()
            print(
                strategy
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