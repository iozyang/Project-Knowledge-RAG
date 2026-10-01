import json
import re
from pathlib import Path

from langchain_text_splitters import RecursiveCharacterTextSplitter


# ============================================================
# 配置
# ============================================================

CHUNK_SIZE = 500
CHUNK_OVERLAP = 100

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# ------------------------------------------------------------
# 只使用冻结的 P1-10MD-v1 Corpus
# ------------------------------------------------------------

CORPUS_DIR = (
    PROJECT_ROOT
    / "corpus"
    / "dalian-neusoft-movie-analysis"
)

# ------------------------------------------------------------
# Heading-aware 独立缓存
#
# 不覆盖原来的：
# cache/corpus_chunks.jsonl
# ------------------------------------------------------------

CACHE_DIR = (
    PROJECT_ROOT
    / "cache"
)

HEADING_CHUNKS_CACHE = (
    CACHE_DIR
    / "heading_corpus_chunks.jsonl"
)


# ============================================================
# Recursive Splitter
# ============================================================

text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP,
    separators=[
        "\n\n",
        "\n",
        "。",
        "；",
        "，",
        " ",
        "",
    ],
)


# ============================================================
# Markdown Heading Section Parser
# ============================================================

def split_by_heading(text: str):
    """
    Markdown
    ↓
    标题层级解析
    ↓
    Section

    Section:

    {
        "heading_path": "...",
        "content": "..."
    }
    """

    sections = []

    heading_stack = []
    current_content = []
    current_path = ""

    in_code_block = False


    # --------------------------------------------------------
    # 保存当前 Section
    # --------------------------------------------------------

    def save_section():

        if not current_path:
            return

        content = "\n".join(
            current_content
        ).strip()

        if not content:
            return

        sections.append(
            {
                "heading_path":
                    current_path,

                "content":
                    content,
            }
        )


    # --------------------------------------------------------
    # 逐行扫描 Markdown
    # --------------------------------------------------------

    for line in text.splitlines():

        stripped = line.strip()


        # ====================================================
        # fenced code block
        #
        # 避免把代码中的 "# xxx"
        # 错误识别为 Markdown Heading
        # ====================================================

        if (
            stripped.startswith("```")
            or stripped.startswith("~~~")
        ):

            in_code_block = not in_code_block

            current_content.append(
                line
            )

            continue


        # ====================================================
        # Markdown Heading
        #
        # # title
        # ## title
        # ### title
        # ...
        # ====================================================

        heading_match = None

        if not in_code_block:

            heading_match = re.match(
                r"^(#{1,6})\s+(.+?)\s*$",
                stripped,
            )


        if heading_match:

            # -----------------------------------------------
            # 新标题出现
            # 先保存上一个 Section
            # -----------------------------------------------

            save_section()

            current_content.clear()


            # -----------------------------------------------
            # 标题级别
            # -----------------------------------------------

            level = len(
                heading_match.group(1)
            )

            title = (
                heading_match
                .group(2)
                .strip()
            )


            # -----------------------------------------------
            # 更新标题层级
            #
            # # A
            # ## B
            # ### C
            #
            # =>
            #
            # A > B > C
            # -----------------------------------------------

            heading_stack[:] = (
                heading_stack[
                    : level - 1
                ]
            )

            heading_stack.append(
                title
            )


            current_path = " > ".join(
                heading_stack
            )


        else:

            # -----------------------------------------------
            # 普通正文
            # -----------------------------------------------

            current_content.append(
                line
            )


    # --------------------------------------------------------
    # 保存最后一个 Section
    # --------------------------------------------------------

    save_section()

    return sections


# ============================================================
# 无效 Chunk 检查
# ============================================================

def is_useless_chunk(text: str):
    """
    过滤纯 Markdown 分隔符等无意义 Chunk。

    例如：

    ---
    ***
    ___
    """

    stripped = text.strip()

    if not stripped:
        return True

    if re.fullmatch(
        r"[-*_]{3,}",
        stripped,
    ):
        return True

    return False


