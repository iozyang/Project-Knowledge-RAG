import importlib
import json
import re
from pathlib import Path

import numpy as np


# ============================================================
# 导入已有模块
# ============================================================

bm25_module = importlib.import_module(
    "src.retrieval.1_bm25_retriever"
)
tokenize = bm25_module.tokenize


dense_module = importlib.import_module(
    "src.retrieval.2_dense_retriever"
)
embed = dense_module.embed
cosine_similarity = dense_module.cosine_similarity


hybrid_module = importlib.import_module(
    "src.retrieval.3_hybrid_retriever"
)
build_bm25 = hybrid_module.build_bm25
reciprocal_rank_fusion = hybrid_module.reciprocal_rank_fusion


chunker_module = importlib.import_module(
    "src.ingestion.2_recursive_chunker"
)
load_and_chunk_corpus = chunker_module.load_and_chunk_corpus


# ============================================================
# 配置
# ============================================================

TOP_K = 20
RRF_K = 60

PROJECT_ROOT = Path(__file__).resolve().parents[2]

BENCHMARK_PATH = (
    PROJECT_ROOT
    / "benchmark"
    / "benchmark_v1.jsonl"
)

RUN_DIR = (
    PROJECT_ROOT
    / "evaluation"
    / "runs"
    / "retrieval"
    / "e2_top20recall_check"
)


# ============================================================
# Benchmark
# ============================================================

def load_benchmark():
    questions = []

    with BENCHMARK_PATH.open(
        "r",
        encoding="utf-8",
    ) as f:

        for line in f:
            item = json.loads(line)

            if item["answerable"]:
                questions.append(item)

    return questions


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
# Candidate Evaluation
# ============================================================

def evaluate_candidates(
    indices,
    chunks,
    gold_evidence,
):
    """
    单个问题：

    hit:
        至少命中 1 条 Gold Evidence -> 1
        否则 -> 0

    recall:
        当前 Top20 覆盖的 Gold Evidence 比例
    """

    gold_ids = {
        evidence["evidence_id"]
        for evidence in gold_evidence
    }

    matched_ids = set()

    for index in indices:

        chunk = chunks[int(index)]

        matched_ids.update(
            find_matched_evidence(
                chunk,
                gold_evidence,
            )
        )

    hit = 1 if matched_ids else 0

    recall = (
        len(matched_ids) / len(gold_ids)
        if gold_ids
        else 0.0
    )

    return {
        "hit": hit,
        "recall": recall,
        "matched_evidence_ids":
            sorted(matched_ids),
    }


# ============================================================
# Summary
# ============================================================

def summarize(traces):

    count = len(traces)

    if count == 0:
        return {}

    strategies = [
        "bm25_only_top20",
        "dense_only_top20",
        "rrf_top20",
    ]

    result = {
        "question_count": count
    }

    for strategy in strategies:

        result[strategy] = {

            "hit_rate": sum(
                trace[strategy]["hit"]
                for trace in traces
            ) / count,

            "recall": sum(
                trace[strategy]["recall"]
                for trace in traces
            ) / count,
        }

    return result


# ============================================================
# Main
# ============================================================

