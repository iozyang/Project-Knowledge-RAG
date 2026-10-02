import importlib
import json
import re
from pathlib import Path

import numpy as np
from rank_bm25 import BM25Okapi


# ============================================================
# 导入已有模块
# ============================================================

# Heading-aware Chunker
heading_chunker = importlib.import_module(
    "src.ingestion.3_heading_recursive_chunker"
)

load_and_chunk_corpus = (
    heading_chunker.load_and_chunk_corpus
)


# BM25 tokenizer
bm25_module = importlib.import_module(
    "src.retrieval.1_bm25_retriever"
)

tokenize = bm25_module.tokenize


# Dense
dense_module = importlib.import_module(
    "src.retrieval.2_dense_retriever"
)

embed = dense_module.embed

cosine_similarity = (
    dense_module.cosine_similarity
)


# RRF
hybrid_module = importlib.import_module(
    "src.retrieval.3_hybrid_retriever"
)

reciprocal_rank_fusion = (
    hybrid_module.reciprocal_rank_fusion
)


# Benchmark Cache
cache_module = importlib.import_module(
    "src.retrieval_cache"
)

load_answerable_benchmark = (
    cache_module.load_answerable_benchmark
)

load_or_create_benchmark_embeddings = (
    cache_module.load_or_create_benchmark_embeddings
)


# ============================================================
# 配置
# ============================================================

TOP_K = 20
RRF_K = 60

PROJECT_ROOT = Path(__file__).resolve().parents[2]

CACHE_DIR = (
    PROJECT_ROOT
    / "cache"
)

HEADING_EMBEDDINGS_PATH = (
    CACHE_DIR
    / "heading_corpus_embeddings.npy"
)

HEADING_BM25_TOKENS_PATH = (
    CACHE_DIR
    / "heading_bm25_tokens.json"
)

RUN_DIR = (
    PROJECT_ROOT
    / "evaluation"
    / "runs"
    / "retrieval"
    / "e4_heading_top20recall_check"
)


# ============================================================
# Heading Corpus Embedding Cache
# ============================================================

def load_or_create_heading_embeddings(
    chunks,
):
    """
    Heading-aware Chunk Embedding。

    注意：

    这里 Embedding 的不是 content，
    而是：

        heading_path
        +
        content

    即 chunk["retrieval_text"]。
    """

    CACHE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )


    # --------------------------------------------------------
    # Cache HIT
    # --------------------------------------------------------

    if (
        HEADING_EMBEDDINGS_PATH.exists()
        and HEADING_EMBEDDINGS_PATH.stat().st_size > 0
    ):

        try:

            embeddings = np.load(
                HEADING_EMBEDDINGS_PATH
            )


            if len(embeddings) == len(chunks):

                print(
                    "[CACHE HIT] "
                    "heading corpus embeddings: "
                    f"{embeddings.shape}"
                )

                return embeddings


            print(
                "[CACHE INVALID] "
                "heading embedding 数量 "
                "和 chunk 数量不一致"
            )


        except (
            EOFError,
            ValueError,
            OSError,
        ):

            print(
                "[CACHE INVALID] "
                "heading corpus embeddings corrupted"
            )


    # --------------------------------------------------------
    # Cache MISS
    # --------------------------------------------------------

    print(
        "[CACHE MISS] "
        "heading corpus embeddings"
    )


    texts = [
        chunk["retrieval_text"]
        for chunk in chunks
    ]


    print(
        f"Embedding "
        f"{len(texts)} heading-aware chunks..."
    )


    embeddings = embed(
        texts
    )


    embeddings = np.asarray(
        embeddings,
        dtype=np.float32,
    )


    np.save(
        HEADING_EMBEDDINGS_PATH,
        embeddings,
    )


    print(
        "[CACHE SAVE] "
        "heading corpus embeddings: "
        f"{embeddings.shape}"
    )


    return embeddings


# ============================================================
# Heading-aware BM25
# ============================================================

