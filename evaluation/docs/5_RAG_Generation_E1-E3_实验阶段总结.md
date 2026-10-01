# RAG Generation 实验阶段总结（E1–E3）

## 1. 实验目标

当前 Generation 实验主要验证两件事：

1. **工程性能**：同步调用是否可以通过异步化显著降低端到端耗时。
2. **回答质量**：在弱生成模型 `deepseek-r1-distill-qwen-7b` 上，增加 Grounding / Abstention / Citation 等 Prompt 约束是否能提升质量。

固定条件：

- Benchmark：50 题（45 answerable + 5 unanswerable）
- Retrieval Context：冻结的 `generation_contexts.jsonl`
- Generator：`deepseek-r1-distill-qwen-7b`
- Claim Splitter：`qwen3.8-flash`
- Judge：E1–E3 当前均使用 `qwen3.8-max`
- Gold Answer Points、Evidence Boundary、主要 Judge 规则保持不变

---

## 2. E1：Naive Baseline

### 做了什么

建立最朴素的 Generation Baseline：

- Generator：同步调用
- Judge：同步调用
- Prompt：`G0_naive`
- 只要求根据 Context 回答、尽量引用证据、输出 JSON
- 没有明确禁止外部知识
- 没有强制证据不足时拒答
- 没有专门设计冲突处理

### 主要结果

| 指标 | E1 |
|---|---:|
| Parse Success | 32% |
| Answer Correctness | 72.5% |
| Faithfulness | 78.29% |
| Unsupported Claim Rate | 21.71% |
| Citation Accuracy | 78.27% |
| Citation Coverage | 70.69% |
| Unanswerable Abstention | 0 / 5 |
| False Abstention | 0 / 45 |

工程性能：

| 项目 | E1 |
|---|---:|
| Generator Wall Time | 250.24 s |
| Generator Throughput | 11.99 q/min |
| Evaluator Wall Time | 736.34 s |
| Evaluator Throughput | 4.07 q/min |

### 简单分析

Baseline 能回答大部分可回答问题，但存在 JSON 输出不稳定、不可回答问题不会主动拒答、Unsupported Claim 和引用可靠性不足等问题。

### 数据来源

- `evaluation/runs/generation/e1_generation_baseline/generation_summary.json`
- `evaluation/runs/generation/e1_generation_baseline/summary.json`

---

## 3. E2：Async Engineering Optimization

### 做了什么

E2 不做质量优化，只做工程异步化：

- Generator：`OpenAI → AsyncOpenAI`
- Judge：`OpenAI → AsyncOpenAI`
- 并发数：3
- Prompt 仍为 `G0_naive`
- 模型、Context、Benchmark 不变

### 主要结果

Generator：

| 指标 | E1 Sync | E2 Async | 变化 |
|---|---:|---:|---:|
| Wall Time | 250.24 s | 88.47 s | **2.83× 加速** |
| Throughput | 11.99 | 33.91 q/min | 明显提升 |

Evaluator：

| 指标 | E1 Sync | E2 Async | 变化 |
|---|---:|---:|---:|
| Wall Time | 736.34 s | 239.28 s | **3.08× 加速** |
| Throughput | 4.07 | 12.54 q/min | 明显提升 |

E2 当前质量结果：

| 指标 | E2 |
|---|---:|
| Parse Success | 42% |
| Answer Correctness | 72.5% |
| Faithfulness | 76.88% |
| Unsupported Claim Rate | 23.12% |
| Citation Accuracy | 71.17% |
| Citation Coverage | 47.63% |
| Unanswerable Abstention | 0 / 5 |

### 简单分析

E2 的主要结论是：**异步化显著降低了工程耗时**。

E1 与 E2 的语义指标不用于证明“异步影响质量”，因为 E2 Generator 重新调用过模型，输出存在自然波动。E2 的核心价值是性能优化。

### 数据来源

- `evaluation/runs/generation/e2_generation_async/generation_summary.json`
- `evaluation/runs/generation/e2_generation_async/summary.json`

---

## 4. E3：G1 Grounded Prompt Optimization

### 做了什么

在 E2 异步框架基础上，只修改 Generator Prompt：

`G0_naive → G1_grounded`

G1 主要增加：

- 只能根据 Context 回答
- 禁止外部知识和自行推测
- 证据不足时固定拒答
- Context 冲突时不得擅自选择
- 多子问题需要分别回答
- 关键事实要求 Citation
- 只输出合法 JSON

### E2 → E3 数据对比

| 指标 | E2 G0 | E3 G1 | 变化 |
|---|---:|---:|---:|
| Parse Success | 42% | **88%** | ↑ 46pp |
| Answer Correctness | **72.5%** | **52.5%** | ↓ 20pp |
| Faithfulness | 76.88% | 76.35% | 基本不变 |
| Unsupported Claim Rate | 23.12% | 23.65% | 基本不变 |
| Unanswerable Abstention | 0/5 | **2/5** | 改善 |
| False Abstention | 0/45 | **4/45** | 出现副作用 |
| Citation Accuracy | 71.17% | **100%** | 提升 |
| Citation Coverage | **47.63%** | **7.01%** | 大幅下降 |
| CORRECT | 18 | 12 | ↓ |
| PARTIAL | 27 | 24 | — |
| WRONG | 0 | 9 | ↑ |

E3 Judge Token：

- Input：101,457
- Output：25,071
- Total：126,528

### 简单分析

这次 Prompt 优化没有整体提升质量，反而暴露了一个重要现象：

> **对于能力较弱的生成模型，Prompt 约束并不是越严格越好。规则过多、拒答条件过强时，模型可能优先触发某些规则，牺牲回答完整性。**

具体表现：

- 严格 JSON 规则有效：Parse Success 从 42% 提升到 88%。
- 拒答规则过强：不可回答题有所改善，但同时出现 4 次 False Abstention，Correctness 明显下降。
- Citation Accuracy 达到 100%，但 Coverage 只有 7.01%，说明“引用正确”和“引用充分”是两个不同问题。
- Grounding、拒答、完整回答、Citation、JSON 等规则同时存在时，弱模型可能无法很好地兼顾所有约束。

### 数据来源

- `evaluation/runs/generation/e3_prompt_optimized/summary.json`
- `evaluation/runs/generation/e3_prompt_optimized/eval_trace.jsonl`

---

## 5. 当前阶段结论

```text
E1 Naive Baseline
        ↓
建立质量与性能基线

E2 Async Optimization
        ↓
Generator ≈ 2.83× 加速
Evaluator ≈ 3.08× 加速

E3 Strict Grounded Prompt
        ↓
JSON 格式明显改善
但 Correctness 明显下降
出现 False Abstention
Citation Coverage 大幅下降
```

当前最重要的实验结论：

> **弱模型上的 Prompt Engineering 需要控制规则数量和优先级。过度严格的 Grounding / Abstention Prompt 可能减少部分风险，但也可能导致过度拒答、信息遗漏和规则竞争，最终降低 Answer Correctness。**

下一步不继续堆规则，而是基于 E3 的失败结果小范围修正 G1：

- 只有核心信息完全没有证据时才整体拒答；
- 部分信息有证据时，回答可确认部分；
- 明确要求 Citation 出现在 `answer` 正文对应事实之后，而不是只放在 `citations` 数组中。
