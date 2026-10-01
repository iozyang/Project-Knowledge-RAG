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


rerank_module = importlib.import_module(
    "src.retrieval.4_rerank_retriever"
)

rerank = rerank_module.rerank


# ============================================================
# 配置
# ============================================================

TOP_K = 20
FINAL_K = 5

PROJECT_ROOT = Path(__file__).resolve().parents[2]

CANDIDATE_MISS_TRACE = (
    PROJECT_ROOT
    / "evaluation"
    / "runs"
    / "retrieval"
    / "e3_candidate_miss_check"
    / "trace.jsonl"
)

RUN_DIR = (
    PROJECT_ROOT
    / "evaluation"
    / "runs"
    / "retrieval"
    / "e3_union_rerank_probe"
)


# ============================================================
# 文本匹配
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
# 找出 fusion_miss 问题
# ============================================================

def load_fusion_miss_question_ids():

    question_ids = set()

    with CANDIDATE_MISS_TRACE.open(
        "r",
        encoding="utf-8",
    ) as f:

        for line in f:

            if not line.strip():
                continue

            item = json.loads(line)

            for evidence in item[
                "missed_evidence"
            ]:

                if (
                    evidence["reason"]
                    == "fusion_miss"
                ):

                    question_ids.add(
                        item["id"]
                    )

    return sorted(
        question_ids
    )


# ============================================================
# Raw Union
# ============================================================

def build_union_candidates(
    query,
    query_vector,
    chunks,
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
    )[::-1][:TOP_K]


    # --------------------------------------------------------
    # Dense Top20
    # --------------------------------------------------------

    dense_scores = cosine_similarity(
        query_vector,
        chunk_vectors,
    )

    dense_indices = np.argsort(
        dense_scores
    )[::-1][:TOP_K]


    # --------------------------------------------------------
    # Union 去重
    #
    # 不做 RRF
    # 不截断回 Top20
    # --------------------------------------------------------

    union_indices = list(
        dict.fromkeys(
            [
                int(index)
                for index in bm25_indices
            ]
            +
            [
                int(index)
                for index in dense_indices
            ]
        )
    )


    return (
        [int(i) for i in bm25_indices],
        [int(i) for i in dense_indices],
        union_indices,
    )


# ============================================================
# Main
# ============================================================

def main():

    print()
    print("=" * 70)
    print("RAW UNION -> RERANK PROBE")
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
    # 2. 只取 fusion_miss
    # --------------------------------------------------------

    target_ids = (
        load_fusion_miss_question_ids()
    )

    print(
        f"Fusion-miss questions: "
        f"{target_ids}"
    )


    # --------------------------------------------------------
    # 3. BM25
    # --------------------------------------------------------

    bm25 = build_bm25(
        chunks
    )


    results = []


    # --------------------------------------------------------
    # 4. Probe
    # --------------------------------------------------------

    for question_id in target_ids:

        question = question_map[
            question_id
        ]

        query = question[
            "question"
        ]

        query_vector = (
            query_vector_map[
                question_id
            ]
        )

        gold_evidence = (
            question[
                "gold_evidence"
            ]
        )

        gold_ids = {
            evidence["evidence_id"]
            for evidence in gold_evidence
        }


        print()
        print("=" * 70)
        print(
            f"{question_id}: {query}"
        )
        print("=" * 70)


        # ====================================================
        # Raw Union
        # ====================================================

        (
            bm25_indices,
            dense_indices,
            union_indices,
        ) = build_union_candidates(
            query=query,
            query_vector=query_vector,
            chunks=chunks,
            chunk_vectors=chunk_vectors,
            bm25=bm25,
        )


        print(
            f"BM25 Top20: "
            f"{len(bm25_indices)}"
        )

        print(
            f"Dense Top20: "
            f"{len(dense_indices)}"
        )

        print(
            f"Union after dedupe: "
            f"{len(union_indices)}"
        )


        # ====================================================
        # Union Candidate 中有哪些 Gold
        # ====================================================

        union_found_ids = set()

        for index in union_indices:

            union_found_ids.update(
                find_matched_evidence(
                    chunks[index],
                    gold_evidence,
                )
            )


        print(
            f"Gold IDs: "
            f"{sorted(gold_ids)}"
        )

        print(
            f"Union found: "
            f"{sorted(union_found_ids)}"
        )


        # ====================================================
        # Reranker
        # ====================================================

        print(
            "Reranking Union -> Top5..."
        )

        reranked = rerank(
            query=query,
            candidate_indices=union_indices,
            chunks=chunks,
            top_n=FINAL_K,
        )


        final_found_ids = set()

        top5_trace = []


        for result in reranked:

            chunk = result[
                "chunk"
            ]

            matched_ids = (
                find_matched_evidence(
                    chunk,
                    gold_evidence,
                )
            )

            final_found_ids.update(
                matched_ids
            )


            top5_trace.append(
                {
                    "rank":
                        result["rank"],

                    "chunk_id":
                        chunk["chunk_id"],

                    "source":
                        chunk["source"],

                    "rerank_score":
                        result[
                            "rerank_score"
                        ],

                    "matched_evidence_ids":
                        matched_ids,
                }
            )


        print(
            f"Top5 found: "
            f"{sorted(final_found_ids)}"
        )


        missing_after_rerank = (
            gold_ids
            - final_found_ids
        )


        if not missing_after_rerank:

            status = "COMPLETE"

        else:

            status = "STILL_MISSING"


        print(
            f"Status: {status}"
        )


        # ====================================================
        # Top5 明细
        # ====================================================

        for item in top5_trace:

            print(
                f"  #{item['rank']} "
                f"{item['chunk_id']} "
                f"score="
                f"{item['rerank_score']:.6f} "
                f"gold="
                f"{item['matched_evidence_ids']}"
            )


        results.append(
            {
                "id":
                    question_id,

                "question":
                    query,

                "union_size":
                    len(union_indices),

                "gold_evidence_ids":
                    sorted(gold_ids),

                "union_found_ids":
                    sorted(
                        union_found_ids
                    ),

                "final_found_ids":
                    sorted(
                        final_found_ids
                    ),

                "status":
                    status,

                "reranked_top5":
                    top5_trace,
            }
        )


    # --------------------------------------------------------
    # 5. Summary
    # --------------------------------------------------------

    complete_count = sum(
        1
        for result in results
        if result["status"]
        == "COMPLETE"
    )


    average_union_size = (
        sum(
            result["union_size"]
            for result in results
        )
        / len(results)
        if results
        else 0.0
    )


    summary = {
        "experiment":
            "E3-Raw-Union-Rerank-Probe",

        "question_count":
            len(results),

        "complete_count":
            complete_count,

        "still_missing_count":
            len(results)
            - complete_count,

        "average_union_size":
            average_union_size,
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
        f"Questions: "
        f"{len(results)}"
    )

    print(
        f"Complete: "
        f"{complete_count}"
    )

    print(
        f"Still missing: "
        f"{len(results) - complete_count}"
    )

    print(
        f"Average union size: "
        f"{average_union_size:.2f}"
    )

    print()
    print(
        f"结果已保存到: "
        f"{RUN_DIR}"
    )


if __name__ == "__main__":
    main()