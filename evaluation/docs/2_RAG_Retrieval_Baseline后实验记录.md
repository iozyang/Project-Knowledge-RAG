# RAG Retrieval：Baseline 之后的实验记录

> 用途：快速回顾 Baseline 之后的检索实验走向、关键结论与数据来源。  
> 本文只记录实验过程与客观结果，不展开详细原理。

---

## 0. 起点：正式 Baseline

正式 Baseline：

```text
Recursive Character Chunking 500/100
+ jieba
+ BM25
+ Top5
```

关键结果：

- Overall Recall@5：60.74%
- Overall MRR@5：34.59%
- Gold Evidence Chunk Coverage：100%

数据来源：

```text
evaluation/runs/retrieval/e0_bm25_recursive500_o100/summary.json
evaluation/runs/retrieval/e0_bm25_recursive500_o100/trace.jsonl
```

Baseline 详细记录另见：`RAG_Baseline_实验记录.md`

---

## 1. E1：Qwen Dense Retrieval

### 实验变化

保持不变：

- Recursive Character Chunking 500/100
- Benchmark v1
- 45 条 answerable 问题
- Top5
- Gold Evidence 匹配规则

唯一主要变化：

```text
BM25
→
Qwen Dense Retrieval
```

Embedding：

```text
qwen3.7-text-embedding
dimensions = 1024
similarity = cosine
```

### 结果

| 分组 | Recall@5 | MRR@5 |
|---|---:|---:|
| Overall | 75.19% | 52.85% |
| Single | 88.46% | 62.50% |
| Multi | 57.02% | 39.65% |
| Cross-document | 50.00% | 40.48% |

相对 Baseline：

- Overall Recall@5：60.74% → 75.19%
- Overall MRR@5：34.59% → 52.85%

结论：Dense Retrieval 在当前 Benchmark 上明显优于 BM25。

数据来源：

```text
evaluation/runs/retrieval/e1_dense_qwen_recursive500_o100/summary.json
evaluation/runs/retrieval/e1_dense_qwen_recursive500_o100/trace.jsonl
```

---

## 2. BM25 vs Dense Trace Analysis

在进入 Hybrid 前，对 BM25 与 Dense 的 Top5 trace 做互补性检查。

按“题目是否至少命中一个 Gold Evidence”统计：

| 情况 | 题数 |
|---|---:|
| 两者都命中 | 25 |
| 仅 BM25 命中 | 4 |
| 仅 Dense 命中 | 12 |
| 两者都未命中 | 4 |

按 Gold Evidence 统计：

| 情况 | Evidence 数 |
|---|---:|
| 两者都能找到 | 29 |
| 仅 BM25 能找到 | 11 |
| 仅 Dense 能找到 | 19 |
| 两者都找不到 | 14 |

观察：

- Dense 整体更强。
- BM25 仍能补回部分 Dense 漏掉的证据。
- 精确字段名、代码标识符等查询中，BM25 有时具有优势。
- 因此有理由验证 Hybrid Retrieval，而不是直接放弃 BM25。

数据来源：

```text
evaluation/runs/retrieval/e0_bm25_recursive500_o100/trace.jsonl
evaluation/runs/retrieval/e1_dense_qwen_recursive500_o100/trace.jsonl
```

---

## 3. E2：BM25 + Dense + RRF Hybrid

### 实验结构

```text
BM25 Top20
+
Dense Top20
↓
Union 去重
↓
RRF（k=60）
↓
Final Top5
```

RRF 只使用两路排名，不直接混合 BM25 score 与 cosine score。

### Final Top5 结果

| 指标 | Dense Top5 | RRF Hybrid Top5 |
|---|---:|---:|
| Overall Recall@5 | 75.19% | 71.85% |
| Overall MRR@5 | 52.85% | 55.15% |

观察：

- RRF 的 MRR@5 小幅提高。
- 但 Recall@5 从 75.19% 降到 71.85%。
- Hybrid 没有在 Final Top5 上超过 Dense。
- Multi / Cross-document 的最终 Recall 也没有得到预期提升。

