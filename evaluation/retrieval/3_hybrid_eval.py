import importlib
import json
import re
from pathlib import Path


# ============================================================
# 导入已有模块
# ============================================================

hybrid_module = importlib.import_module(
    "src.retrieval.3_hybrid_retriever"
)

load_and_chunk_corpus = hybrid_module.load_and_chunk_corpus
build_bm25 = hybrid_module.build_bm25
embed = hybrid_module.embed
hybrid_search = hybrid_module.hybrid_search


metrics_module = importlib.import_module(
    "evaluation.retrieval.0_metrics"
)

evaluate_question = metrics_module.evaluate_question


# ============================================================
# 实验配置
# ============================================================

CANDIDATE_K = 20
FINAL_K = 5
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
    / "e2_hybrid_rrf_recursive500_o100"
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
# Summary
# ============================================================

def summarize(traces):
    count = len(traces)

    if count == 0:
        return {}

    metric_names = [
        "hit_at_1",
        "hit_at_3",
        "hit_at_5",
        "recall_at_1",
        "recall_at_3",
        "recall_at_5",
        "rr_at_5",
    ]

    result = {
        "question_count": count
    }

    for metric in metric_names:

        average = sum(
            trace[metric]
            for trace in traces
        ) / count

        if metric == "rr_at_5":
            result["mrr_at_5"] = average
        else:
            result[metric] = average

    return result


# ============================================================
# Main
# ============================================================

def main():

    # --------------------------------------------------------
    # 1. Corpus
    # --------------------------------------------------------

    _, chunks = load_and_chunk_corpus()

    print(f"Chunks: {len(chunks)}")


    # --------------------------------------------------------
    # 2. BM25 Index
    # --------------------------------------------------------

    print("Building BM25 index...")

    bm25 = build_bm25(chunks)


    # --------------------------------------------------------
    # 3. Chunk Embeddings
    # --------------------------------------------------------

    print("Embedding chunks...")

    texts = [
        chunk["content"]
        for chunk in chunks
    ]

    chunk_vectors = embed(texts)

    print(
        f"Chunk vectors: {len(chunk_vectors)}"
    )


    # --------------------------------------------------------
    # 4. Benchmark
    # --------------------------------------------------------

    questions = load_benchmark()

    print(
        f"Answerable Questions: {len(questions)}"
    )


    # --------------------------------------------------------
    # 5. Hybrid Retrieval
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

        results = hybrid_search(
            query=query,
            chunks=chunks,
            bm25=bm25,
            chunk_vectors=chunk_vectors,
            candidate_k=CANDIDATE_K,
            final_k=FINAL_K,
        )

        retrieved = []
        matched_ids_by_rank = []

        for result in results:

            chunk = result["chunk"]

            matched_ids = (
                find_matched_evidence(
                    chunk,
                    question["gold_evidence"],
                )
            )

            matched_ids_by_rank.append(
                matched_ids
            )

            retrieved.append(
                {
                    "rank":
                        result["rank"],

                    "chunk_id":
                        chunk["chunk_id"],

                    "source":
                        chunk["source"],

                    "rrf_score":
                        result["rrf_score"],

                    "bm25_rank":
                        result["bm25_rank"],

                    "dense_rank":
                        result["dense_rank"],

                    "bm25_score":
                        result["bm25_score"],

                    "dense_score":
                        result["dense_score"],

                    "matched_evidence_ids":
                        matched_ids,
                }
            )


        gold_evidence_ids = [
            evidence["evidence_id"]
            for evidence
            in question["gold_evidence"]
        ]

        metrics = evaluate_question(
            matched_ids_by_rank,
            gold_evidence_ids,
        )

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

                "gold_evidence_ids":
                    gold_evidence_ids,

                "retrieved":
                    retrieved,

                **metrics,
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
            "E2-Hybrid-RRF-Recursive500-O100",

        "overall":
            summarize(traces),

        "single":
            summarize(single_traces),

        "multi":
            summarize(multi_traces),

        "cross_document":
            summarize(cross_document_traces),
    }


    # --------------------------------------------------------
    # 8. 保存
    # --------------------------------------------------------

    RUN_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    config = {
        "experiment":
            "E2",

        "chunk_strategy":
            "recursive_character",

        "chunk_size":
            500,

        "chunk_overlap":
            100,

        "retriever":
            "hybrid_rrf",

        "bm25":
            True,

        "dense_embedding_model":
            "qwen3.7-text-embedding",

        "embedding_dimensions":
            1024,

        "candidate_k_per_retriever":
            CANDIDATE_K,

        "rrf_k":
            RRF_K,

        "final_top_k":
            FINAL_K,

        "corpus_version":
            "P1-10MD-v1",

        "benchmark_version":
            "v1",
    }


    # config.json

    with (
        RUN_DIR / "config.json"
    ).open(
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            config,
            f,
            ensure_ascii=False,
            indent=2,
        )


    # trace.jsonl

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


    # summary.json

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
    print("=" * 60)
    print("E2 Hybrid Retrieval Result")
    print("=" * 60)

    for group_name, group_result \
            in summary.items():

        if group_name == "experiment":

            print(
                f"experiment: "
                f"{group_result}"
            )

            continue

        print()
        print(
            f"[{group_name.upper()}]"
        )

        for metric_name, value \
                in group_result.items():

            if isinstance(value, float):

                print(
                    f"{metric_name}: "
                    f"{value:.4f}"
                )

            else:

                print(
                    f"{metric_name}: "
                    f"{value}"
                )

    print()

    print(
        f"结果已保存到: {RUN_DIR}"
    )


if __name__ == "__main__":
    main()