# ============================================================
# Section 内 Recursive 500/100
# ============================================================

def split_section_recursive(section):
    """
    Heading Section
    ↓
    Section 内 Recursive 500/100
    ↓
    子 Chunk 继承 heading_path

    retrieval_text:
        heading_path + content

    content:
        仅正文
    """

    heading_path = section[
        "heading_path"
    ]

    content = section[
        "content"
    ]


    child_texts = (
        text_splitter.split_text(
            content
        )
    )


    chunks = []


    for child_text in child_texts:

        child_text = (
            child_text.strip()
        )


        # ----------------------------------------------------
        # 删除空 Chunk / "---" 等
        # ----------------------------------------------------

        if is_useless_chunk(
            child_text
        ):
            continue


        # ----------------------------------------------------
        # Retrieval 使用：
        #
        # heading_path + content
        # ----------------------------------------------------

        retrieval_text = (
            f"{heading_path}\n"
            f"{child_text}"
        )


        chunks.append(
            {
                "heading_path":
                    heading_path,

                "content":
                    child_text,

                "retrieval_text":
                    retrieval_text,
            }
        )


    return chunks


# ============================================================
# 单个 Markdown
# ============================================================

def chunk_markdown_file(
    file_path: Path,
):
    """
    Markdown
    ↓
    Heading Section
    ↓
    Recursive 500/100
    """

    text = file_path.read_text(
        encoding="utf-8"
    )


    sections = split_by_heading(
        text
    )


    chunks = []


    for section in sections:

        child_chunks = (
            split_section_recursive(
                section
            )
        )

        chunks.extend(
            child_chunks
        )


    return chunks


# ============================================================
# 实际执行 Corpus Chunking
# ============================================================

def build_corpus_chunks():
    """
    真正执行 Heading-aware Chunking。

    只有 Cache MISS 时才调用。
    """

    markdown_files = sorted(
        CORPUS_DIR.rglob("*.md")
    )


    chunks = []

    global_chunk_index = 0


    for file_path in markdown_files:

        # ----------------------------------------------------
        # 保持与 Benchmark / Baseline 相同 source 格式
        #
        # backend/API手册.md
        # data/...
        # frontend/...
        # ----------------------------------------------------

        relative_path = (
            file_path
            .relative_to(CORPUS_DIR)
            .as_posix()
        )


        file_chunks = (
            chunk_markdown_file(
                file_path
            )
        )


        for file_chunk_index, chunk in enumerate(
            file_chunks
        ):

            chunks.append(
                {
                    "chunk_id":
                        (
                            f"{relative_path}"
                            f"::{file_chunk_index}"
                        ),

                    "source":
                        relative_path,

                    "heading_path":
                        chunk[
                            "heading_path"
                        ],

                    # Evidence / Citation
                    "content":
                        chunk[
                            "content"
                        ],

                    # BM25 / Embedding
                    "retrieval_text":
                        chunk[
                            "retrieval_text"
                        ],

                    "global_index":
                        global_chunk_index,
                }
            )


            global_chunk_index += 1


    return chunks


# ============================================================
# 保存 Cache
# ============================================================

def save_chunks_cache(
    chunks,
):
    """
    保存 Heading-aware Chunks。
    """

    CACHE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )


    with HEADING_CHUNKS_CACHE.open(
        "w",
        encoding="utf-8",
    ) as f:

        for chunk in chunks:

            f.write(
                json.dumps(
                    chunk,
                    ensure_ascii=False,
                )
                + "\n"
            )


    print(
        f"[CACHE SAVE] "
        f"heading chunks: "
        f"{len(chunks)}"
    )


# ============================================================
# 读取 Cache
# ============================================================

def load_chunks_cache():
    """
    读取 Heading-aware Chunk Cache。
    """

    chunks = []


    with HEADING_CHUNKS_CACHE.open(
        "r",
        encoding="utf-8",
    ) as f:

        for line in f:

            if not line.strip():
                continue

            chunks.append(
                json.loads(line)
            )


    return chunks


