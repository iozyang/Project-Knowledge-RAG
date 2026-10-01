import asyncio
import importlib
import time


# ============================================================
# 复用已经冻结、验证过的模块
# ============================================================

heading_chunker = importlib.import_module(
    "src.ingestion.3_heading_recursive_chunker"
)

heading_eval = importlib.import_module(
    "evaluation.retrieval.5_heading_eval"
)

heading_rerank_eval = importlib.import_module(
    "evaluation.retrieval.5_heading_rerank_eval"
)

dense_module = importlib.import_module(
    "src.retrieval.2_dense_retriever"
)

rerank_module = importlib.import_module(
    "src.retrieval.4_rerank_retriever"
)

generator = importlib.import_module(
    "src.generation.4_qwen_flash_generator"
)


# ============================================================
# 冻结参数
# ============================================================

CANDIDATE_K = 20
FINAL_K = 5

chunks = None
chunk_vectors = None
bm25 = None


# ============================================================
# 初始化
# ============================================================

def initialize():
    global chunks, chunk_vectors, bm25

    print("=" * 70)
    print("RAG DEMO INITIALIZING")
    print("=" * 70)

    _, chunks = heading_chunker.load_and_chunk_corpus()

    chunk_vectors = (
        heading_eval.load_or_create_heading_embeddings(
            chunks
        )
    )

    bm25 = heading_eval.build_heading_bm25(
        chunks
    )

    print()
    print(f"Chunks: {len(chunks)}")
    print(f"Embedding shape: {chunk_vectors.shape}")
    print("Retrieval: Heading-aware + BM2520 + Dense20 + RRF20 + Rerank5")
    print(f"Generator: {generator.GENERATOR_MODEL}")
    print("Ready.")


# ============================================================
# Frozen Retrieval
# ============================================================

def retrieve(question):
    start = time.perf_counter()

    # 1. Query Embedding
    query_vector = dense_module.embed(
        [question]
    )[0]

    # 2. BM25 Top20 + Dense Top20 -> RRF Top20
    candidate_indices = (
        heading_rerank_eval.rrf_top20(
            query=question,
            query_vector=query_vector,
            chunk_vectors=chunk_vectors,
            bm25=bm25,
        )
    )

    # 3. RRF Top20 -> Qwen Reranker -> Top5
    reranked = rerank_module.rerank(
        query=question,
        candidate_indices=candidate_indices,
        chunks=chunks,
        top_n=FINAL_K,
    )

    latency_ms = (
        time.perf_counter() - start
    ) * 1000

    return reranked, round(latency_ms, 2)


# ============================================================
# Top5 -> Generation Context
# ============================================================

def build_contexts(reranked):
    contexts = []

    for result in reranked:
        chunk = result["chunk"]

        contexts.append(
            {
                "source": chunk["source"],
                "heading_path": chunk["heading_path"],
                "content": chunk["content"],
            }
        )

    return contexts


# ============================================================
# 单次问答
# ============================================================

async def ask(question):
    total_start = time.perf_counter()

    print()
    print("[1/2] Retrieving...")

    reranked, retrieval_ms = retrieve(
        question
    )

    contexts = build_contexts(
        reranked
    )

    print(
        f"      RRF Top{CANDIDATE_K} "
        f"-> Rerank Top{FINAL_K} "
        f"({retrieval_ms:.2f} ms)"
    )

    print("[2/2] Generating...")

    result = await generator.generate_answer(
        question=question,
        contexts=contexts,
    )

    total_ms = (
        time.perf_counter() - total_start
    ) * 1000

    print()
    print("=" * 70)
    print("ANSWER")
    print("=" * 70)
    print(result["answer"])

    print()
    print("=" * 70)
    print("SOURCES")
    print("=" * 70)

    for source_id, item in enumerate(
        reranked,
        start=1,
    ):
        chunk = item["chunk"]

        print(
            f"[S{source_id}] "
            f"{item['rerank_score']:.6f}"
        )
        print(
            f"  source: {chunk['source']}"
        )
        print(
            f"  heading: {chunk['heading_path']}"
        )

    print()
    print("=" * 70)
    print("TRACE")
    print("=" * 70)
    print(
        f"retrieval: {retrieval_ms:.2f} ms"
    )
    print(
        f"generation: {result['latency_ms']:.2f} ms"
    )
    print(
        f"total: {total_ms:.2f} ms"
    )
    print(
        f"tokens: {result['total_tokens']}"
    )
    print(
        f"parse_success: {result['parse_success']}"
    )
    print(
        f"citations: {result['citations']}"
    )


# ============================================================
# CLI Demo
# ============================================================

async def main():
    initialize()

    try:
        while True:
            print()
            question = input(
                "Question (输入 exit 退出): "
            ).strip()

            if not question:
                continue

            if question.lower() in {
                "exit",
                "quit",
                "q",
            }:
                break

            try:
                await ask(question)

            except Exception as exc:
                print()
                print(
                    f"[ERROR] "
                    f"{type(exc).__name__}: {exc}"
                )

    finally:
        client = getattr(
            generator,
            "client",
            None,
        )

        if client is not None:
            close = getattr(
                client,
                "close",
                None,
            )

            if close is not None:
                result = close()

                if asyncio.iscoroutine(result):
                    await result


if __name__ == "__main__":
    asyncio.run(main())

