import importlib
import json
import re
from pathlib import Path

import numpy as np

evaluate_question = importlib.import_module(
    "evaluation.retrieval.0_metrics"
).evaluate_question


# =========================
# 导入 Dense Retriever
# =========================

# 文件名以数字开头，不能普通 import
dense_module = importlib.import_module(
    "src.retrieval.2_dense_retriever"
)

embed = dense_module.embed
cosine_similarity = dense_module.cosine_similarity
load_and_chunk_corpus = dense_module.load_and_chunk_corpus


# =========================
# 实验配置
# =========================

TOP_K = 5

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
    / "e1_dense_qwen_recursive500_o100"
)


def load_benchmark():
    """
    读取 Benchmark，
    只保留 answerable=true 的 45 道题。
    """

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


def normalize_text(text):
    """
    统一空格和换行。
    """

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
    判断当前 Chunk 命中了哪些 Gold Evidence。
    """

    matched_ids = []

    chunk_text = normalize_text(
        chunk["content"]
    )

    chunk_file = Path(
        chunk["source"]
    ).name

    for evidence in gold_evidence:

        # 必须来自同一篇文档
        if chunk_file != evidence["document"]:
            continue

        evidence_text = normalize_text(
            evidence["evidence"]
        )

        # Gold Evidence 完整存在于 Chunk 中
        if evidence_text in chunk_text:

            matched_ids.append(
                evidence["evidence_id"]
            )

    return matched_ids


def summarize(traces):
    """
    对一组题目的 Retrieval 指标求平均。
    """

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


def main():

    # =========================
    # 1. 加载并切片 Corpus
    # =========================

    _, chunks = load_and_chunk_corpus()

    print(f"Chunks: {len(chunks)}")

    texts = [
        chunk["content"]
        for chunk in chunks
    ]

    # =========================
    # 2. 所有 Chunk 只向量化一次
    # =========================

    print("Embedding chunks...")

    chunk_vectors = embed(texts)

    print(
        f"Chunk vectors: {len(chunk_vectors)}"
    )

    # =========================
    # 3. 加载 45 道 Benchmark
    # =========================

    questions = load_benchmark()

    print(
        f"Answerable Questions: {len(questions)}"
    )

    # =========================
    # 4. 逐题 Dense Retrieval
    # =========================

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

        # Query embedding
        query_vector = embed([query])[0]

        # 与所有 Chunk 做 cosine similarity
        scores = cosine_similarity(
            query_vector,
            chunk_vectors,
        )

        # Top-5
        top_indices = np.argsort(
            scores
        )[::-1][:TOP_K]

        retrieved = []
        matched_ids_by_rank = []

        for rank, index in enumerate(
            top_indices,
            start=1,
        ):

            chunk = chunks[index]

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
                    "rank": rank,
                    "chunk_id": chunk["chunk_id"],
                    "source": chunk["source"],
                    "score": float(
                        scores[index]
                    ),
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
                "id": question["id"],
                "question": query,
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

    # =========================
    # 5. 分组统计
    # =========================

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

    summary = {
        "experiment":
            "E1-Dense-Qwen-Recursive500-O100",

        "overall":
            summarize(traces),

        "single":
            summarize(single_traces),

        "multi":
            summarize(multi_traces),

        "cross_document":
            summarize(cross_document_traces),
    }

    # =========================
    # 6. 保存结果
    # =========================

    RUN_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    config = {
        "experiment": "E1",
        "chunk_strategy":
            "recursive_character",
        "chunk_size": 500,
        "chunk_overlap": 100,

        "retriever": "dense",

        "embedding_model":
            "qwen3.7-text-embedding",

        "embedding_dimensions":
            1024,

        "similarity":
            "cosine",

        "top_k": TOP_K,

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

    # =========================
    # 7. 打印结果
    # =========================

    print()
    print("=" * 60)
    print("E1 Dense Retrieval Result")
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