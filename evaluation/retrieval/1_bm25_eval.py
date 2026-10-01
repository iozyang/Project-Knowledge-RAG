import importlib
import json
import re
from pathlib import Path

from rank_bm25 import BM25Okapi

# load_and_chunk_corpus = importlib.import_module(
#     "src.ingestion.1_fixed_chunker"
# ).load_and_chunk_corpus
load_and_chunk_corpus = importlib.import_module(
    "src.ingestion.2_recursive_chunker"
).load_and_chunk_corpus
tokenize = importlib.import_module(
    "src.retrieval.1_bm25_retriever"
).tokenize
evaluate_question = importlib.import_module(
    "evaluation.retrieval.0_metrics"
).evaluate_question


# 返回前 5 个结果
TOP_K = 5

# 获取项目根目录
PROJECT_ROOT = Path(__file__).resolve().parents[2]

BENCHMARK_PATH = (
    PROJECT_ROOT
    / "benchmark"
    / "benchmark_v1.jsonl"
)

# # Baseline 实验结果保存目录
# RUN_DIR = (
#     PROJECT_ROOT
#     / "evaluation"
#     / "runs"
#     / "retrieval"
#     / "e0_bm25_fixed500_o100"
# )

RUN_DIR = (
    PROJECT_ROOT
    / "evaluation"
    / "runs"
    / "retrieval"
    / "e0_bm25_recursive500_o100"
)


def load_benchmark():
    """读取 Benchmark，只保留 answerable=true 的题目。"""

    questions = []

    with BENCHMARK_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            item = json.loads(line)

            if item["answerable"]:
                questions.append(item)

    return questions


def normalize_text(text):
    """
    统一空格和换行，方便判断 Gold Evidence
    是否完整出现在 Chunk 中。
    """
    return re.sub(r"\s+", " ", text).strip()


def find_matched_evidence(chunk, gold_evidence):
    """
    判断当前 Chunk 命中了哪些 Gold Evidence。
    """

    matched_ids = []

    chunk_text = normalize_text(chunk["content"])
    chunk_file = Path(chunk["source"]).name

    for evidence in gold_evidence:
        # 必须来自同一篇文档
        if chunk_file != evidence["document"]:
            continue

        evidence_text = normalize_text(evidence["evidence"])

        # Gold Evidence 必须完整存在于 Chunk 中
        if evidence_text in chunk_text:
            matched_ids.append(evidence["evidence_id"])

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
    # 1. 加载 Corpus 并切片
    # =========================

    _, chunks = load_and_chunk_corpus()

    print(f"Chunks: {len(chunks)}")

    # =========================
    # 2. 建立 BM25
    # =========================

    tokenized_chunks = [
        tokenize(chunk["content"])
        for chunk in chunks
    ]

    bm25 = BM25Okapi(tokenized_chunks)

    # =========================
    # 3. 加载 45 条可回答问题
    # =========================

    questions = load_benchmark()

    print(f"Answerable Questions: {len(questions)}")

    # =========================
    # 4. 逐题检索
    # =========================

    traces = []

    for question in questions:
        query = question["question"]

        query_tokens = tokenize(query)

        scores = bm25.get_scores(query_tokens)

        top_indices = sorted(
            range(len(scores)),
            key=lambda i: scores[i],
            reverse=True,
        )[:TOP_K]

        retrieved = []
        matched_ids_by_rank = []

        for rank, index in enumerate(
            top_indices,
            start=1,
        ):
            chunk = chunks[index]

            matched_ids = find_matched_evidence(
                chunk,
                question["gold_evidence"],
            )

            matched_ids_by_rank.append(matched_ids)

            retrieved.append(
                {
                    "rank": rank,
                    "chunk_id": chunk["chunk_id"],
                    "source": chunk["source"],
                    "score": float(scores[index]),
                    "matched_evidence_ids": matched_ids,
                }
            )

        gold_evidence_ids = [
            evidence["evidence_id"]
            for evidence in question["gold_evidence"]
        ]

        metrics = evaluate_question(
            matched_ids_by_rank,
            gold_evidence_ids,
        )

        traces.append(
            {
                "id": question["id"],
                "question": query,
                "question_type": question["question_type"],
                "hop_type": question["hop_type"],
                "gold_evidence_ids": gold_evidence_ids,
                "retrieved": retrieved,
                **metrics,
            }
        )

    # =========================
    # 5. 分组汇总指标
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
        if trace["question_type"] == "cross_document"
    ]

    summary = {
        "experiment": "E0",
        "overall": summarize(traces),
        "single": summarize(single_traces),
        "multi": summarize(multi_traces),
        "cross_document": summarize(cross_document_traces),
    }

    # =========================
    # 6. 保存实验结果
    # =========================

    RUN_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    # config = {
    #     "experiment": "E0",
    #     "chunk_strategy": "fixed_size",
    #     "chunk_size": 500,
    #     "chunk_overlap": 100,
    #     "retriever": "BM25",
    #     "tokenizer": "jieba",
    #     "top_k": TOP_K,
    #     "corpus_version": "P1-10MD-v1",
    #     "benchmark_version": "v1",
    # }
    config = {
        "experiment": "E0",
        "chunk_strategy": "recursive_character",
        "chunk_size": 500,
        "chunk_overlap": 100,
        "retriever": "BM25",
        "tokenizer": "jieba",
        "top_k": TOP_K,
        "corpus_version": "P1-10MD-v1",
        "benchmark_version": "v1",
    }

    with (RUN_DIR / "config.json").open(
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            config,
            f,
            ensure_ascii=False,
            indent=2,
        )

    # 每道题详细 Trace
    with (RUN_DIR / "trace.jsonl").open(
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

    # 汇总成绩
    with (RUN_DIR / "summary.json").open(
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
    # 7. 打印成绩
    # =========================

    print()
    print("=" * 60)
    print("E0 Baseline Result")
    print("=" * 60)

    for group_name, group_result in summary.items():

        if group_name == "experiment":
            print(f"experiment: {group_result}")
            continue

        print()
        print(f"[{group_name.upper()}]")

        for metric_name, value in group_result.items():

            if isinstance(value, float):
                print(f"{metric_name}: {value:.4f}")
            else:
                print(f"{metric_name}: {value}")

    print()
    print(f"结果已保存到: {RUN_DIR}")


if __name__ == "__main__":
    main()