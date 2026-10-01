import importlib
import os
from pathlib import Path

import httpx
import numpy as np
from dotenv import load_dotenv


# ============================================================
# 导入已有模块
# ============================================================

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


bm25_module = importlib.import_module(
    "src.retrieval.1_bm25_retriever"
)

tokenize = bm25_module.tokenize


# ============================================================
# Cache
# ============================================================

cache_module = importlib.import_module(
    "src.retrieval_cache"
)

load_or_create_chunks = (
    cache_module.load_or_create_chunks
)

load_or_create_corpus_embeddings = (
    cache_module.load_or_create_corpus_embeddings
)


# ============================================================
# 配置
# ============================================================

CANDIDATE_K = 20
FINAL_K = 5
RRF_K = 60

RERANK_MODEL = "qwen3.7-text-rerank"

INSTRUCT = (
    "Given a software engineering project question, "
    "retrieve passages that directly answer the question."
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]

load_dotenv(
    PROJECT_ROOT / ".env"
)

API_KEY = os.getenv(
    "DASHSCOPE_API_KEY"
)

BASE_URL = os.getenv(
    "DASHSCOPE_BASE_URL"
)


# ============================================================
# Rerank Endpoint
# ============================================================

def get_rerank_url():

    if not BASE_URL:

        raise ValueError(
            "DASHSCOPE_BASE_URL 未配置"
        )

    base_url = BASE_URL.rstrip("/")

    if "/compatible-mode/v1" in base_url:

        base_url = base_url.replace(
            "/compatible-mode/v1",
            "/api/v1",
        )

    return (
        base_url
        + "/services/rerank/"
        + "text-rerank/"
        + "text-rerank"
    )


# ============================================================
# Qwen Reranker
# ============================================================

def rerank(
    query,
    candidate_indices,
    chunks,
    top_n=FINAL_K,
):
    """
    对候选 Chunk 进行 Rerank。

    candidate_indices:
        chunks 中的全局下标

    返回：
        Reranker 排序后的结果
    """

    # documents = [
    #     chunks[index]["content"]
    #     for index in candidate_indices
    # ]

    documents = [
        chunks[index].get(
            "retrieval_text",
            chunks[index]["content"],
        )
        for index in candidate_indices
    ]


    payload = {

        "model":
            RERANK_MODEL,

        "input": {

            "query":
                query,

            "documents":
                documents,
        },

        "parameters": {

            "top_n":
                top_n,

            "instruct":
                INSTRUCT,
        },
    }


    response = httpx.post(

        get_rerank_url(),

        headers={

            "Authorization":
                f"Bearer {API_KEY}",

            "Content-Type":
                "application/json",
        },

        json=payload,

        timeout=60,
    )


    response.raise_for_status()

    data = response.json()

    rerank_results = (
        data["output"]["results"]
    )


    results = []

    for rank, item in enumerate(
        rerank_results,
        start=1,
    ):

        # item["index"] 是 documents 中的局部下标
        candidate_position = (
            item["index"]
        )

        # 转换回 chunks 中的全局下标
        chunk_index = int(
            candidate_indices[
                candidate_position
            ]
        )


        results.append(
            {
                "rank":
                    rank,

                "chunk_index":
                    chunk_index,

                "chunk":
                    chunks[chunk_index],

                "rerank_score":
                    item["relevance_score"],
            }
        )

    return results


# ============================================================
# Dense TopK
# ============================================================

def dense_top_k(
    query,
    chunk_vectors,
    top_k=CANDIDATE_K,
):
    """
    Probe 使用。

    Corpus Embedding 已缓存，
   这里只需要对新 Query 做一次 Embedding。
    """

    query_vector = embed(
        [query]
    )[0]


    scores = cosine_similarity(
        query_vector,
        chunk_vectors,
    )


    indices = np.argsort(
        scores
    )[::-1][:top_k]


    return [
        int(index)
        for index in indices
    ]


# ============================================================
# RRF TopK
# ============================================================

def rrf_top_k(
    query,
    chunks,
    bm25,
    chunk_vectors,
    top_k=CANDIDATE_K,
):
    """
    BM25 Top20
        +
    Dense Top20
        ↓
    Union + RRF
        ↓
    RRF Top20
    """


    # --------------------------------------------------------
    # BM25 Top20
    # --------------------------------------------------------

    bm25_scores = bm25.get_scores(
        tokenize(query)
    )


    bm25_indices = np.argsort(
        bm25_scores
    )[::-1][:top_k]


    # --------------------------------------------------------
    # Dense Top20
    # --------------------------------------------------------

    query_vector = embed(
        [query]
    )[0]


    dense_scores = cosine_similarity(
        query_vector,
        chunk_vectors,
    )


    dense_indices = np.argsort(
        dense_scores
    )[::-1][:top_k]


    # --------------------------------------------------------
    # RRF
    # --------------------------------------------------------

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


    return [
        int(chunk_index)
        for chunk_index, _
        in ranked[:top_k]
    ]


# ============================================================
# Probe
# ============================================================

def main():

    print()
    print("=" * 70)
    print("RERANK PROBE")
    print("=" * 70)


    # --------------------------------------------------------
    # 1. 读取缓存 Chunk
    # --------------------------------------------------------

    chunks = load_or_create_chunks()

    print(
        f"Chunks: {len(chunks)}"
    )


    # --------------------------------------------------------
    # 2. 读取缓存 Corpus Embeddings
    # --------------------------------------------------------

    chunk_vectors = (
        load_or_create_corpus_embeddings(
            chunks
        )
    )

    print(
        f"Chunk vectors: "
        f"{chunk_vectors.shape}"
    )


    # --------------------------------------------------------
    # 3. BM25
    # --------------------------------------------------------

    print(
        "Building BM25 index..."
    )

    bm25 = build_bm25(
        chunks
    )


    # --------------------------------------------------------
    # 4. Probe Query
    # --------------------------------------------------------

    query = (
        "做演员参演数 Top50 时，"
        "`ACTOR_IDS` 先按什么分隔，"
        "演员名从哪里取？"
    )


    print()

    print(
        "Query:"
    )

    print(
        query
    )


    # --------------------------------------------------------
    # 5. RRF Top20
    # --------------------------------------------------------

    print()
    print(
        "Retrieving RRF Top20..."
    )


    candidate_indices = rrf_top_k(

        query=query,

        chunks=chunks,

        bm25=bm25,

        chunk_vectors=chunk_vectors,

        top_k=CANDIDATE_K,
    )


    print(
        f"Candidates: "
        f"{len(candidate_indices)}"
    )


    # --------------------------------------------------------
    # 6. Rerank Top20 -> Top5
    # --------------------------------------------------------

    print()
    print(
        "Reranking Top20 -> Top5..."
    )


    results = rerank(

        query=query,

        candidate_indices=candidate_indices,

        chunks=chunks,

        top_n=FINAL_K,
    )


    # --------------------------------------------------------
    # 7. 输出
    # --------------------------------------------------------

    print()

    print("=" * 70)
    print("RERANK TOP 5")
    print("=" * 70)


    for result in results:

        chunk = result["chunk"]

        print()

        print(
            f"TOP {result['rank']}"
        )

        print(
            f"rerank_score: "
            f"{result['rerank_score']:.6f}"
        )

        print(
            f"source: "
            f"{chunk['source']}"
        )

        print(
            f"chunk_id: "
            f"{chunk['chunk_id']}"
        )

        print()

        print(
            chunk["content"][:300]
        )


if __name__ == "__main__":
    main()