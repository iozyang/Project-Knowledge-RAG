from pathlib import Path

from langchain_text_splitters import RecursiveCharacterTextSplitter


CHUNK_SIZE = 500
CHUNK_OVERLAP = 100

PROJECT_ROOT = Path(__file__).resolve().parents[2]

CORPUS_DIR = (
    PROJECT_ROOT
    / "corpus"
    / "dalian-neusoft-movie-analysis"
)


# 递归字符切片器
splitter = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP,
    separators=[
        "\n\n",   # 优先按段落
        "\n",     # 再按换行
        "。",     # 再按句号
        "；",
        "，",
        " ",
        "",       # 最后实在不行才硬切
    ],
)


def split_text(text):
    """
    将一篇文档切成多个 chunk。
    """
    return splitter.split_text(text)


def load_and_chunk_corpus():
    """
    读取 Corpus 中全部 Markdown，并进行 Recursive Character Chunking。
    """

    markdown_files = sorted(
        CORPUS_DIR.rglob("*.md")
    )

    all_chunks = []

    for file_path in markdown_files:
        text = file_path.read_text(
            encoding="utf-8"
        )

        source = file_path.relative_to(
            CORPUS_DIR
        ).as_posix()

        texts = split_text(text)

        for index, chunk_text in enumerate(texts):
            all_chunks.append(
                {
                    "chunk_id": f"{source}::{index}",
                    "source": source,
                    "chunk_index": index,
                    "content": chunk_text,
                }
            )

    return markdown_files, all_chunks


def main():
    files, chunks = load_and_chunk_corpus()

    print("=" * 60)
    print("Recursive Character Chunking")
    print("=" * 60)

    print(f"文档数量: {len(files)}")
    print(f"Chunk 数量: {len(chunks)}")
    print(f"Chunk Size: {CHUNK_SIZE}")
    print(f"Overlap: {CHUNK_OVERLAP}")

    print()
    print("=" * 60)
    print("前两个 Chunk")
    print("=" * 60)

    for chunk in chunks[:2]:
        print()
        print("chunk_id:", chunk["chunk_id"])
        print("source:", chunk["source"])
        print("length:", len(chunk["content"]))
        print()
        print(chunk["content"])
        print("-" * 60)


if __name__ == "__main__":
    main()