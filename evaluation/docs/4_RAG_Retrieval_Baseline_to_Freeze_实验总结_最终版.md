# RAG Retrieval 实验总结：Baseline → Freeze

> 目标：在固定 Benchmark 下，用尽量少的实验回答“哪些改动真正提升 Retrieval”，并在效果、Token 成本和延迟之间做工程取舍。

---

## 1. 从 Reranker 继续往下：先做小诊断

在 Recursive Chunking 下：

```text
BM25 Top20 + Dense Top20
→ RRF Top20
→ Reranker
→ Top5
```

Overall Recall@5 已达到 **89.26%**。

随后对失败样本做诊断：

| 项目 | 数量 |
|---|---:|
| complete | 38 |
| candidate_miss | 5 |
| reranker_miss | 2 |
| Gold Evidence 总数 | 73 |
| Candidate Miss Evidence | 8 |
| Reranker Miss Evidence | 3 |

进一步检查 8 条 Candidate Miss：

```text
retrieval_miss = 4
fusion_miss    = 4
```

结论：

> RRF Top20 会丢掉一部分已经被 BM25 或 Dense 找到的候选，因此 RRF 的“候选压缩”可能损害 Recall。

### 小规模 Raw Union Probe

对存在 `fusion_miss` 的 3 道题测试：

```text
BM25 Top20 ∪ Dense Top20
→ 不做 RRF 截断
→ 直接 Reranker
→ Top5
```

结果：

- 4 条 `fusion_miss` Gold Evidence 在 Raw Union 候选阶段全部恢复；
- 最终 Top5 恢复 2/4；
- 候选池从固定 20 增加到约 34。

这个 Probe 证明了 RRF 确实会造成候选损失，但当时不足以判断全量 Benchmark 上的最终收益，因此没有立即修改主 Pipeline。

---

## 2. 从源头优化：Heading-aware Chunking

相比继续扩大候选池，先尝试从 Chunking 提升 Candidate Quality。

实现：

```text
Markdown
↓
按标题层级划分 Section
↓
Section 内 Recursive 500/100
↓
Chunk 继承 heading_path
↓
heading_path + content
用于 BM25 / Embedding / Reranker
↓
content
用于 Evidence Match / Citation
```

Heading-aware：

```text
Chunks = 469
Gold Evidence Coverage = 73/73 = 100%
```

原 Recursive：

```text
Chunks = 317
Gold Evidence Coverage = 73/73 = 100%
```

### Candidate Top20 对比

| Retriever | Recursive Recall@20 | Heading-aware Recall@20 | 变化 |
|---|---:|---:|---:|
| BM25 | 85.93% | 85.04% | -0.89pp |
| Dense | 89.63% | 92.96% | +3.33pp |
| RRF | 91.85% | **95.93%** | **+4.08pp** |

核心结论：

> **在 Candidate K 固定为 20、不增加 Reranker 候选预算的情况下，Heading-aware 提高了候选质量。**

因此继续验证 Heading-aware 是否能把 Candidate 阶段的收益传递到 Final Top5。

---

## 3. Heading-aware + Reranker

保持相同 Reranker Candidate Budget：

```text
Dense Top20 → Reranker → Top5
RRF Top20   → Reranker → Top5
```

| Pipeline | Recall@5 | MRR@5 |
|---|---:|---:|
| Recursive Dense20 → Rerank5 | 84.81% | 72.67% |
| Recursive RRF20 → Rerank5 | 89.26% | 76.93% |
| Heading Dense20 → Rerank5 | 88.15% | 75.26% |
| **Heading RRF20 → Rerank5** | **90.74%** | **77.48%** |

Heading-aware 在固定 Top20 预算下最终仍然有效：

```text
Recall@5
89.26% → 90.74%
+1.48pp

MRR@5
76.93% → 77.48%
+0.56pp
```

但 Candidate Recall@20 的提升为 +4.08pp，而 Final Recall@5 只提升 +1.48pp，说明新增候选收益没有全部通过 Reranker 保留下来。

---

## 4. 最后验证：完整 Raw Union Benchmark

为了把 RRF 的取舍彻底量化，最终又完整跑了两组：

```text
A. Recursive
BM25 Top20 ∪ Dense Top20
→ Raw Union
→ Reranker
→ Top5

B. Heading-aware
BM25 Top20 ∪ Dense Top20
→ Raw Union
→ Reranker
→ Top5
```

### Overall

| Chunking | Candidate 策略 | 平均 Reranker 候选数 | Recall@5 | MRR@5 |
|---|---|---:|---:|---:|
| Recursive | RRF Top20 | 20 | 89.26% | 76.93% |
| **Recursive** | **Raw Union** | **31.71** | **91.48%** | 77.07% |
| Heading-aware | RRF Top20 | 20 | 90.74% | **77.48%** |
| Heading-aware | Raw Union | 30.69 | 90.74% | 76.70% |

### 结果 1：Recursive 下去掉 RRF 确实提高 Recall

```text
Recall@5
89.26% → 91.48%
+2.22pp

Reranker 平均候选数
20 → 31.71
+58.6%
```

说明：

> RRF Top20 的候选压缩确实存在 Recall 损失。

