import importlib
import json
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

CONTEXTS_PATH = ROOT / "cache" / "generation_contexts.jsonl"

RUN_DIR = (
    ROOT
    / "evaluation"
    / "runs"
    / "generation"
    / "e1_generation_baseline"
)

OUTPUT_PATH = RUN_DIR / "outputs.jsonl"
SUMMARY_PATH = RUN_DIR / "generation_summary.json"

generator = importlib.import_module(
    "src.generation.1_generator"
)


def load_jsonl(path):
    rows = []

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            if line:
                rows.append(json.loads(line))

    return rows


def append_jsonl(path, row):
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with path.open("a", encoding="utf-8") as f:
        f.write(
            json.dumps(
                row,
                ensure_ascii=False,
            )
            + "\n"
        )


def save_json(path, data):
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with path.open("w", encoding="utf-8") as f:
        json.dump(
            data,
            f,
            ensure_ascii=False,
            indent=2,
        )


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

            except (
                json.JSONDecodeError,
                KeyError,
            ):
                continue

    return ids


def main():
    contexts = load_jsonl(
        CONTEXTS_PATH
    )

    finished_ids = load_finished_ids(
        OUTPUT_PATH
    )

    print(
        f"Generator: "
        f"{generator.GENERATOR_MODEL}"
    )

    print(
        f"Questions: "
        f"{len(contexts)}"
    )

    print(
        f"Already generated: "
        f"{len(finished_ids)}"
    )

    print()

    run_start = time.perf_counter()

    success = 0
    failed = 0

    for index, row in enumerate(
        contexts,
        start=1,
    ):
        question_id = row["id"]

        if question_id in finished_ids:
            print(
                f"[{index}/{len(contexts)}] "
                f"{question_id} SKIP"
            )

            continue

        print(
            f"[{index}/{len(contexts)}] "
            f"{question_id} generating..."
        )

        try:
            result = generator.generate_answer(
                question=row["question"],
                contexts=row.get(
                    "contexts",
                    [],
                ),
            )

            output = {
                "id": question_id,
                "question": row["question"],
                "question_type": row.get(
                    "question_type"
                ),
                "difficulty": row.get(
                    "difficulty"
                ),
                "answerable": row.get(
                    "answerable"
                ),
                "hop_type": row.get(
                    "hop_type"
                ),
                "context_count": len(
                    row.get(
                        "contexts",
                        [],
                    )
                ),
                **result,
            }

            append_jsonl(
                OUTPUT_PATH,
                output,
            )

            success += 1

            print(
                f"  OK "
                f"parse={result['parse_success']} "
                f"latency={result['latency_ms']}ms "
                f"tokens={result['total_tokens']}"
            )

        except Exception as e:
            failed += 1

            print(
                f"  ERROR: {e}"
            )

    wall_time = (
        time.perf_counter()
        - run_start
    )

    outputs = load_jsonl(
        OUTPUT_PATH
    )

    total_tokens = sum(
        row.get(
            "total_tokens",
            0,
        )
        or 0
        for row in outputs
    )

    total_input_tokens = sum(
        row.get(
            "input_tokens",
            0,
        )
        or 0
        for row in outputs
    )

    total_output_tokens = sum(
        row.get(
            "output_tokens",
            0,
        )
        or 0
        for row in outputs
    )

    summary = {
        "experiment": (
            "e1_g0_naive_baseline"
        ),

        "generator_model": (
            generator.GENERATOR_MODEL
        ),

        "prompt": "G0_naive",

        "questions": len(contexts),

        "generated": len(outputs),

        "complete": (
            len(outputs)
            == len(contexts)
        ),

        "current_run": {
            "success": success,
            "failed": failed,
            "wall_time_sec": wall_time,
            "avg_wall_time_per_question_sec": (
                wall_time / success
                if success else None
            ),
            "throughput_questions_per_min": (
                success / wall_time * 60
                if success
                and wall_time > 0
                else None
            ),
        },

        "tokens": {
            "input": total_input_tokens,
            "output": total_output_tokens,
            "total": total_tokens,
        },
    }

    save_json(
        SUMMARY_PATH,
        summary,
    )

    print()
    print("=" * 60)

    print(
        f"Success: {success}"
    )

    print(
        f"Failed: {failed}"
    )

    print(
        f"Generated: "
        f"{len(outputs)}/{len(contexts)}"
    )

    print(
        f"Wall Time: "
        f"{wall_time:.2f}s"
    )

    if success:
        print(
            f"Avg / Question: "
            f"{wall_time / success:.2f}s"
        )

    print(
        f"Total Tokens: "
        f"{total_tokens}"
    )

    print(
        f"Output: "
        f"{OUTPUT_PATH}"
    )


if __name__ == "__main__":
    main()