def build_heading_bm25(
    chunks,
):
    """
    BM25 也必须使用 retrieval_text：

        heading_path + content

    否则标题只参与 Dense，
    实验变量就不一致了。

    分词结果缓存到 cache/heading_bm25_tokens.json。
    命中时直接读词表，再交给 BM25Okapi。
    """

    CACHE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )


    tokenized_corpus = None


    # --------------------------------------------------------
    # Cache HIT
    # --------------------------------------------------------

    if (
        HEADING_BM25_TOKENS_PATH.exists()
        and HEADING_BM25_TOKENS_PATH.stat().st_size > 0
    ):

        try:

            tokenized_corpus = json.loads(
                HEADING_BM25_TOKENS_PATH.read_text(
                    encoding="utf-8"
                )
            )


            if (
                isinstance(tokenized_corpus, list)
                and len(tokenized_corpus) == len(chunks)
                and all(
                    isinstance(tokens, list)
                    for tokens in tokenized_corpus
                )
            ):

                print(
                    "[CACHE HIT] "
                    "heading bm25 tokens: "
                    f"{len(tokenized_corpus)}"
                )


            else:

                tokenized_corpus = None

                print(
                    "[CACHE INVALID] "
                    "heading bm25 token 数量 "
                    "和 chunk 数量不一致"
                )


        except (
            json.JSONDecodeError,
            OSError,
            UnicodeError,
        ):

            tokenized_corpus = None

            print(
                "[CACHE INVALID] "
                "heading bm25 tokens corrupted"
            )


    # --------------------------------------------------------
    # Cache MISS
    # --------------------------------------------------------

    if tokenized_corpus is None:

        print(
            "[CACHE MISS] "
            "heading bm25 tokens"
        )

        print(
            f"Tokenizing "
            f"{len(chunks)} heading-aware chunks..."
        )


        tokenized_corpus = [
            tokenize(
                chunk["retrieval_text"]
            )
            for chunk in chunks
        ]


        HEADING_BM25_TOKENS_PATH.write_text(
            json.dumps(
                tokenized_corpus,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )


        print(
            "[CACHE SAVE] "
            "heading bm25 tokens: "
            f"{len(tokenized_corpus)}"
        )


    return BM25Okapi(
        tokenized_corpus
    )


# ============================================================
# Gold Evidence Match
# ============================================================

def normalize_text(text):

    return re.sub(
        r"\s+",
        " ",
        text,
    ).strip()


def find_matched_evidence(
    chunk,
    gold_evidence,
):
    """
    Gold Match 仍然只检查 content。

    heading_path 是 Retrieval Context，
    不能算作 Gold Evidence。
    """

    matched_ids = []

    chunk_text = normalize_text(
        chunk["content"]
    )

    chunk_file = Path(
        chunk["source"]
    ).name


    for evidence in gold_evidence:

        if (
            chunk_file
            != evidence["document"]
        ):
            continue


        evidence_text = normalize_text(
            evidence["evidence"]
        )


        if evidence_text in chunk_text:

            matched_ids.append(
                evidence["evidence_id"]
            )


    return matched_ids


# ============================================================
# Candidate Evaluation
# ============================================================

def evaluate_candidates(
    indices,
    chunks,
    gold_evidence,
):

    gold_ids = {
        evidence["evidence_id"]
        for evidence in gold_evidence
    }


    matched_ids = set()


    for index in indices:

        chunk = chunks[
            int(index)
        ]


        matched_ids.update(
            find_matched_evidence(
                chunk,
                gold_evidence,
            )
        )


    hit = (
        1
        if matched_ids
        else 0
    )


    recall = (
        len(matched_ids)
        / len(gold_ids)
        if gold_ids
        else 0.0
    )


    return {
        "hit":
            hit,

        "recall":
            recall,

        "matched_evidence_ids":
            sorted(
                matched_ids
            ),
    }


# ============================================================
# Summary
# ============================================================

def summarize(
    traces,
):

    count = len(traces)


    if count == 0:
        return {}


    strategies = [
        "bm25_top20",
        "dense_top20",
        "rrf_top20",
    ]


    result = {
        "question_count":
            count
    }


    for strategy in strategies:

        result[strategy] = {

            "hit_rate":
                sum(
                    trace[
                        strategy
                    ]["hit"]
                    for trace
                    in traces
                )
                / count,

            "recall":
                sum(
                    trace[
                        strategy
                    ]["recall"]
                    for trace
                    in traces
                )
                / count,
        }


    return result


# ============================================================
# Main
# ============================================================

def main():

    print()
    print("=" * 70)
    print(
        "E4 HEADING-AWARE "
        "TOP20 RETRIEVAL EVALUATION"
    )
    print("=" * 70)


    # --------------------------------------------------------
    # 1. Heading-aware Chunks
    # --------------------------------------------------------

    documents, chunks = (
        load_and_chunk_corpus()
    )


    print(
        f"Documents: "
        f"{len(documents)}"
    )

    print(
        f"Chunks: "
        f"{len(chunks)}"
    )


    # --------------------------------------------------------
    # 2. Heading Corpus Embeddings
    # --------------------------------------------------------

    chunk_vectors = (
        load_or_create_heading_embeddings(
            chunks
        )
    )


    # --------------------------------------------------------
    # 3. Benchmark
    # --------------------------------------------------------

    questions = (
        load_answerable_benchmark()
    )


    print(
        f"Answerable Questions: "
        f"{len(questions)}"
    )


    # --------------------------------------------------------
    # 4. Benchmark Embedding
    #
    # 直接复用原 Cache
    # 不重新调用 Embedding API
    # --------------------------------------------------------

    question_ids, query_vectors = (
        load_or_create_benchmark_embeddings(
            questions
        )
    )


    print(
        "[CACHE HIT] "
        "benchmark embeddings: "
        f"{query_vectors.shape}"
    )


    query_vector_map = {

        question_id:
            query_vectors[index]

        for index, question_id
        in enumerate(
            question_ids
        )
    }


    # --------------------------------------------------------
    # 5. Heading-aware BM25
    # --------------------------------------------------------

    print(
        "Building heading-aware BM25 index..."
    )


    bm25 = build_heading_bm25(
        chunks
    )


    # --------------------------------------------------------
    # 6. Evaluation
    # --------------------------------------------------------

    traces = []


    for number, question in enumerate(
        questions,
        start=1,
    ):

        question_id = (
            question["id"]
        )

        query = (
            question["question"]
        )

        query_vector = (
            query_vector_map[
                question_id
            ]
        )


        print(
            f"[{number}/{len(questions)}] "
            f"{question_id}"
        )


        # ====================================================
        # BM25 Top20
        # ====================================================

        bm25_scores = bm25.get_scores(
            tokenize(query)
        )


        bm25_indices = np.argsort(
            bm25_scores
        )[::-1][:TOP_K]


        # ====================================================
        # Dense Top20
        # ====================================================

        dense_scores = cosine_similarity(
            query_vector,
            chunk_vectors,
        )


        dense_indices = np.argsort(
            dense_scores
        )[::-1][:TOP_K]


        # ====================================================
        # RRF Top20
        #
        # BM25 Top20
        # +
        # Dense Top20
        # ↓
        # Union
        # ↓
        # RRF
        # ↓
        # Top20
        # ====================================================

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


        rrf_indices = [
            int(chunk_index)
            for chunk_index, _
            in ranked[:TOP_K]
        ]


        # ====================================================
        # Metrics
        # ====================================================

        bm25_result = evaluate_candidates(
            bm25_indices,
            chunks,
            question[
                "gold_evidence"
            ],
        )


        dense_result = evaluate_candidates(
            dense_indices,
            chunks,
            question[
                "gold_evidence"
            ],
        )


        rrf_result = evaluate_candidates(
            rrf_indices,
            chunks,
            question[
                "gold_evidence"
            ],
        )


        # ====================================================
        # Trace
        # ====================================================

        traces.append(
            {
                "id":
                    question_id,

                "question":
                    query,

                "question_type":
                    question[
                        "question_type"
                    ],

                "hop_type":
                    question[
                        "hop_type"
                    ],

                "gold_evidence_ids": [
                    evidence[
                        "evidence_id"
                    ]
                    for evidence
                    in question[
                        "gold_evidence"
                    ]
                ],


                # --------------------------------------------
                # BM25
                # --------------------------------------------

                "bm25_top20": {

                    **bm25_result,

                    "chunk_ids": [
                        chunks[int(i)][
                            "chunk_id"
                        ]
                        for i
                        in bm25_indices
                    ],
                },


                # --------------------------------------------
                # Dense
                # --------------------------------------------

                "dense_top20": {

                    **dense_result,

                    "chunk_ids": [
                        chunks[int(i)][
                            "chunk_id"
                        ]
                        for i
                        in dense_indices
                    ],
                },


                # --------------------------------------------
                # RRF
                # --------------------------------------------

                "rrf_top20": {

                    **rrf_result,

                    "chunk_ids": [
                        chunks[int(i)][
                            "chunk_id"
                        ]
                        for i
                        in rrf_indices
                    ],
                },
            }
        )


    # --------------------------------------------------------
    # 7. 分组
    # --------------------------------------------------------

    single_traces = [
        trace
        for trace in traces
        if trace["hop_type"]
        == "single"
    ]


    multi_traces = [
        trace
        for trace in traces
        if trace["hop_type"]
        == "multi"
    ]


    cross_document_traces = [
        trace
        for trace in traces
        if trace["question_type"]
        == "cross_document"
    ]


    # --------------------------------------------------------
    # 8. Summary
    # --------------------------------------------------------

    summary = {

        "experiment":
            "E4-Heading-Aware-Top20",

        "chunking":
            (
                "heading-aware + "
                "recursive500_o100"
            ),

        "chunk_count":
            len(chunks),

        "embedding_input":
            "heading_path + content",

        "bm25_input":
            "heading_path + content",

        "top_k":
            TOP_K,

        "rrf_k":
            RRF_K,


        "overall":
            summarize(
                traces
            ),

        "single":
            summarize(
                single_traces
            ),

        "multi":
            summarize(
                multi_traces
            ),

        "cross_document":
            summarize(
                cross_document_traces
            ),
    }


    # --------------------------------------------------------
    # 9. 保存
    # --------------------------------------------------------

    RUN_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )


    with (
        RUN_DIR
        / "trace.jsonl"
    ).open(
        "w",
        encoding="utf-8",
    ) as f:

        for trace in traces:

            f.write(
                json.dumps(
                    trace,
                    ensure_ascii=False,
                )
                + "\n"
            )


    with (
        RUN_DIR
        / "summary.json"
    ).open(
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            summary,
            f,
            ensure_ascii=False,
            indent=2,
        )


    # --------------------------------------------------------
    # 10. Console
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print(
        "HEADING-AWARE TOP20 RESULT"
    )
    print("=" * 70)


    for group_name in [
        "overall",
        "single",
        "multi",
        "cross_document",
    ]:

        group = summary[
            group_name
        ]


        print()
        print(
            f"[{group_name.upper()}]"
        )

        print(
            f"Questions: "
            f"{group['question_count']}"
        )


        for strategy in [
            "bm25_top20",
            "dense_top20",
            "rrf_top20",
        ]:

            result = group[
                strategy
            ]


            print()
            print(
                strategy
            )

            print(
                "  Hit Rate: "
                f"{result['hit_rate']:.4f}"
            )

            print(
                "  Recall:   "
                f"{result['recall']:.4f}"
            )


    print()

    print(
        f"结果已保存到: "
        f"{RUN_DIR}"
    )


if __name__ == "__main__":
    main()