import importlib
import json
import re
from pathlib import Path

# load_and_chunk_corpus = importlib.import_module(
#     "src.ingestion.2_recursive_chunker"
# ).load_and_chunk_corpus

# load_and_chunk_corpus = importlib.import_module(
#     "src.ingestion.1_fixed_chunker"
# ).load_and_chunk_corpus

load_and_chunk_corpus = importlib.import_module(
    "src.ingestion.3_heading_recursive_chunker"
).load_and_chunk_corpus


PROJECT_ROOT = Path(__file__).resolve().parents[2]

BENCHMARK_PATH = (
    PROJECT_ROOT
    / "benchmark"
    / "benchmark_v1.jsonl"
)


def normalize_text(text):
    """统一连续空白、换行。"""
    return re.sub(r"\s+", " ", text).strip()


def load_gold_evidence():
    """
    读取所有 answerable 问题中的 Gold Evidence。
    """

    evidence_list = []

    with BENCHMARK_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            question = json.loads(line)

            if not question["answerable"]:
                continue

            for evidence in question["gold_evidence"]:
                evidence_list.append(
                    {
                        "question_id": question["id"],
                        "evidence_id": evidence["evidence_id"],
                        "document": evidence["document"],
                        "section": evidence["section"],
                        "evidence": evidence["evidence"],
                    }
                )

    return evidence_list


def main():
    _, chunks = load_and_chunk_corpus()
    gold_evidence = load_gold_evidence()

    covered = []
    uncovered = []

    for evidence in gold_evidence:

        gold_text = normalize_text(
            evidence["evidence"]
        )

        found = False

        for chunk in chunks:

            # 必须是同一篇文档
            if Path(chunk["source"]).name != evidence["document"]:
                continue

            chunk_text = normalize_text(
                chunk["content"]
            )

            # Gold Evidence 完整包含在这个 Chunk 中
            if gold_text in chunk_text:
                found = True
                break

        if found:
            covered.append(evidence)
        else:
            uncovered.append(evidence)

    total = len(gold_evidence)

    coverage = len(covered) / total

    print("=" * 60)
    print("Gold Evidence Chunk Coverage")
    print("=" * 60)

    print(f"Gold Evidence 总数: {total}")
    print(f"完整覆盖: {len(covered)}")
    print(f"未完整覆盖: {len(uncovered)}")
    print(f"Coverage: {coverage:.2%}")

    print()

    if uncovered:
        print("=" * 60)
        print("未被任何 Chunk 完整覆盖的 Evidence")
        print("=" * 60)

        for evidence in uncovered:
            print()
            print("question_id:", evidence["question_id"])
            print("evidence_id:", evidence["evidence_id"])
            print("document:", evidence["document"])
            print("section:", evidence["section"])
            print(
                "evidence_length:",
                len(evidence["evidence"])
            )
            print("evidence:")
            print(evidence["evidence"])
            print("-" * 60)


if __name__ == "__main__":
    main()