def main():

    # --------------------------------------------------------
    # 1. Corpus
    # --------------------------------------------------------

    _, chunks = load_and_chunk_corpus()

    print(
        f"Chunks: {len(chunks)}"
    )


    # --------------------------------------------------------
    # 2. BM25
    # --------------------------------------------------------

    print(
        "Building BM25 index..."
    )

    bm25 = build_bm25(chunks)


    # --------------------------------------------------------
    # 3. Dense Chunk Embedding
    # --------------------------------------------------------

    print(
        "Embedding chunks..."
    )

    texts = [
        chunk["content"]
        for chunk in chunks
    ]

    chunk_vectors = embed(texts)

    print(
        f"Chunk vectors: "
        f"{len(chunk_vectors)}"
    )


    # --------------------------------------------------------
    # 4. Benchmark
    # --------------------------------------------------------

    questions = load_benchmark()

    print(
        f"Answerable Questions: "
        f"{len(questions)}"
    )


    # --------------------------------------------------------
    # 5. Top20 Recall Check
    # --------------------------------------------------------

    traces = []

    for number, question in enumerate(
        questions,
        start=1,
    ):

        query = question["question"]

        print(
            f"[{number}/{len(questions)}] "
            f"{question['id']}"
        )


        # ====================================================
        # BM25-only Top20
        # ====================================================

        bm25_scores = bm25.get_scores(
            tokenize(query)
        )

        bm25_indices = np.argsort(
            bm25_scores
        )[::-1][:TOP_K]


        # ====================================================
        # Dense-only Top20
        # ====================================================

        query_vector = embed(
            [query]
        )[0]

        dense_scores = cosine_similarity(
            query_vector,
            chunk_vectors,
        )

        dense_indices = np.argsort(
            dense_scores
        )[::-1][:TOP_K]


        # ====================================================
        # RRF Top20
        #
        # BM25 Top20 + Dense Top20
        # -> RRF
        # -> Top20
        # ====================================================

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

        rrf_indices = [
            int(chunk_index)
            for chunk_index, _
            in ranked[:TOP_K]
        ]


        # ====================================================
        # 评测
        # ====================================================

        bm25_result = evaluate_candidates(
            bm25_indices,
            chunks,
            question["gold_evidence"],
        )

        dense_result = evaluate_candidates(
            dense_indices,
            chunks,
            question["gold_evidence"],
        )

        rrf_result = evaluate_candidates(
            rrf_indices,
            chunks,
            question["gold_evidence"],
        )


        # ====================================================
        # Trace
        # ====================================================

        traces.append(
            {
                "id":
                    question["id"],

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

                "bm25_only_top20": {
                    **bm25_result,

                    "chunk_ids": [
                        chunks[int(i)]["chunk_id"]
                        for i in bm25_indices
                    ],
                },

                "dense_only_top20": {
                    **dense_result,

                    "chunk_ids": [
                        chunks[int(i)]["chunk_id"]
                        for i in dense_indices
                    ],
                },

                "rrf_top20": {
                    **rrf_result,

                    "chunk_ids": [
                        chunks[int(i)]["chunk_id"]
                        for i in rrf_indices
                    ],
                },
            }
        )


    # --------------------------------------------------------
    # 6. 分组
    # --------------------------------------------------------

    single_traces = [
        trace
        for trace in traces
        if trace["hop_type"] == "single"
    ]

    multi_traces = [
        trace
        for trace in traces
        if trace["hop_type"] == "multi"
    ]

    cross_document_traces = [
        trace
        for trace in traces
        if trace["question_type"]
        == "cross_document"
    ]


    # --------------------------------------------------------
    # 7. Summary
    # --------------------------------------------------------

    summary = {
        "experiment":
            "E2-Top20-Recall-Check",

        "top_k":
            TOP_K,

        "rrf_k":
            RRF_K,

        "comparison": [
            "bm25_only_top20",
            "dense_only_top20",
            "rrf_top20",
        ],

        "overall":
            summarize(traces),

        "single":
            summarize(single_traces),

        "multi":
            summarize(multi_traces),

        "cross_document":
            summarize(
                cross_document_traces
            ),
    }


    # --------------------------------------------------------
    # 8. 保存
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
    # 9. 输出
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print(
        "E2 Top20 Recall Check"
    )
    print("=" * 70)

    for group_name in [
        "overall",
        "single",
        "multi",
        "cross_document",
    ]:

        group = summary[group_name]

        print()
        print(
            f"[{group_name.upper()}]"
        )

        print(
            f"Questions: "
            f"{group['question_count']}"
        )

        for strategy in [
            "bm25_only_top20",
            "dense_only_top20",
            "rrf_top20",
        ]:

            print()
            print(
                f"{strategy}:"
            )

            print(
                f"  Hit Rate: "
                f"{group[strategy]['hit_rate']:.4f}"
            )

            print(
                f"  Recall: "
                f"{group[strategy]['recall']:.4f}"
            )

    print()

    print(
        f"结果已保存到: "
        f"{RUN_DIR}"
    )


if __name__ == "__main__":
    main()