# ============================================================
# Load or Create
# ============================================================

def load_or_create_chunks(
    force_rebuild=False,
):
    """
    默认：

    Cache 存在
        → 直接读取

    Cache 不存在
        → 重新 Heading-aware Chunking
        → 保存 Cache


    force_rebuild=True：

        忽略 Cache
        → 重新生成
    """

    CACHE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )


    # --------------------------------------------------------
    # Cache HIT
    # --------------------------------------------------------

    if (
        not force_rebuild
        and HEADING_CHUNKS_CACHE.exists()
        and HEADING_CHUNKS_CACHE.stat().st_size > 0
    ):

        try:

            chunks = (
                load_chunks_cache()
            )


            if chunks:

                print(
                    f"[CACHE HIT] "
                    f"heading chunks: "
                    f"{len(chunks)}"
                )

                return chunks


            print(
                "[CACHE INVALID] "
                "heading chunks is empty"
            )


        except (
            json.JSONDecodeError,
            OSError,
        ):

            print(
                "[CACHE INVALID] "
                "heading chunks file is corrupted"
            )


    # --------------------------------------------------------
    # Cache MISS
    # --------------------------------------------------------

    print(
        "[CACHE MISS] "
        "heading chunks"
    )

    print(
        "Running heading-aware "
        "recursive chunking..."
    )


    chunks = (
        build_corpus_chunks()
    )


    save_chunks_cache(
        chunks
    )


    return chunks


# ============================================================
# 与旧 Chunker 保持接口兼容
# ============================================================

def load_and_chunk_corpus(
    force_rebuild=False,
):
    """
    保持之前：

        documents, chunks =
            load_and_chunk_corpus()

    的调用形式。

    chunks 使用缓存。

    documents 这里只保留最简单的文件信息，
    不参与后续 Retrieval。
    """

    markdown_files = sorted(
        CORPUS_DIR.rglob("*.md")
    )


    documents = [
        {
            "source":
                file_path
                .relative_to(CORPUS_DIR)
                .as_posix()
        }
        for file_path
        in markdown_files
    ]


    chunks = load_or_create_chunks(
        force_rebuild=force_rebuild
    )


    return (
        documents,
        chunks,
    )


# ============================================================
# 统计
# ============================================================

def print_statistics(
    documents,
    chunks,
):

    print()
    print("=" * 70)
    print(
        "HEADING-AWARE + "
        "RECURSIVE CHUNKING"
    )
    print("=" * 70)


    print(
        f"Documents: "
        f"{len(documents)}"
    )

    print(
        f"Chunks: "
        f"{len(chunks)}"
    )


    if not chunks:
        return


    lengths = [
        len(
            chunk["content"]
        )
        for chunk in chunks
    ]


    print(
        f"Min length: "
        f"{min(lengths)}"
    )

    print(
        f"Max length: "
        f"{max(lengths)}"
    )

    print(
        f"Avg length: "
        f"{sum(lengths) / len(lengths):.2f}"
    )


# ============================================================
# Sample
# ============================================================

def print_samples(
    chunks,
    count=5,
):

    print()
    print("=" * 70)
    print("SAMPLE CHUNKS")
    print("=" * 70)


    for chunk in chunks[:count]:

        print()

        print(
            f"chunk_id: "
            f"{chunk['chunk_id']}"
        )

        print(
            f"source: "
            f"{chunk['source']}"
        )

        print(
            f"heading_path: "
            f"{chunk['heading_path']}"
        )


        print()
        print("content:")

        print(
            chunk[
                "content"
            ][:500]
        )


        print()
        print("retrieval_text:")

        print(
            chunk[
                "retrieval_text"
            ][:700]
        )


        print(
            "-" * 70
        )


# ============================================================
# Main
# ============================================================

def main():

    documents, chunks = (
        load_and_chunk_corpus()
    )


    print_statistics(
        documents,
        chunks,
    )


    print_samples(
        chunks,
        count=5,
    )


if __name__ == "__main__":
    main()