# RAG Retrieval：Reranker 阶段实验记录

> 用途：记录 Reranker 阶段的实验动机、实验设计、过程、关键数据与阶段结论，便于后续快速回顾。  
> 本文承接 `RAG_Retrieval_Baseline后实验记录.md`，只记录本阶段新增内容。

---

## 1. 实验背景

在前一阶段，Hybrid Retrieval 使用：

```text
BM25 Top20
+
Dense Top20
↓
Union 去重
↓
RRF（k=60）
↓
Top20 / Top5
```

已经得到两个关键现象。

### 1.1 RRF Top20 的 Candidate Recall 更高

固定候选预算为 20 时：

| 策略 | Overall Hit Rate | Overall Recall |
|---|---:|---:|
| BM25 Top20 | 91.11% | 85.93% |
| Dense Top20 | 95.56% | 89.63% |
| RRF Top20 | 95.56% | 91.85% |

其中 Multi-evidence Recall：

```text
BM25 Top20  = 77.19%
Dense Top20 = 80.70%
RRF Top20   = 85.96%
```

说明 RRF 确实能把 BM25 与 Dense 的互补证据保留下来。

### 1.2 但 RRF Final Top5 并没有更好

此前 Final Top5：

```text
Dense Top5 Recall@5 = 75.19%
RRF Top5 Recall@5   = 71.85%
```

因此问题已经从“有没有召回”变成：

```text
Gold Evidence 已进入 RRF Top20
但 RRF 本身不擅长把它们稳定排进最终 Top5
```

这构成了引入 Reranker 的直接实验动机。

---

## 2. 实验目标

本阶段验证两个问题：

### Q1

Reranker 能否把 Top20 候选中的 Gold Evidence 更稳定地推入 Final Top5？

### Q2

RRF Top20 相比 Dense Top20 多出来的 Candidate Recall，能否真正转化为最终 Top5 的收益？

因此设计两个严格控制的 A/B Pipeline：

```text
A. Dense Top20
   → Qwen Reranker
   → Top5

B. RRF Top20
   → Qwen Reranker
   → Top5
```

两条链使用：

- 相同 Corpus
- 相同 Recursive Chunking 500/100
- 相同 Benchmark v1
- 相同 Dense Embedding
- 相同 Reranker
- 相同 Candidate K = 20
- 相同 Final K = 5

唯一主要差异是 Reranker 的候选输入来源。

---

## 3. 工程优化：缓存固定实验输入

正式跑 Reranker Eval 前，为避免重复切片和重复 Embedding，增加了简单缓存：

```text
cache/
├─ corpus_chunks.jsonl
├─ corpus_embeddings.npy
└─ benchmark_embeddings.npz
```

分别缓存：

1. Corpus 的 Recursive 500/100 切片结果
2. 317 个 Corpus Chunk 的 Embedding
3. 45 道 answerable Benchmark Query 的 Embedding

因此正式 Eval 中：

```text
Corpus Chunking         = 0 次重复执行
Corpus Embedding API    = 0 次
Benchmark Embedding API = 0 次
```

本阶段新增 API 成本主要来自 Reranker。

---

## 4. Reranker Probe

先实现：

```text
src/retrieval/4_rerank_retriever.py
```

输入：

```text
Query
+
Candidate Chunk Indices
```

处理：

```text
Candidate Top20
→ qwen3.7-text-rerank
→ relevance_score
→ Top5
```

Probe 跑通后，再进入正式 Benchmark。

---

## 5. 正式 Eval

文件：

```text
evaluation/retrieval/4_rerank_eval.py
```

Run：

```text
evaluation/runs/retrieval/e3_rerank_ab/
├─ summary.json
└─ trace.jsonl
```

正式比较：

```text
dense_top20_rerank_top5
rrf_top20_rerank_top5
```

Benchmark：

```text
45 条 answerable questions
```

指标：

- Hit Rate@1
- Hit Rate@3
- Hit Rate@5
- Recall@1
- Recall@3
- Recall@5
- MRR@5

并继续分组观察：

- Overall
- Single
- Multi
- Cross-document

---

## 6. Overall 结果

| Pipeline | Hit@1 | Recall@1 | Hit@3 | Recall@3 | Hit@5 | Recall@5 | MRR@5 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Dense20 → Rerank5 | 60.00% | 54.44% | 82.22% | 74.44% | 93.33% | 84.81% | 72.67% |
| RRF20 → Rerank5 | **64.44%** | **58.89%** | **86.67%** | **78.89%** | **95.56%** | **89.26%** | **76.93%** |

RRF20 → Rerank5 相比 Dense20 → Rerank5：

```text
Recall@5：84.81% → 89.26%   +4.44pp
Hit@5：   93.33% → 95.56%   +2.22pp
MRR@5：   72.67% → 76.93%   +4.26pp
```

结论：

```text
Hybrid 多出来的 Candidate Recall
确实能被 Reranker 转化为最终 Top5 收益
```

---

## 7. Single 结果

| Pipeline | Recall@1 | Recall@3 | Recall@5 | MRR@5 |
|---|---:|---:|---:|---:|
| Dense20 → Rerank5 | 69.23% | 92.31% | 96.15% | 81.09% |
| RRF20 → Rerank5 | **73.08%** | 92.31% | 96.15% | **83.01%** |

观察：

- 两条 Pipeline 的 Recall@5 完全相同：96.15%
- RRF 的主要优势体现在更前面的排序位置
- Single 问题本身已经比较容易，Dense 候选已经足够强

