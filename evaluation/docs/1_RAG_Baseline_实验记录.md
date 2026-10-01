# RAG Baseline 阶段实验记录

## 1. 实验目的

建立一个简单、可复现的 BM25 检索 Baseline，用于后续 Dense Retrieval、Hybrid Retrieval、Reranker 等方案的对比。

Benchmark：`benchmark/benchmark_v1.jsonl`

本阶段仅统计 45 条 `answerable=true` 的问题，主要指标为：

- Hit@1 / Hit@3 / Hit@5
- Recall@1 / Recall@3 / Recall@5
- MRR@5

---

## 2. Baseline V0-A：Fixed Window 500/100 + BM25

Chunking：

- 固定字符窗口
- `chunk_size = 500`
- `chunk_overlap = 100`

Retrieval：

- jieba 中文分词
- BM25
- Top-K = 5

主要结果：

| 分组 | Hit@5 | Recall@5 | MRR@5 |
|---|---:|---:|---:|
| Overall | 60.00% | 58.52% | 36.07% |
| Single | 69.23% | 69.23% | 43.08% |
| Multi | 47.37% | 43.86% | 26.49% |
| Cross-document | 28.57% | 28.57% | 28.57% |

Gold Evidence Chunk Coverage：

- 语料被切成 292 个 chunks
- 69 / 73
- 94.52%
- 有 4 条 Gold Evidence 未被任何单个 Chunk 完整覆盖

数据来源：

`evaluation/runs/retrieval/e0_bm25_fixed500_o100/summary.json`

Chunk Coverage 由：

`python -m evaluation.retrieval.0_chunk_coverage`

在 `1_fixed_chunker.py` 配置下运行得到。

---

## 3. Baseline V0-B：Recursive Character 500/100 + BM25

Chunking：

- Recursive Character Chunking
- `chunk_size = 500`
- `chunk_overlap = 100`
- 优先按段落、换行、句号、分号、逗号等自然边界切分

Retrieval：

- jieba 中文分词
- BM25
- Top-K = 5

主要结果：

| 分组 | Hit@5 | Recall@5 | MRR@5 |
|---|---:|---:|---:|
| Overall | 64.44% | 60.74% | 34.59% |
| Single | 73.08% | 73.08% | 38.08% |
| Multi | 52.63% | 43.86% | 29.82% |
| Cross-document | 57.14% | 42.86% | 42.86% |

Gold Evidence Chunk Coverage：

- 语料被切成 317 个 chunks
- 73 / 73
- 100%

数据来源：

`evaluation/runs/retrieval/e0_bm25_recursive500_o100/summary.json`

Chunk Coverage 由：

`python -m evaluation.retrieval.0_chunk_coverage`

在 `2_recursive_chunker.py` 配置下运行得到。

---

## 4. 简单分析

两个版本在不同问题类型上的 BM25 检索表现存在差异。

相较纯 Fixed Window：

- Recursive Chunking 的 Overall Hit@5 从 60.00% 提升到 64.44%
- Overall Recall@5 从 58.52% 提升到 60.74%
- Cross-document Recall@5 从 28.57% 提升到 42.86%
- MRR@5 没有整体提升，Overall 从 36.07% 降至 34.59%
- Multi Recall@5 保持 43.86%

Chunk Coverage 方面，Fixed Window 把语料切成 292 个 chunks，完整覆盖 69/73（94.52%）。Recursive Chunking 切成 317 个 chunks，覆盖 73/73（100%），避免了部分 Gold Evidence 被固定字符边界切断。

---

## 5. Baseline 最终选择

正式 Baseline 采用：

```text
Recursive Character Chunking 500/100
+ jieba
+ BM25
+ Top-K = 5
```

理由：

- 相比纯 Fixed Window，更能保持证据完整性
- Gold Evidence Chunk Coverage 达到 100%
- Overall Hit@5、Recall@5 以及 Cross-document Recall@5 更高
- 仍然保持实现简单，适合作为后续检索优化的参照组

后续实验保持当前 Chunking 配置不变，只替换 Retrieval 策略，以保证变量控制。