因此不能直接把 RRF 当作最终排序器。

数据来源：

```text
evaluation/runs/retrieval/e2_hybrid_rrf_recursive500_o100/summary.json
evaluation/runs/retrieval/e2_hybrid_rrf_recursive500_o100/trace.jsonl
```

---

## 4. E2 辅助实验：Top20 Candidate Recall Check

目的：

判断 Hybrid 的问题是：

```text
候选阶段没有找到 Gold
```

还是：

```text
Gold 已进入较大候选集
但 RRF Final Top5 排序不理想
```

最终采用固定相同候选预算的公平比较：

```text
BM25-only Top20
Dense-only Top20
RRF(BM25 Top20 + Dense Top20) Top20
```

### Overall

| 策略 | Hit Rate | Recall |
|---|---:|---:|
| BM25 Top20 | 91.11% | 85.93% |
| Dense Top20 | 95.56% | 89.63% |
| RRF Top20 | 95.56% | 91.85% |

### 分组 Recall

| 分组 | BM25 Top20 | Dense Top20 | RRF Top20 |
|---|---:|---:|---:|
| Single | 92.31% | 96.15% | 96.15% |
| Multi | 77.19% | 80.70% | 85.96% |
| Cross-document | 76.19% | 85.71% | 85.71% |

主要观察：

- 相同 Top20 候选预算下，RRF Overall Recall 最高：91.85%。
- RRF 相比 Dense Top20 提升约 2.22 个百分点。
- 提升主要来自 Multi-evidence：80.70% → 85.96%。
- Single 基本没有增益。
- Cross-document Recall 与 Dense 持平，但 Hit Rate 存在个别退化。

结论：

```text
RRF 作为 Candidate Generator 有一定价值
但 RRF 作为 Final Top5 Ranker 表现不够好
```

数据来源：

```text
evaluation/runs/retrieval/e2_top20recall_check/summary.json
evaluation/runs/retrieval/e2_top20recall_check/trace.jsonl
```

### 方法修正记录

曾检查过：

```text
BM25 Top20 ∪ Dense Top20
```

原始 Union 平均约 31.7 个候选，Recall 很高，但它与固定 Top20 的 Dense / RRF 候选数量不同，因此不能直接作为公平对比指标。

后续正式诊断改为固定：

```text
20 vs 20 vs 20
```

---

## 5. 当前下一步：Reranker

当前实验动机：

```text
RRF Top20 Recall = 91.85%
RRF Top5 Recall = 71.85%
```

说明较多 Gold Evidence 已经进入候选集，但没有稳定进入最终 Top5。

因此下一步验证 Reranker 是否能够改善最终排序。

计划做两个控制实验：

```text
A. Dense Top20
   → Reranker
   → Top5

B. RRF Top20
   → 同一个 Reranker
   → Top5
```

比较：

- Hit@1 / Hit@3 / Hit@5
- Recall@1 / Recall@3 / Recall@5
- MRR@5
- Single / Multi / Cross-document

目的：

判断 Hybrid 多出来的 Candidate Recall，能否通过 Reranker 转化为最终 Top5 的实际收益。

如果两者最终效果接近，则优先保留更简单的 Dense Top20 → Reranker；如果 RRF Top20 → Reranker 明显更好，则保留 Hybrid Candidate Generation。

---

## 6. 当前 Retrieval 主线

```text
E0  BM25 Baseline
↓
E1  Dense Retrieval
↓
Trace Error Analysis
↓
E2  BM25 + Dense + RRF
↓
Top20 Candidate Recall Check
↓
E3  Reranker A/B
    Dense Top20 vs RRF Top20
↓
后续再评估 Heading-aware Chunking
↓
Freeze Best Retrieval Pipeline
↓
进入 Generation
```

当前原则：

- 不围绕单个 Query 调参。
- 固定 Benchmark 做回归。
- 一次尽量只改变一个主要变量。
- 新技术只有在实验暴露明确问题后再引入。