因此 RRF 在 Single 上的增益有限。

---

## 8. Multi-evidence 结果

| Pipeline | Hit@1 | Recall@1 | Hit@3 | Recall@3 | Hit@5 | Recall@5 | MRR@5 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Dense20 → Rerank5 | 47.37% | 34.21% | 68.42% | 50.00% | 89.47% | 69.30% | 61.14% |
| RRF20 → Rerank5 | **52.63%** | **39.47%** | **78.95%** | **60.53%** | **94.74%** | **79.82%** | **68.60%** |

这是本阶段最重要的一组结果。

RRF20 → Rerank5 相比 Dense20 → Rerank5：

```text
Recall@5：69.30% → 79.82%
提升：+10.53pp
```

说明前面 Candidate Recall Check 中观察到的：

```text
RRF 对 Multi-evidence 更有优势
```

经过 Reranker 后，已经成功转化为最终 Top5 收益。

---

## 9. Cross-document 结果

| Pipeline | Recall@1 | Recall@3 | Recall@5 | MRR@5 |
|---|---:|---:|---:|---:|
| Dense20 → Rerank5 | 30.95% | 59.52% | 71.43% | 71.43% |
| RRF20 → Rerank5 | 30.95% | **66.67%** | **78.57%** | 71.43% |

观察：

- RRF Top20 → Rerank 在 Recall@3 / Recall@5 上更好
- 但 Hit@5 两者都只有 85.71%
- 说明仍存在至少一道 Cross-document 问题，在 Candidate Top20 阶段就没有召回任何 Gold Evidence

因此：

```text
Reranker 只能重新排序已有候选
无法修复 Candidate Miss
```

---

## 10. 与前面 Retrieval 阶段的整体对比

当前主线关键节点：

| 阶段 | Overall Recall@5 | MRR@5 |
|---|---:|---:|
| BM25 Baseline | 60.74% | 34.59% |
| Dense Top5 | 75.19% | 52.85% |
| RRF Final Top5 | 71.85% | 55.15% |
| Dense20 → Rerank5 | 84.81% | 72.67% |
| **RRF20 → Rerank5** | **89.26%** | **76.93%** |

相比 Dense Top5：

```text
Recall@5：
75.19% → 89.26%
+14.07pp

MRR@5：
52.85% → 76.93%
+24.07pp
```

相比原始 BM25 Baseline：

```text
Recall@5：
60.74% → 89.26%
+28.52pp
```

---

## 11. Candidate Recall 与 Final Recall 的关系

此前：

```text
RRF Top20 Candidate Recall = 91.85%
```

加入 Reranker 后：

```text
RRF20 → Rerank5 Recall@5 = 89.26%
```

两者只相差约：

```text
2.59pp
```

这说明 Reranker 已经能够把 RRF Top20 中的大部分 Gold Evidence 保留到最终仅 5 个 Chunk 的上下文中。

这也是本阶段最关键的实验结果之一。

---

## 12. 阶段结论

当前表现最好的 Retrieval Pipeline：

```text
BM25 Top20
      \
       → RRF → Top20
      /
Dense Top20
        ↓
Qwen Reranker
        ↓
Final Top5
```

阶段结论：

1. Dense 整体强于 BM25，但 BM25 提供了部分 Dense 缺失的词法证据。
2. RRF Top20 的 Candidate Recall 高于 Dense Top20。
3. RRF 自己直接承担 Final Top5 排序时效果并不好。
4. Reranker 成功解决了“候选召回较好，但最终排序不足”的问题。
5. RRF20 → Rerank5 明显优于 Dense20 → Rerank5。
6. 提升主要来自 Multi-evidence 和部分 Cross-document 问题。
7. 当前主要剩余问题已经不再只是 Final Ranking，而需要进一步区分：
   - Candidate Miss
   - Reranker Miss

---

## 13. 当前实验链

```text
E0  Recursive + BM25 Baseline
↓
E1  Dense Retrieval
↓
BM25 / Dense Trace Analysis
↓
E2  BM25 + Dense + RRF
↓
发现 Final Top5 Recall 下降
↓
Top20 Candidate Recall Check
↓
发现 RRF Top20 Candidate Recall 更高
↓
E3  Reranker A/B
├─ Dense20 → Rerank5
└─ RRF20 → Rerank5
↓
RRF20 → Rerank5 当前最优
```

---

## 14. 数据来源

Baseline：

```text
evaluation/runs/retrieval/e0_bm25_recursive500_o100/
```

Dense：

```text
evaluation/runs/retrieval/e1_dense_qwen_recursive500_o100/
```

Hybrid RRF：

```text
evaluation/runs/retrieval/e2_hybrid_rrf_recursive500_o100/
```

Top20 Candidate Recall Check：

```text
evaluation/runs/retrieval/e2_top20recall_check/
```

Reranker A/B：

```text
evaluation/runs/retrieval/e3_rerank_ab/
├─ summary.json
└─ trace.jsonl
```

---

## 15. 下一步

不立即继续堆新模块。

下一步优先对：

```text
RRF Top20 → Rerank Top5
```

做 Error Analysis，重点区分：

```text
1. Candidate Miss
   Gold Evidence 根本没有进入 RRF Top20

2. Reranker Miss
   Gold Evidence 已经进入 RRF Top20
   但没有进入 Reranked Top5
```

再根据错误类型决定是否值得继续做：

```text
Heading-aware Chunking
```

而不是预先假设它一定有效。