但换来的代价是 Reranker 输入规模明显增加，而 MRR 仅从 76.93% 提升到 77.07%。

### 结果 2：Heading-aware 下 Raw Union 没有额外收益

```text
RRF20:
Recall@5 = 90.74%
MRR@5    = 77.48%

Raw Union:
Recall@5 = 90.74%
MRR@5    = 76.70%
```

候选数：

```text
20 → 30.69
```

Recall 完全不变，MRR 反而下降。

因此：

> Heading-aware 的主要价值，是在固定候选预算下提高 Candidate Quality；当候选池放宽到 Raw Union 后，它相对普通 Recursive 的优势基本消失。

---

## 5. Baseline → Freeze 完整实验路线

| 阶段 | Pipeline | 关键指标 |
|---|---|---:|
| E0 Baseline | Recursive 500/100 + BM25 Top5 | Recall@5 **60.74%**, MRR@5 **34.59%** |
| E1 Dense | Recursive + Dense Top5 | Recall@5 **75.19%**, MRR@5 **52.85%** |
| E2 RRF Final | Recursive + RRF Top5 | Recall@5 **71.85%**, MRR@5 **55.15%** |
| E2 Candidate Check | Recursive + RRF Top20 | Candidate Recall@20 **91.85%** |
| E3 Reranker | Recursive + RRF20 → Rerank5 | Recall@5 **89.26%**, MRR@5 **76.93%** |
| E4 Heading Candidate | Heading-aware + RRF Top20 | Candidate Recall@20 **95.93%** |
| E4 Heading Final | Heading-aware + RRF20 → Rerank5 | Recall@5 **90.74%**, MRR@5 **77.48%** |
| E5 Raw Union | Recursive + Raw Union → Rerank5 | **Recall@5 91.48%**, MRR@5 77.07% |
| E5 Raw Union | Heading-aware + Raw Union → Rerank5 | Recall@5 90.74%, MRR@5 76.70% |

> Candidate Recall@20 与 Final Recall@5 是不同指标，不能直接横向当作同一个分数比较。

---

## 6. 最终工程取舍

最高 Recall 的方案：

```text
Recursive
→ BM25 Top20 ∪ Dense Top20
→ Raw Union（平均 31.71 candidates）
→ Reranker
→ Top5

Recall@5 = 91.48%
MRR@5    = 77.07%
```

最终 Freeze 的方案：

```text
Heading-aware Section
→ Section 内 Recursive 500/100
→ heading_path + content
→ BM25 Top20 + Dense Top20
→ RRF Top20
→ Reranker
→ Top5

Recall@5 = 90.74%
MRR@5    = 77.48%
```

选择 Freeze 方案的原因：

- 只比最高 Recall 低 **0.74pp**；
- Reranker 候选从平均 **31.71** 压缩到固定 **20**；
- 候选规模减少约 **36.9%**；
- MRR@5 反而略高：**77.48% vs 77.07%**；
- Heading-aware 在固定 Candidate K=20 时明显提高 Candidate Recall；
- 更符合 Demo 对效果、Token 成本和延迟的综合要求。

最终结论：

> **Raw Union 可以获得最高 Recall，但需要显著扩大 Reranker 输入，带来的recall@5提升有限（仅为+0.74pp），且MRR甚至降低；Heading-aware + RRF Top20 仅牺牲 0.74pp Recall，就把候选规模从平均 31.71 压缩到 20，候选规模减少了约 36.9%,显著降低了rerank阶段的tokens开销,并同时保持更高的 MRR，因此作为最终 Retrieval Pipeline。**

Retrieval 阶段到此 Freeze，不再继续针对 RRF、Union 或 Chunking 做追加优化。

---

## 7. 数据来源

### E0 Baseline

```text
evaluation/runs/retrieval/e0_bm25_recursive500_o100/
```

### E1 Dense

```text
evaluation/runs/retrieval/e1_dense_qwen_recursive500_o100/
```

### E2 Hybrid / RRF

```text
evaluation/runs/retrieval/e2_hybrid_rrf_recursive500_o100/
```

### E2 Candidate Top20

```text
evaluation/runs/retrieval/e2_top20recall_check/
```

### E3 Recursive Reranker A/B

```text
evaluation/runs/retrieval/e3_rerank_ab/
```

### E3 Reranker Error Check

```text
evaluation/runs/retrieval/e3_rerank_error_analysis/
```

### E3 Candidate Miss Check

```text
evaluation/runs/retrieval/e3_candidate_miss_check/
```

### E3 Raw Union Probe

```text
evaluation/runs/retrieval/e3_union_rerank_probe/
```

### E4 Heading-aware Candidate

```text
evaluation/runs/retrieval/e4_heading_top20recall_check/
```

### E4 Heading-aware Reranker A/B

```text
evaluation/runs/retrieval/e4_heading_rerank_ab/
```

### E5 Full Raw Union Benchmark

```text
evaluation/runs/retrieval/e5_union_rerank/
```

其中最终 E5 数据：

```text
Recursive Raw Union
avg candidates = 31.71
Recall@5       = 91.48%
MRR@5          = 77.07%

Heading Raw Union
avg candidates = 30.69
Recall@5       = 90.74%
MRR@5          = 76.70%
```
