import importlib
import os
from pathlib import Path

import numpy as np
from dotenv import load_dotenv
from openai import OpenAI


# 文件名以数字开头，不能写成普通 import
chunker = importlib.import_module("src.ingestion.2_recursive_chunker")
load_and_chunk_corpus = chunker.load_and_chunk_corpus


TOP_K = 5
EMBED_MODEL = "qwen3.7-text-embedding"# 向量模型
EMBED_DIMENSIONS = 1024# 向量维度
EMBED_BATCH_SIZE = 10# 向量批量大小，用以反映向量计算的效率

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

client = OpenAI(
    api_key=os.getenv("DASHSCOPE_API_KEY"),
    base_url=os.getenv("DASHSCOPE_BASE_URL"),
)


def embed(texts):
    """调用 qwen3.7-text-embedding，返回与 texts 顺序一致的向量。"""

    vectors = []

    for start in range(0, len(texts), EMBED_BATCH_SIZE):
        batch = texts[start:start + EMBED_BATCH_SIZE]

        response = client.embeddings.create(
            model=EMBED_MODEL,
            input=batch,
            dimensions=EMBED_DIMENSIONS,
            encoding_format="float",
        )

        ordered = sorted(response.data, key=lambda item: item.index)
        vectors.extend(item.embedding for item in ordered)

    return vectors


def cosine_similarity(query_vector, chunk_vectors):
    """
    计算 query 和所有 chunk 的余弦相似度。
    """

    query_vector = np.array(query_vector)
    chunk_vectors = np.array(chunk_vectors)

    query_norm = np.linalg.norm(query_vector)
    chunk_norms = np.linalg.norm(chunk_vectors, axis=1)

    scores = (
        chunk_vectors @ query_vector
        / (chunk_norms * query_norm)
    )

    return scores


def main():
    _, chunks = load_and_chunk_corpus()

    print(f"Chunks: {len(chunks)}")

    texts = [
        chunk["content"]
        for chunk in chunks
    ]

    chunk_vectors = embed(texts)

    query = "Spring Boot 后端默认监听哪个端口？"

    query_vector = embed([query])[0]

    scores = cosine_similarity(
        query_vector,
        chunk_vectors,
    )

    top_indices = np.argsort(scores)[::-1][:TOP_K]

    for rank, index in enumerate(
        top_indices,
        start=1,
    ):
        chunk = chunks[index]

        print("=" * 60)
        print(f"TOP {rank}")
        print(f"score: {scores[index]:.4f}")
        print(f"source: {chunk['source']}")
        print(f"chunk_id: {chunk['chunk_id']}")
        print()
        print(chunk["content"][:300])


if __name__ == "__main__":
    main()