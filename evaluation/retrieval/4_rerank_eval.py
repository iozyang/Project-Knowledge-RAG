import importlib
import json
import re
from pathlib import Path

import numpy as np


# ============================================================
# 导入已有模块
# ============================================================

# BM25
bm25_module = importlib.import_module(
    "src.retrieval.1_bm25_retriever"
)

tokenize = bm25_module.tokenize


# Dense
dense_module = importlib.import_module(
    "src.retrieval.2_dense_retriever"
)

cosine_similarity = (
    dense_module.cosine_similarity
)


# Hybrid
hybrid_module = importlib.import_module(
    "src.retrieval.3_hybrid_retriever"
)

build_bm25 = hybrid_module.build_bm25

reciprocal_rank_fusion = (
    hybrid_module.reciprocal_rank_fusion
)


# Reranker
rerank_module = importlib.import_module(
    "src.retrieval.4_rerank_retriever"
)

rerank = rerank_module.rerank


# Cache
cache_module = importlib.import_module(
    "src.retrieval_cache"
)

load_or_create_chunks = (
    cache_module.load_or_create_chunks
)

load_or_create_corpus_embeddings = (
    cache_module.load_or_create_corpus_embeddings
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
    / "e3_rerank_ab"
)


# ============================================================
# Gold Evidence Match
# ============================================================

def normalize_text(text):
    return re.sub(
        r"\s+",
        " ",
        text,
    ).strip()


def find_matched_evidence(
    chunk,
    gold_evidence,
):
    """
    判断一个 chunk 命中了哪些 Gold Evidence。

    规则继续沿用前面的实验：

    1. document 文件名相同
    2. normalized evidence 是 chunk content 的子串
    """

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
# Retrieval
# ============================================================

def dense_top20(
    query_vector,
    chunk_vectors,
):
    """
    使用已经缓存的 Benchmark Query Embedding。

    不再调用 Embedding API。
    """

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


def rrf_top20(
    query,
    query_vector,
    chunks,
    chunk_vectors,
    bm25,
):
    """
    BM25 Top20
        +
    Dense Top20
        ↓
    Union + RRF
        ↓
    Top20
    """


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
# Metrics
# ============================================================

def evaluate_top5(
    results,
    gold_evidence,
):
    """
    对 Reranker 输出的 Top5 计算：

    Hit@1 / 3 / 5
    Recall@1 / 3 / 5
    RR@5
    """

    gold_ids = {
        evidence["evidence_id"]
        for evidence in gold_evidence
    }


    matched_by_rank = []

    for result in results:

        matched = find_matched_evidence(
            result["chunk"],
            gold_evidence,
        )

        matched_by_rank.append(
            set(matched)
        )


    metrics = {}


    for k in [1, 3, 5]:

        matched_ids = set()

        for matched in matched_by_rank[:k]:

            matched_ids.update(
                matched
            )


        metrics[
            f"hit_at_{k}"
        ] = (
            1
            if matched_ids
            else 0
        )


        metrics[
            f"recall_at_{k}"
        ] = (
            len(matched_ids)
            / len(gold_ids)
            if gold_ids
            else 0.0
        )


    # --------------------------------------------------------
    # RR@5
    # --------------------------------------------------------

    rr = 0.0

    for rank, matched in enumerate(
        matched_by_rank,
        start=1,
    ):

        if matched:

            rr = 1.0 / rank
            break


    metrics["rr_at_5"] = rr


    return metrics


# ============================================================
# Trace
# ============================================================

def build_rerank_trace(
    results,
    gold_evidence,
):
    """
    保存 Reranker Top5 的详细排序，
    后面方便做 Error Analysis。
    """

    trace = []

    for result in results:

        chunk = result["chunk"]

        matched_ids = (
            find_matched_evidence(
                chunk,
                gold_evidence,
            )
        )


        trace.append(
            {
                "rank":
                    result["rank"],

                "chunk_id":
                    chunk["chunk_id"],

                "source":
                    chunk["source"],

                "rerank_score":
                    result["rerank_score"],

                "matched_evidence_ids":
                    matched_ids,
            }
        )


    return trace


# ============================================================
# Summary
# ============================================================

