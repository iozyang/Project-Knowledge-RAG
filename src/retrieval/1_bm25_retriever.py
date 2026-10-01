# src/retrieval/bm25_retriever.py
# 使用BM25算法进行检索
# BM25是一种基于TF-IDF的检索算法，用于计算查询与文档之间的相似度，简单理解为关键词

import importlib

import jieba
from rank_bm25 import BM25Okapi# BM25算法实现

fixed_chunker = importlib.import_module("src.ingestion.1_fixed_chunker")
load_and_chunk_corpus = fixed_chunker.load_and_chunk_corpus

# 将文本分词，把chunk的内容转换为关键词列表
def tokenize(text):
    return [
        word.strip().lower()
        for word in jieba.lcut(text)
        if word.strip()
    ]


def main():
    _, chunks = load_and_chunk_corpus()# 加载并chunk化corpus

    # 1. 把每个 Chunk 分词
    tokenized_chunks = [
        tokenize(chunk["content"])
        for chunk in chunks
    ]

    # 2. 建立 BM25 索引
    bm25 = BM25Okapi(tokenized_chunks)

    # 3. 测试一个问题
    query = "后端用的什么框架？"
    query_tokens = tokenize(query)

    # 4. 计算每个 Chunk 的 BM25 分数
    scores = bm25.get_scores(query_tokens)

    # 5. 找分数最高的 5 个
    top_indices = sorted(
        range(len(scores)),
        key=lambda i: scores[i],
        reverse=True,
    )[:5]

    # 6. 打印结果
    for rank, index in enumerate(top_indices, start=1):
        chunk = chunks[index]

        print("=" * 60)
        print(f"TOP {rank}")
        print(f"score: {scores[index]:.4f}")# 
        print(f"source: {chunk['source']}")
        print(f"chunk_id: {chunk['chunk_id']}")
        print()
        print(chunk["content"][:300])


if __name__ == "__main__":
    main()