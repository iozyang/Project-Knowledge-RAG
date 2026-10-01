# RAG Generation Prompt 优化实验总结（E3 → E3.1）

## 1. 实验目的

E3 已经验证：在弱生成模型 `deepseek-r1-distill-qwen-7b` 上，单纯增加更严格的 Grounding / Abstention / Citation 规则，会出现明显的规则竞争。

因此 E3.1 不再继续增加规则，而是基于 E3 Failure Analysis 做一次 **Failure-driven Prompt Refinement（基于失败分析的 Prompt 修正）**。

固定条件：

- Benchmark：50 题（45 answerable + 5 unanswerable）
- Generator：`deepseek-r1-distill-qwen-7b`
- Retrieval Context：继续使用冻结的 `generation_contexts.jsonl`
- 异步 Generation / Evaluation 流程不变
- Gold Answer Points、Judge Prompt、Evidence Boundary 不变
- 主要变量：`G1 → G1.1`

---

## 2. E3：Strict Grounded Prompt

### 做了什么

G1 主要增加：

- 只能使用 Context
- 禁止外部知识和自行推测
- 证据不足时拒答
- 冲突信息不得自行选择
- 多子问题需要完整回答
- 关键事实要求 Citation
- 只输出合法 JSON

### 主要结果

| 指标 | E3 G1 |
|---|---:|
| Parse Success | 88% |
| Answer Correctness | 52.5% |
| CORRECT / PARTIAL / WRONG | 12 / 24 / 9 |
| Faithfulness | 76.35% |
| Unsupported Claim Rate | 23.65% |
| Unanswerable Abstention | 2 / 5 |
| False Abstention | 4 / 45 |
| Citation Accuracy | 100% |
| Citation Coverage | 7.01% |

### Failure Analysis

E3 暴露出三个主要问题：

1. **过度拒答**
   - 多个本来可以回答的问题因为证据不完整而直接拒答。

2. **规则竞争**
   - Grounding、拒答、完整性、Citation、JSON 等约束同时存在时，弱模型不能稳定兼顾全部规则。

3. **Citation 执行偏差**
   - 模型经常把 Citation 只放进 `citations` 数组，而没有放进 `answer` 正文。
   - 因此 Citation Accuracy 很高，但 Coverage 极低。

核心结论：

> 对弱模型来说，Prompt 约束并不是越严格越好。规则数量过多、拒答条件过强时，模型可能优先执行部分规则，从而牺牲回答完整性和引用覆盖。

数据来源：

- `evaluation/runs/generation/e3_prompt_optimized/summary.json`
- `evaluation/runs/generation/e3_prompt_optimized/eval_trace.jsonl`

---

## 3. E3.1：Refined Grounded Prompt

### 做了什么

E3.1 不新增复杂规则，而是减少和重排规则。

G1.1 主要调整：

- 有证据的部分优先回答；
- 只有核心信息完全无证据时才整体拒答；
- 不因为部分信息缺失而拒答整个问题；
- 冲突信息同时保留不同口径；
- Citation 必须直接出现在 `answer` 正文对应事实之后；
- `citations` 数组只做汇总；
- 强制只输出一个合法 JSON。

---

## 4. E3 → E3.1 数据对比

| 指标 | E3 G1 | E3.1 G1.1 | 变化 |
|---|---:|---:|---:|
| Parse Success | 88% | **94%** | ↑ |
| Answer Correctness | 52.5% | **59.72%** | ↑ |
| CORRECT | 12 | **13** | ↑ |
| PARTIAL | 24 | 28 | ↑ |
| WRONG | 9 | **4** | 明显下降 |
| Faithfulness | 76.35% | **78.37%** | ↑ |
| Unsupported Claim Rate | 23.65% | **21.63%** | ↓ |
| Unanswerable Abstention | 2/5 | 2/5 | 不变 |
| False Abstention | 4/45 | **3/45** | 改善 |
| Citation Accuracy | 100% | 67.68% | ↓ |
| Citation Coverage | 7.01% | **30.44%** | 明显恢复 |

E3.1 其他数据：

- Generator input tokens：56,203
- Generator output tokens：19,255
- Generator total tokens：75,458
- Eval wall time：205.80 s
- Eval throughput：14.58 questions/min
- Evaluation tokens：144,712

数据来源：

- `evaluation/runs/generation/e3_1_prompt_refined/summary.json`
- `evaluation/runs/generation/e3_1_prompt_refined/eval_trace.jsonl`

---

## 5. 当前结论

E3.1 证明 **减少规则、明确优先级** 是有效方向：

- JSON 稳定性继续提升；
- WRONG 从 9 降到 4；
- Correctness、Faithfulness 均有所恢复；
- False Abstention 减少；
- Citation Coverage 从 7.01% 恢复到 30.44%。

但 E3.1 仍未回到 G0 / E2 的 Answer Correctness 水平，说明问题已经不只是 Prompt 设计。

当前可以得到一个更完整的结论：

> 对 `deepseek-r1-distill-qwen-7b` 这类较弱生成模型，Prompt 简化能够缓解规则竞争，但无法完全解决多约束执行不稳定的问题。继续围绕固定 Benchmark 反复微调 Prompt，容易进入局部过拟合，收益开始下降。

因此到这里应停止继续细调 7B Prompt。

---

## 6. 下一步：E4 Generator Model Upgrade

E4 只改变一个主要变量：

```text
E3.1
Generator = deepseek-r1-distill-qwen-7b
Prompt    = G1.1
Contexts  = Frozen
Async     = Yes

              ↓ 只换 Generator

E4
Generator = qwen3.8-flash
Prompt    = G1.1
Contexts  = Frozen
Async     = Yes
```

目标：

> 验证在相同 Context、相同 G1.1 Prompt 和相同 Evaluation Framework 下，更强生成模型是否能够更稳定地同时执行 Grounding、Abstention、Citation 和 JSON 约束。

如果 E4 明显改善，则 Generation 阶段即可基本收束，选定最终 Generator，继续进入 API / Demo / MVP。
