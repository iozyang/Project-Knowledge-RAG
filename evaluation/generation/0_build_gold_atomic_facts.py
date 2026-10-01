import importlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

BENCHMARK_PATH = ROOT / "benchmark" / "benchmark_v1.jsonl"
OUTPUT_PATH = ROOT / "cache" / "gold_atomic_facts.jsonl"

judge = importlib.import_module("evaluation.generation.0_generation_judge")


def load_jsonl(path):
    rows = []

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))

    return rows


def load_finished_ids(path):
    if not path.exists():
        return set()

    ids = set()

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            if not line:
                continue

            try:
                row = json.loads(line)
                ids.add(row["id"])
            except (json.JSONDecodeError, KeyError):
                continue

    return ids


def append_jsonl(path, row):
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def main():
    benchmark = load_jsonl(BENCHMARK_PATH)

    answerable_rows = [
        row for row in benchmark
        if row.get("answerable") is True
    ]

    finished_ids = load_finished_ids(OUTPUT_PATH)

    print(f"Benchmark: {len(benchmark)}")
    print(f"Answerable: {len(answerable_rows)}")
    print(f"Already cached: {len(finished_ids)}")
    print()

    success = 0
    failed = 0

    for index, row in enumerate(answerable_rows, start=1):
        question_id = row["id"]

        if question_id in finished_ids:
            print(f"[{index}/{len(answerable_rows)}] {question_id} SKIP")
            continue

        gold_answer = row.get("gold_answer", "").strip()

        if not gold_answer:
            print(f"[{index}/{len(answerable_rows)}] {question_id} ERROR: gold_answer 为空")
            failed += 1
            continue

        print(f"[{index}/{len(answerable_rows)}] {question_id} splitting...")

        try:
            result = judge.extract_atomic_facts(gold_answer)

            facts = result["facts"]

            output = {
                "id": question_id,
                "question": row.get("question"),
                "question_type": row.get("question_type"),
                "difficulty": row.get("difficulty"),
                "hop_type": row.get("hop_type"),
                "gold_answer": gold_answer,
                "atomic_facts": facts,
                "fact_count": len(facts),
                "model": result["model"],
                "usage": result["usage"],
            }

            append_jsonl(OUTPUT_PATH, output)

            success += 1

            print(
                f"  OK facts={len(facts)} "
                f"tokens={result['usage']['total_tokens']}"
            )

        except Exception as e:
            failed += 1
            print(f"  ERROR: {e}")

    print()
    print("=" * 60)
    print(f"New success: {success}")
    print(f"Failed: {failed}")
    print(f"Output: {OUTPUT_PATH}")

    if OUTPUT_PATH.exists():
        cached = load_jsonl(OUTPUT_PATH)

        fact_counts = [
            row["fact_count"]
            for row in cached
        ]

        total_tokens = sum(
            row.get("usage", {}).get("total_tokens", 0) or 0
            for row in cached
        )

        print()
        print("Cache summary")
        print(f"Rows: {len(cached)}")

        if fact_counts:
            print(f"Facts total: {sum(fact_counts)}")
            print(f"Facts min: {min(fact_counts)}")
            print(f"Facts max: {max(fact_counts)}")
            print(f"Facts avg: {sum(fact_counts) / len(fact_counts):.2f}")

        print(f"Splitter total tokens: {total_tokens}")


if __name__ == "__main__":
    main()