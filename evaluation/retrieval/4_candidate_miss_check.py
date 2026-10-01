import importlib
import json
import re
from pathlib import Path

import numpy as np


# ============================================================
# 导入已有模块
# ============================================================

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


bm25_module = importlib.import_module(
    "src.retrieval.1_bm25_retriever"
)

tokenize = bm25_module.tokenize


dense_module = importlib.import_module(
    "src.retrieval.2_dense_retriever"
)

cosine_similarity = (
    dense_module.cosine_similarity
)


hybrid_module = importlib.import_module(
    "src.retrieval.3_hybrid_retriever"
)

build_bm25 = hybrid_module.build_bm25

reciprocal_rank_fusion = (
    hybrid_module.reciprocal_rank_fusion
)


# ============================================================
# 配置
# ============================================================

TOP_K = 20
RRF_K = 60

PROJECT_ROOT = Path(__file__).resolve().parents[2]

ERROR_TRACE_PATH = (
    PROJECT_ROOT
    / "evaluation"
    / "runs"
    / "retrieval"
    / "e3_rerank_error_analysis"
    / "trace.jsonl"
)

RUN_DIR = (
    PROJECT_ROOT
    / "evaluation"
    / "runs"
    / "retrieval"
    / "e3_candidate_miss_check"
)


# ============================================================
# 文本处理
# ============================================================

def normalize_text(text):
    return re.sub(
        r"\s+",
        " ",
        text,
    ).strip()


def chunk_matches_evidence(
    chunk,
    evidence,
):
    chunk_file = Path(
        chunk["source"]
    ).name

    if chunk_file != evidence["document"]:
        return False

    chunk_text = normalize_text(
        chunk["content"]
    )

    evidence_text = normalize_text(
        evidence["evidence"]
    )

    return evidence_text in chunk_text


# ============================================================
# 加载 Error Trace
# ============================================================

