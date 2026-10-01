# src/ingestion/fixed_chunker.py
# baseline的chunking策略：size=500, overlap=100

# 将corpus/dalian-neusoft-movie-analysis中的markdown文件进行chunking


from pathlib import Path


CHUNK_SIZE = 500
CHUNK_OVERLAP = 100


# 项目根目录：RAG/
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# 当前 Frozen Corpus
CORPUS_DIR = (
    PROJECT_ROOT
    / "corpus"
    / "dalian-neusoft-movie-analysis"
)


def split_text(text: str):
    """
    最简单的固定字符切片：
    每个 chunk 500 个字符，相邻 chunk 重叠 100 个字符。
    """

    # 使用列表存储每个chunk
    chunks = []

    # 每次向前移动 400 个字符
    step = CHUNK_SIZE - CHUNK_OVERLAP

    start = 0

    while start < len(text):
        end = min(start + CHUNK_SIZE, len(text))

        chunk_text = text[start:end]

        # 将chunk添加到列表中
        chunks.append(
            {
                "start": start, #记录chunk的开始位置
                "end": end, #记录chunk的结束位置
                "content": chunk_text, #记录chunk的内容
            }
        )

        # 已经到文档末尾就结束
        if end == len(text):
            break

        start += step # 移动到下一个chunk的开始位置

    return chunks


def load_and_chunk_corpus():
    """
    读取 10 个 Markdown，并全部切片。
    """

    markdown_files = sorted(CORPUS_DIR.rglob("*.md"))# 以递归方式查找corpus目录下的所有markdown文件

    # # 逐行打印出扫描到的markdown文件
    # print("扫描到的markdown文件:")
    # for file in markdown_files:
    #     print(file)
    
    all_chunks = []# 用列表存储所有chunk

    for file_path in markdown_files:
        text = file_path.read_text(encoding="utf-8")

        # 例如：
        # backend/API手册.md
        source = file_path.relative_to(CORPUS_DIR).as_posix()

        chunks = split_text(text)

        for index, chunk in enumerate(chunks):
            all_chunks.append(
                {
                    "chunk_id": f"{source}::{index}",
                    "source": source,
                    "chunk_index": index,
                    "start": chunk["start"],
                    "end": chunk["end"],
                    "content": chunk["content"],
                }
            )

    return markdown_files, all_chunks


def main():
    files, chunks = load_and_chunk_corpus()

    print("=" * 60)
    print("E0 Fixed-size Chunking")
    print("=" * 60)

    print(f"文档数量: {len(files)}")
    print(f"Chunk 数量: {len(chunks)}")
    print(f"Chunk Size: {CHUNK_SIZE}")
    print(f"Overlap: {CHUNK_OVERLAP}")

    print("\n读取到的文档：")

    for file in files:
        print("-", file.relative_to(CORPUS_DIR))

    print("\n" + "=" * 60)
    print("第 1 个 Chunk")
    print("=" * 60)

    first = chunks[0]

    print("chunk_id:", first["chunk_id"])
    print("source:", first["source"])
    print("start:", first["start"])
    print("end:", first["end"])
    print()
    print(first["content"])

    print("\n" + "=" * 60)
    print("第 2 个 Chunk")
    print("=" * 60)

    second = chunks[1]

    print("chunk_id:", second["chunk_id"])
    print("source:", second["source"])
    print("start:", second["start"])
    print("end:", second["end"])
    print()
    print(second["content"])


if __name__ == "__main__":
    main()