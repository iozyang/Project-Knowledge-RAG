import importlib

import numpy as np
from rank_bm25 import BM25Okapi


# ============================================================
# 导入已有模块
# ============================================================

bm25_module = importlib.import_module(
    "src.retrieval.1_bm25_retriever"
)
tokenize = bm25_module.tokenize


dense_module = importlib.import_module(
    "src.retrieval.2_dense_retriever"
)
embed = dense_module.embed
cosine_similarity = dense_module.cosine_similarity


chunker_module = importlib.import_module(
    "src.ingestion.2_recursive_chunker"
)
load_and_chunk_corpus = chunker_module.load_and_chunk_corpus


# ============================================================
# 配置
# ============================================================

CANDIDATE_K = 20
RRF_CANDIDATE_K = 20
FINAL_K = 5
RRF_K = 60


# ============================================================
# BM25
# ============================================================

def build_bm25(chunks):
    """
    为全部 Chunk 建立 BM25 索引。
    """

    tokenized_chunks = [
        tokenize(chunk["content"])
        for chunk in chunks
    ]

    return BM25Okapi(tokenized_chunks)


# ============================================================
# RRF
# ============================================================

def reciprocal_rank_fusion(
    bm25_indices,
    dense_indices,
    rrf_k=RRF_K,
):
    """
    对 BM25 和 Dense 排名进行 RRF 融合。
    """

    fused = {}

    # BM25
    for rank, chunk_index in enumerate(
        bm25_indices,
        start=1,
    ):
        chunk_index = int(chunk_index)

        if chunk_index not in fused:
            fused[chunk_index] = {
                "rrf_score": 0.0,
                "bm25_rank": None,
                "dense_rank": None,
            }

        fused[chunk_index]["bm25_rank"] = rank

        fused[chunk_index]["rrf_score"] += (
            1 / (rrf_k + rank)
        )

    # Dense
    for rank, chunk_index in enumerate(
        dense_indices,
        start=1,
    ):
        chunk_index = int(chunk_index)

        if chunk_index not in fused:
            fused[chunk_index] = {
                "rrf_score": 0.0,
                "bm25_rank": None,
                "dense_rank": None,
            }

        fused[chunk_index]["dense_rank"] = rank

        fused[chunk_index]["rrf_score"] += (
            1 / (rrf_k + rank)
        )

    return fused


# ============================================================
# 构造输出结果
# ============================================================

def build_results(
    ranked,
    chunks,
    bm25_scores,
    dense_scores,
    top_k,
):
    """
    把 RRF 排名转换成统一结果结构。
    """

    results = []

    for rank, (
        chunk_index,
        rrf_info,
    ) in enumerate(
        ranked[:top_k],
        start=1,
    ):
        results.append(
            {
                "rank": rank,

                "chunk_index":
                    chunk_index,

                "chunk":
                    chunks[chunk_index],

                "rrf_score":
                    rrf_info["rrf_score"],

                "bm25_rank":
                    rrf_info["bm25_rank"],

                "dense_rank":
                    rrf_info["dense_rank"],

                # 仅用于 Debug
                "bm25_score":
                    float(
                        bm25_scores[chunk_index]
                    ),

                "dense_score":
                    float(
                        dense_scores[chunk_index]
                    ),
            }
        )

    return results


# ============================================================
# Hybrid Search
# ============================================================