def load_error_trace():

    traces = []

    with ERROR_TRACE_PATH.open(
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
# Rank Map
# ============================================================

def build_rank_map(indices):
    """
    index -> rank
    rank 从 1 开始
    """

    return {
        int(index): rank
        for rank, index
        in enumerate(
            indices,
            start=1,
        )
    }


# ============================================================
# Main
# ============================================================

def main():

    print()
    print("=" * 70)
    print("CANDIDATE MISS CHECK")
    print("=" * 70)


    # --------------------------------------------------------
    # 1. Cache
    # --------------------------------------------------------

    chunks = load_or_create_chunks()

    chunk_vectors = (
        load_or_create_corpus_embeddings(
            chunks
        )
    )

    questions = (
        load_answerable_benchmark()
    )

    question_ids, query_vectors = (
        load_or_create_benchmark_embeddings(
            questions
        )
    )


    question_map = {
        question["id"]: question
        for question in questions
    }

    query_vector_map = {
        question_id: query_vectors[i]
        for i, question_id
        in enumerate(question_ids)
    }


    # --------------------------------------------------------
    # 2. Error Trace
    # --------------------------------------------------------

    error_traces = load_error_trace()

    candidate_miss_traces = [
        trace
        for trace in error_traces
        if trace["category"]
        in {
            "candidate_miss",
            "mixed",
        }
    ]


    print(
        f"Candidate-miss questions: "
        f"{len(candidate_miss_traces)}"
    )


    # --------------------------------------------------------
    # 3. BM25
    # --------------------------------------------------------

    bm25 = build_bm25(
        chunks
    )


    results = []


    # --------------------------------------------------------
    # 4. 分析每一道 Candidate Miss
    # --------------------------------------------------------

    for trace in candidate_miss_traces:

        question_id = trace["id"]

        question = question_map[
            question_id
        ]

        query = question["question"]

        query_vector = query_vector_map[
            question_id
        ]


        print()
        print("=" * 70)
        print(question_id)
        print(query)
        print("=" * 70)


        # ====================================================
        # BM25 全量 Ranking
        # ====================================================

        bm25_scores = bm25.get_scores(
            tokenize(query)
        )

        bm25_full_indices = np.argsort(
            bm25_scores
        )[::-1]

        bm25_rank_map = build_rank_map(
            bm25_full_indices
        )

        bm25_top20 = (
            bm25_full_indices[:TOP_K]
        )


        # ====================================================
        # Dense 全量 Ranking
        # ====================================================

        dense_scores = cosine_similarity(
            query_vector,
            chunk_vectors,
        )

        dense_full_indices = np.argsort(
            dense_scores
        )[::-1]

        dense_rank_map = build_rank_map(
            dense_full_indices
        )

        dense_top20 = (
            dense_full_indices[:TOP_K]
        )


        # ====================================================
        # 实际 RRF Union
        # ====================================================

        fused = reciprocal_rank_fusion(
            bm25_top20,
            dense_top20,
            rrf_k=RRF_K,
        )

        rrf_ranked = sorted(
            fused.items(),
            key=lambda item:
                item[1]["rrf_score"],
            reverse=True,
        )

        rrf_full_indices = [
            int(chunk_index)
            for chunk_index, _
            in rrf_ranked
        ]

        rrf_rank_map = build_rank_map(
            rrf_full_indices
        )


        # ====================================================
        # 只分析漏掉的 Evidence
        # ====================================================

        missed_ids = set(
            trace["candidate_missed_ids"]
        )

        question_result = {
            "id":
                question_id,

            "question":
                query,

            "missed_evidence":
                [],
        }


        for evidence in question[
            "gold_evidence"
        ]:

            evidence_id = (
                evidence["evidence_id"]
            )

            if evidence_id not in missed_ids:
                continue


            # ------------------------------------------------
            # 找出所有能完整覆盖该 Evidence 的 Chunk
            # ------------------------------------------------

            matching_indices = [
                index
                for index, chunk
                in enumerate(chunks)
                if chunk_matches_evidence(
                    chunk,
                    evidence,
                )
            ]


            # ------------------------------------------------
            # 找最佳 Rank
            # ------------------------------------------------

            bm25_ranks = [
                bm25_rank_map[index]
                for index in matching_indices
            ]

            dense_ranks = [
                dense_rank_map[index]
                for index in matching_indices
            ]

            rrf_ranks = [
                rrf_rank_map[index]
                for index in matching_indices
                if index in rrf_rank_map
            ]


            best_bm25_rank = (
                min(bm25_ranks)
                if bm25_ranks
                else None
            )

            best_dense_rank = (
                min(dense_ranks)
                if dense_ranks
                else None
            )

            best_rrf_rank = (
                min(rrf_ranks)
                if rrf_ranks
                else None
            )


            # ------------------------------------------------
            # 简单归因
            # ------------------------------------------------

            in_bm25_top20 = (
                best_bm25_rank is not None
                and best_bm25_rank <= TOP_K
            )

            in_dense_top20 = (
                best_dense_rank is not None
                and best_dense_rank <= TOP_K
            )


            if (
                not in_bm25_top20
                and not in_dense_top20
            ):

                reason = (
                    "retrieval_miss"
                )

            elif (
                best_rrf_rank is None
                or best_rrf_rank > TOP_K
            ):

                reason = (
                    "fusion_miss"
                )

            else:

                reason = (
                    "unexpected"
                )


            # ------------------------------------------------
            # 输出
            # ------------------------------------------------

            print()

            print(
                f"Evidence: {evidence_id}"
            )

            print(
                f"Document: "
                f"{evidence['document']}"
            )

            print(
                f"BM25 best rank: "
                f"{best_bm25_rank}"
            )

            print(
                f"Dense best rank: "
                f"{best_dense_rank}"
            )

            print(
                f"RRF rank: "
                f"{best_rrf_rank}"
            )

            print(
                f"Reason: {reason}"
            )


            # ------------------------------------------------
            # 找最佳匹配 Chunk
            # ------------------------------------------------

            if matching_indices:

                best_index = min(
                    matching_indices,
                    key=lambda index:
                        min(
                            bm25_rank_map[index],
                            dense_rank_map[index],
                        )
                )

                best_chunk = chunks[
                    best_index
                ]

                print(
                    f"Chunk ID: "
                    f"{best_chunk['chunk_id']}"
                )

                print()
                print(
                    best_chunk[
                        "content"
                    ][:500]
                )


            # ------------------------------------------------
            # 保存
            # ------------------------------------------------

            question_result[
                "missed_evidence"
            ].append(
                {
                    "evidence_id":
                        evidence_id,

                    "document":
                        evidence["document"],

                    "evidence":
                        evidence["evidence"],

                    "matching_chunk_ids": [
                        chunks[index][
                            "chunk_id"
                        ]
                        for index
                        in matching_indices
                    ],

                    "best_bm25_rank":
                        best_bm25_rank,

                    "best_dense_rank":
                        best_dense_rank,

                    "best_rrf_rank":
                        best_rrf_rank,

                    "in_bm25_top20":
                        in_bm25_top20,

                    "in_dense_top20":
                        in_dense_top20,

                    "reason":
                        reason,
                }
            )


        results.append(
            question_result
        )


    # --------------------------------------------------------
    # 5. 汇总
    # --------------------------------------------------------

    reason_count = {
        "retrieval_miss": 0,
        "fusion_miss": 0,
        "unexpected": 0,
    }


    for question in results:

        for evidence in question[
            "missed_evidence"
        ]:

            reason_count[
                evidence["reason"]
            ] += 1


    summary = {
        "experiment":
            "E3-Candidate-Miss-Check",

        "question_count":
            len(results),

        "missed_evidence_count":
            sum(
                reason_count.values()
            ),

        "reason_count":
            reason_count,
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
    # 7. Console Summary
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)

    print(
        f"Candidate-miss questions: "
        f"{len(results)}"
    )

    print(
        f"Missed Gold Evidence: "
        f"{summary['missed_evidence_count']}"
    )

    print()

    for reason, count in reason_count.items():

        print(
            f"{reason}: {count}"
        )


    print()
    print(
        f"结果已保存到: "
        f"{RUN_DIR}"
    )


if __name__ == "__main__":
    main()