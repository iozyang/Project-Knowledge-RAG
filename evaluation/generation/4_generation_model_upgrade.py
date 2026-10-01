import asyncio
import importlib
import json
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

CONTEXTS_PATH = (
    ROOT
    / "cache"
    / "generation_contexts.jsonl"
)

RUN_DIR = (
    ROOT
    / "evaluation"
    / "runs"
    / "generation"
    / "e4_generator_qwen38_flash"
)

OUTPUT_PATH = (
    RUN_DIR
    / "outputs.jsonl"
)

SUMMARY_PATH = (
    RUN_DIR
    / "generation_summary.json"
)

MAX_CONCURRENCY = 3


generator = importlib.import_module(
    "src.generation.4_qwen_flash_generator"
)


# ============================================================
# IO
# ============================================================

def load_jsonl(path):
    with path.open(
        "r",
        encoding="utf-8",
    ) as f:
        return [
            json.loads(line)
            for line in f
            if line.strip()
        ]


def save_jsonl(
    path,
    rows,
):
    with path.open(
        "w",
        encoding="utf-8",
    ) as f:
        for row in rows:
            f.write(
                json.dumps(
                    row,
                    ensure_ascii=False,
                )
                + "\n"
            )


def save_json(
    path,
    data,
):
    with path.open(
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            data,
            f,
            ensure_ascii=False,
            indent=2,
        )


# ============================================================
# 单题 Generation
# ============================================================

async def generate_one(
    row,
    semaphore,
):
    async with semaphore:
        result = (
            await generator.generate_answer(
                question=row["question"],
                contexts=row.get(
                    "contexts",
                    [],
                ),
            )
        )

        return {
            "id": row["id"],

            "question": (
                row["question"]
            ),

            "question_type": (
                row.get(
                    "question_type"
                )
            ),

            "difficulty": (
                row.get(
                    "difficulty"
                )
            ),

            "answerable": (
                row.get(
                    "answerable"
                )
            ),

            "hop_type": (
                row.get(
                    "hop_type"
                )
            ),

            "context_count": len(
                row.get(
                    "contexts",
                    [],
                )
            ),

            **result,
        }


# ============================================================
# Main
# ============================================================

async def main():
    RUN_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    contexts = load_jsonl(
        CONTEXTS_PATH
    )

    semaphore = asyncio.Semaphore(
        MAX_CONCURRENCY
    )

    print(
        "Experiment: "
        "e4_generator_qwen38_flash"
    )

    print(
        f"Generator: "
        f"{generator.GENERATOR_MODEL}"
    )

    print(
        "Prompt: "
        "G1.1_grounded"
    )

    print(
        f"Questions: "
        f"{len(contexts)}"
    )

    print(
        f"Concurrency: "
        f"{MAX_CONCURRENCY}"
    )

    print()

    start = time.perf_counter()

    tasks = [
        asyncio.create_task(
            generate_one(
                row,
                semaphore,
            )
        )
        for row in contexts
    ]

    outputs = []

    for i, task in enumerate(
        asyncio.as_completed(tasks),
        start=1,
    ):
        result = await task

        outputs.append(
            result
        )

        print(
            f"[{i}/{len(contexts)}] "
            f"{result['id']} OK "
            f"parse={result['parse_success']} "
            f"latency={result['latency_ms']}ms "
            f"tokens={result['total_tokens']}"
        )

    wall_time = (
        time.perf_counter()
        - start
    )

    outputs.sort(
        key=lambda row: row["id"]
    )

    save_jsonl(
        OUTPUT_PATH,
        outputs,
    )


    # ========================================================
    # Token 统计
    # ========================================================

    input_tokens = sum(
        row.get(
            "input_tokens",
            0,
        )
        or 0
        for row in outputs
    )

    output_tokens = sum(
        row.get(
            "output_tokens",
            0,
        )
        or 0
        for row in outputs
    )

    total_tokens = sum(
        row.get(
            "total_tokens",
            0,
        )
        or 0
        for row in outputs
    )


    # ========================================================
    # Summary
    # ========================================================

    summary = {
        "experiment": (
            "e4_generator_qwen38_flash"
        ),

        "generator_model": (
            generator.GENERATOR_MODEL
        ),

        "prompt": (
            "G1.1_grounded"
        ),

        "questions": (
            len(contexts)
        ),

        "generated": (
            len(outputs)
        ),

        "complete": (
            len(outputs)
            == len(contexts)
        ),

        "current_run": {
            "success": (
                len(outputs)
            ),

            "failed": (
                len(contexts)
                - len(outputs)
            ),

            "wall_time_sec": (
                wall_time
            ),

            "avg_wall_time_per_question_sec": (
                wall_time
                / len(outputs)
                if outputs
                else None
            ),

            "throughput_questions_per_min": (
                len(outputs)
                / wall_time
                * 60
                if outputs
                and wall_time > 0
                else None
            ),
        },

        "tokens": {
            "input": input_tokens,
            "output": output_tokens,
            "total": total_tokens,
        },
    }

    save_json(
        SUMMARY_PATH,
        summary,
    )


    # ========================================================
    # Console
    # ========================================================

    print()
    print("=" * 60)

    print(
        f"Wall Time: "
        f"{wall_time:.2f}s"
    )

    print(
        f"Avg / Question: "
        f"{wall_time / len(contexts):.2f}s"
    )

    print(
        f"Throughput: "
        f"{len(contexts) / wall_time * 60:.2f} "
        f"questions/min"
    )

    print()

    print("Tokens")

    print(
        f"  Input:  "
        f"{input_tokens}"
    )

    print(
        f"  Output: "
        f"{output_tokens}"
    )

    print(
        f"  Total:  "
        f"{total_tokens}"
    )

    print()

    print(
        f"Output: "
        f"{OUTPUT_PATH}"
    )

    print(
        f"Summary: "
        f"{SUMMARY_PATH}"
    )

    await generator.client.close()


if __name__ == "__main__":
    asyncio.run(main())