def summarize(traces):

    count = len(traces)

    if count == 0:
        return {}


    strategies = [
        "dense_top20_rerank_top5",
        "rrf_top20_rerank_top5",
    ]


    summary = {
        "question_count": count
    }


    for strategy in strategies:

        summary[strategy] = {}


        for k in [1, 3, 5]:

            summary[strategy][
                f"hit_rate_at_{k}"
            ] = sum(
                trace[strategy]["metrics"][
                    f"hit_at_{k}"
                ]
                for trace in traces
            ) / count


            summary[strategy][
                f"recall_at_{k}"
            ] = sum(
                trace[strategy]["metrics"][
                    f"recall_at_{k}"
                ]
                for trace in traces
            ) / count


        summary[strategy][
            "mrr_at_5"
        ] = sum(
            trace[strategy]["metrics"][
                "rr_at_5"
            ]
            for trace in traces
        ) / count


    return summary


# ============================================================
# Main
# ============================================================

def main():

    print()
    print("=" * 70)
    print("E3 RERANKER A/B EVALUATION")
    print("=" * 70)


    # --------------------------------------------------------
    # 1. Cached Corpus Chunks
    # --------------------------------------------------------

    chunks = (
        load_or_create_chunks()
    )

    print(
        f"Chunks: {len(chunks)}"
    )


    # --------------------------------------------------------
    # 2. Cached Corpus Embeddings
    # --------------------------------------------------------

    chunk_vectors = (
        load_or_create_corpus_embeddings(
            chunks
        )
    )

    print(
        f"Corpus embeddings: "
        f"{chunk_vectors.shape}"
    )


    # --------------------------------------------------------
    # 3. Benchmark
    # --------------------------------------------------------

    questions = (
        load_answerable_benchmark()
    )

    print(
        f"Questions: {len(questions)}"
    )


    # --------------------------------------------------------
    # 4. Cached Benchmark Embeddings
    # --------------------------------------------------------

    question_ids, query_vectors = (
        load_or_create_benchmark_embeddings(
            questions
        )
    )


    print(
        f"Benchmark embeddings: "
        f"{query_vectors.shape}"
    )


    # --------------------------------------------------------
    # ID -> Embedding
    # --------------------------------------------------------

    query_vector_map = {

        question_id:
            query_vectors[index]

        for index, question_id
        in enumerate(question_ids)
    }


    # --------------------------------------------------------
    # 5. BM25 Index
    # --------------------------------------------------------

    print(
        "Building BM25 index..."
    )

    bm25 = build_bm25(
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
        # A. Dense Top20
        # ====================================================

        dense_candidates = dense_top20(
            query_vector,
            chunk_vectors,
        )


        # ====================================================
        # Dense Top20 -> Rerank Top5
        # ====================================================

        print(
            "  Dense Top20 -> Rerank Top5"
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
        # B. RRF Top20
        # ====================================================

        rrf_candidates = rrf_top20(
            query=query,

            query_vector=query_vector,

            chunks=chunks,

            chunk_vectors=
                chunk_vectors,

            bm25=bm25,
        )


        # ====================================================
        # RRF Top20 -> Rerank Top5
        # ====================================================

        print(
            "  RRF Top20 -> Rerank Top5"
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

        trace = {

            "id":
                question_id,

            "question":
                query,

            "question_type":
                question["question_type"],

            "hop_type":
                question["hop_type"],

            "gold_evidence_ids": [
                evidence["evidence_id"]
                for evidence
                in question["gold_evidence"]
            ],


            # ------------------------------------------------
            # Dense -> Rerank
            # ------------------------------------------------

            "dense_top20_rerank_top5": {

                "candidate_chunk_ids": [
                    chunks[index]["chunk_id"]
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


            # ------------------------------------------------
            # RRF -> Rerank
            # ------------------------------------------------

            "rrf_top20_rerank_top5": {

                "candidate_chunk_ids": [
                    chunks[index]["chunk_id"]
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


        traces.append(
            trace
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
            "E3-Reranker-AB",

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


    # Trace
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


    # Summary
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
    # 10. Console Summary
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("E3 RERANKER A/B RESULT")
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
            print(strategy)

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