def hybrid_search(
    query,
    chunks,
    bm25,
    chunk_vectors,
    candidate_k=CANDIDATE_K,
    rrf_candidate_k=RRF_CANDIDATE_K,
    final_k=FINAL_K,
):
    """
    BM25 Top20
    +
    Dense Top20
    ↓
    Union + RRF
    ↓
    RRF Top20
    ↓
    Final Top5
    """

    # --------------------------------------------------------
    # 1. BM25 Top20
    # --------------------------------------------------------

    bm25_scores = bm25.get_scores(
        tokenize(query)
    )

    bm25_indices = np.argsort(
        bm25_scores
    )[::-1][:candidate_k]


    # --------------------------------------------------------
    # 2. Dense Top20
    # --------------------------------------------------------

    query_vector = embed([query])[0]

    dense_scores = cosine_similarity(
        query_vector,
        chunk_vectors,
    )

    dense_indices = np.argsort(
        dense_scores
    )[::-1][:candidate_k]


    # --------------------------------------------------------
    # 3. RRF
    # --------------------------------------------------------

    fused = reciprocal_rank_fusion(
        bm25_indices,
        dense_indices,
    )

    ranked = sorted(
        fused.items(),
        key=lambda item: item[1]["rrf_score"],
        reverse=True,
    )


    # --------------------------------------------------------
    # 4. RRF Top20
    # --------------------------------------------------------

    candidate_results = build_results(
        ranked=ranked,
        chunks=chunks,
        bm25_scores=bm25_scores,
        dense_scores=dense_scores,
        top_k=rrf_candidate_k,
    )


    # --------------------------------------------------------
    # 5. Final Top5
    # --------------------------------------------------------

    final_results = build_results(
        ranked=ranked,
        chunks=chunks,
        bm25_scores=bm25_scores,
        dense_scores=dense_scores,
        top_k=final_k,
    )


    return {
        "candidate_results":
            candidate_results,

        "final_results":
            final_results,

        "union_size":
            len(fused),
    }


# ============================================================
# Probe
# ============================================================

def main():

    # --------------------------------------------------------
    # Corpus
    # --------------------------------------------------------

    _, chunks = load_and_chunk_corpus()

    print(
        f"Chunks: {len(chunks)}"
    )


    # --------------------------------------------------------
    # BM25
    # --------------------------------------------------------

    print("Building BM25 index...")

    bm25 = build_bm25(chunks)


    # --------------------------------------------------------
    # Dense
    # --------------------------------------------------------

    print("Embedding chunks...")

    texts = [
        chunk["content"]
        for chunk in chunks
    ]

    chunk_vectors = embed(texts)

    print(
        f"Chunk vectors: "
        f"{len(chunk_vectors)}"
    )


    # --------------------------------------------------------
    # Probe Query
    # --------------------------------------------------------

    query = (
        "做演员参演数 Top50 时，"
        "`ACTOR_IDS` 先按什么分隔，"
        "演员名从哪里取？"
    )

    print()
    print("Query:")
    print(query)


    # --------------------------------------------------------
    # Hybrid
    # --------------------------------------------------------

    search_result = hybrid_search(
        query=query,
        chunks=chunks,
        bm25=bm25,
        chunk_vectors=chunk_vectors,
    )

    candidate_results = (
        search_result["candidate_results"]
    )

    final_results = (
        search_result["final_results"]
    )


    print()
    print(
        "Union candidate count:",
        search_result["union_size"],
    )


    # --------------------------------------------------------
    # RRF Top20
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("RRF TOP 20")
    print("=" * 70)

    for result in candidate_results:

        chunk = result["chunk"]

        print(
            f"{result['rank']:>2}. "
            f"{chunk['chunk_id']}"
        )

        print(
            f"    RRF={result['rrf_score']:.6f} "
            f"BM25={result['bm25_rank']} "
            f"Dense={result['dense_rank']}"
        )


    # --------------------------------------------------------
    # Final Top5
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("FINAL TOP 5")
    print("=" * 70)

    for result in final_results:

        chunk = result["chunk"]

        print()
        print(
            f"TOP {result['rank']}"
        )

        print(
            f"RRF score: "
            f"{result['rrf_score']:.6f}"
        )

        print(
            f"BM25 rank: "
            f"{result['bm25_rank']}"
        )

        print(
            f"Dense rank: "
            f"{result['dense_rank']}"
        )

        print(
            f"source: "
            f"{chunk['source']}"
        )

        print(
            f"chunk_id: "
            f"{chunk['chunk_id']}"
        )


if __name__ == "__main__":
    main()