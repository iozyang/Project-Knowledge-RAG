# python -m src.retrieval_cache
# 缓存检索侧的 Embedding 结果

import importlib
import json
from pathlib import Path

import numpy as np


# ============================================================
# 导入已有模块
# ============================================================

chunker_module = importlib.import_module(
    "src.ingestion.2_recursive_chunker"
)

load_and_chunk_corpus = (
    chunker_module.load_and_chunk_corpus
)


dense_module = importlib.import_module(
    "src.retrieval.2_dense_retriever"
)

embed = dense_module.embed


# ============================================================
# 路径
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

CACHE_DIR = PROJECT_ROOT / "cache"

CORPUS_CHUNKS_PATH = (
    CACHE_DIR / "corpus_chunks.jsonl"
)

CORPUS_EMBEDDINGS_PATH = (
    CACHE_DIR / "corpus_embeddings.npy"
)

BENCHMARK_EMBEDDINGS_PATH = (
    CACHE_DIR / "benchmark_embeddings.npz"
)

BENCHMARK_PATH = (
    PROJECT_ROOT
    / "benchmark"
    / "benchmark_v1.jsonl"
)


# ============================================================
# Benchmark
# ============================================================

def load_answerable_benchmark():
    """
    只读取 answerable=true 的 Benchmark。
    当前应为 45 道题。
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


# ============================================================
# 1. Corpus Chunks Cache
# ============================================================

def load_or_create_chunks():
    """
    缓存递归切片结果。

    HIT:
        直接读取 corpus_chunks.jsonl

    MISS:
        调用 Recursive Chunker
        然后保存
    """

    CACHE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    # --------------------------------------------------------
    # Cache HIT
    # --------------------------------------------------------

    if (
        CORPUS_CHUNKS_PATH.exists()
        and CORPUS_CHUNKS_PATH.stat().st_size > 0
    ):
        chunks = []

        with CORPUS_CHUNKS_PATH.open(
            "r",
            encoding="utf-8",
        ) as f:

            for line in f:

                if line.strip():
                    chunks.append(
                        json.loads(line)
                    )

        if chunks:

            print(
                f"[CACHE HIT] corpus chunks: "
                f"{len(chunks)}"
            )

            return chunks

        print(
            "[CACHE INVALID] corpus chunks is empty"
        )


    # --------------------------------------------------------
    # Cache MISS
    # --------------------------------------------------------

    print(
        "[CACHE MISS] corpus chunks"
    )

    print(
        "Running recursive chunking..."
    )

    _, chunks = load_and_chunk_corpus()


    # --------------------------------------------------------
    # 保存
    # --------------------------------------------------------

    with CORPUS_CHUNKS_PATH.open(
        "w",
        encoding="utf-8",
    ) as f:

        for chunk in chunks:

            f.write(
                json.dumps(
                    chunk,
                    ensure_ascii=False,
                    default=str,
                )
                + "\n"
            )


    print(
        f"[CACHE SAVE] corpus chunks: "
        f"{len(chunks)}"
    )

    return chunks


# ============================================================
# 2. Corpus Embeddings Cache
# ============================================================

def load_or_create_corpus_embeddings(
    chunks=None,
):
    """
    缓存全部 Corpus Chunk Embeddings。

    embeddings[i]
    必须对应
    chunks[i]
    """

    CACHE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )


    if chunks is None:
        chunks = load_or_create_chunks()


    # --------------------------------------------------------
    # Cache HIT
    # --------------------------------------------------------

    if (
        CORPUS_EMBEDDINGS_PATH.exists()
        and CORPUS_EMBEDDINGS_PATH.stat().st_size > 0
    ):

        try:

            embeddings = np.load(
                CORPUS_EMBEDDINGS_PATH
            )

            if len(embeddings) == len(chunks):

                print(
                    f"[CACHE HIT] corpus embeddings: "
                    f"{embeddings.shape}"
                )

                return embeddings

            print(
                "[CACHE INVALID] "
                "embedding 数量和 chunk 数量不一致"
            )

        except (
            EOFError,
            ValueError,
            OSError,
        ):

            print(
                "[CACHE INVALID] "
                "corpus embeddings file is corrupted"
            )

    else:

        print(
            "[CACHE MISS] corpus embeddings"
        )


    # --------------------------------------------------------
    # Cache MISS：文件不存在、损坏，或和当前 chunks 对不上
    # --------------------------------------------------------

    texts = [
        chunk["content"]
        for chunk in chunks
    ]

    print(
        f"Embedding {len(texts)} chunks..."
    )

    embeddings = embed(texts)

    embeddings = np.asarray(
        embeddings,
        dtype=np.float32,
    )


    # --------------------------------------------------------
    # 保存
    # --------------------------------------------------------

    np.save(
        CORPUS_EMBEDDINGS_PATH,
        embeddings,
    )

    print(
        f"[CACHE SAVE] corpus embeddings: "
        f"{embeddings.shape}"
    )

    return embeddings


# ============================================================
# 3. Benchmark Embeddings Cache
# ============================================================

def load_or_create_benchmark_embeddings(
    questions=None,
):
    """
    缓存 45 道 answerable Benchmark Query Embeddings。

    返回：

        question_ids
        embeddings

    question_ids[i]
    对应
    embeddings[i]
    """

    CACHE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )


    if questions is None:

        questions = (
            load_answerable_benchmark()
        )


    current_ids = [
        question["id"]
        for question in questions
    ]


    # --------------------------------------------------------
    # Cache HIT
    # --------------------------------------------------------

    if (
        BENCHMARK_EMBEDDINGS_PATH.exists()
        and BENCHMARK_EMBEDDINGS_PATH.stat().st_size > 0
    ):

        try:

            data = np.load(
                BENCHMARK_EMBEDDINGS_PATH
            )

            cached_ids = (
                data["question_ids"]
                .astype(str)
                .tolist()
            )

            embeddings = data[
                "embeddings"
            ]

            if cached_ids == current_ids:

                print(
                    f"[CACHE HIT] "
                    f"benchmark embeddings: "
                    f"{embeddings.shape}"
                )

                return (
                    cached_ids,
                    embeddings,
                )

            print(
                "[CACHE INVALID] "
                "Benchmark IDs 已变化"
            )

        except (
            EOFError,
            ValueError,
            OSError,
        ):

            print(
                "[CACHE INVALID] "
                "benchmark embeddings file is corrupted"
            )

    else:

        print(
            "[CACHE MISS] "
            "benchmark embeddings"
        )


    # --------------------------------------------------------
    # Cache MISS：文件不存在、损坏，或题目 ID 已变化
    # --------------------------------------------------------

    queries = [
        question["question"]
        for question in questions
    ]


    print(
        f"Embedding "
        f"{len(queries)} benchmark queries..."
    )

    embeddings = embed(
        queries
    )

    embeddings = np.asarray(
        embeddings,
        dtype=np.float32,
    )


    # --------------------------------------------------------
    # 保存
    # --------------------------------------------------------

    np.savez(
        BENCHMARK_EMBEDDINGS_PATH,

        question_ids=np.asarray(
            current_ids
        ),

        embeddings=embeddings,
    )


    print(
        f"[CACHE SAVE] "
        f"benchmark embeddings: "
        f"{embeddings.shape}"
    )

    return (
        current_ids,
        embeddings,
    )


# ============================================================
# Main
# ============================================================

def main():

    print()
    print("=" * 70)
    print("BUILD / LOAD RAG CACHE")
    print("=" * 70)
    print()


    # --------------------------------------------------------
    # Corpus chunks
    # --------------------------------------------------------

    chunks = load_or_create_chunks()


    # --------------------------------------------------------
    # Corpus embeddings
    # --------------------------------------------------------

    corpus_embeddings = (
        load_or_create_corpus_embeddings(
            chunks
        )
    )


    # --------------------------------------------------------
    # Benchmark embeddings
    # --------------------------------------------------------

    questions = (
        load_answerable_benchmark()
    )

    question_ids, benchmark_embeddings = (
        load_or_create_benchmark_embeddings(
            questions
        )
    )


    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("CACHE READY")
    print("=" * 70)

    print(
        f"Corpus chunks: "
        f"{len(chunks)}"
    )

    print(
        f"Corpus embeddings: "
        f"{corpus_embeddings.shape}"
    )

    print(
        f"Benchmark questions: "
        f"{len(question_ids)}"
    )

    print(
        f"Benchmark embeddings: "
        f"{benchmark_embeddings.shape}"
    )

    print()

    print(
        f"Cache directory: "
        f"{CACHE_DIR}"
    )


if __name__ == "__main__":
    main()