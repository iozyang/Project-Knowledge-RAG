# RAG Generation 模型升级实验总结（E4）

## 1. 实验目的

在 E3.1 中，针对弱模型 `deepseek-r1-distill-qwen-7b` 已完成 Prompt 精简与修正，但仍存在：

- Answer Correctness 偏低；
- False Abstention 仍存在；
- Citation Coverage 不足；
- 多约束同时执行时稳定性有限。

因此 E4 不再继续调 Prompt，而是只替换 Generator，验证剩余问题是否主要来自模型能力瓶颈。

---

## 2. 实验设置

### E3.1

```text
Generator = deepseek-r1-distill-qwen-7b
Prompt    = G1.1_grounded
Async     = Yes
Contexts  = Frozen
```

### E4

```text
Generator = qwen3.8-flash
Prompt    = G1.1_grounded
Async     = Yes
Contexts  = Frozen
```

保持不变：

- Benchmark：50 题
  - 45 answerable
  - 5 unanswerable
- Retrieval Context：冻结
- Prompt：G1.1
- Claim Splitter：qwen3.8-flash
- Judge：qwen3.8-max-0902
- Gold Answer Points / Evidence Boundary / Evaluation 逻辑不变

核心变量：

> **只将 Generator 从 `deepseek-r1-distill-qwen-7b` 替换为 `qwen3.8-flash`。**

---

## 3. E3.1 → E4 数据对比

| 指标 | E3.1 7B | E4 Qwen3.8-Flash | 变化 |
|---|---:|---:|---:|
| Parse Success | 94% | **98%** | ↑ 4pp |
| Answer Correctness | 59.72% | **93.61%** | ↑ 33.89pp |
| CORRECT | 13 | **35** | +22 |
| PARTIAL | 28 | **10** | -18 |
| WRONG | 4 | **0** | 清零 |
| Faithfulness | 78.37% | **94.29%** | ↑ 15.92pp |
| Unsupported Claim Rate | 21.63% | **5.71%** | 大幅下降 |
| Unanswerable Abstention | 2/5 | **5/5** | 全部正确 |
| False Abstention | 3/45 | **0/45** | 清零 |
| Citation Accuracy | 67.68% | **94.29%** | ↑ 26.61pp |
| Citation Coverage | 30.44% | **95.61%** | ↑ 65.17pp |

---

## 4. E4 工程数据

### Generator Token

| 指标 | E3.1 | E4 |
|---|---:|---:|
| Input Tokens | 56,203 | 56,903 |
| Output Tokens | 19,255 | **6,208** |
| Total Tokens | 75,458 | **63,111** |

E4 输入 Token 基本不变，但输出 Token 大幅下降，说明更强模型在相同 Prompt 下生成结果更紧凑。

### Generator Latency

E4：

- Avg：5463.69 ms
- Median：2693.65 ms
- P95：27834.97 ms

说明 E4 质量明显提升，但尾延迟较高，后续工程实现中需要保留这一效果—延迟权衡。

### Evaluation

- Wall Time：235.44 s
- Throughput：12.74 questions/min
- Evaluation Tokens：164,480

---

## 5. 实验结论

E4 的结果说明，E3 / E3.1 阶段暴露的问题并不只是 Prompt 设计问题。

在保持 G1.1 Prompt、Context 和 Evaluation Framework 不变的情况下，仅替换 Generator：

```text
deepseek-r1-distill-qwen-7b
            ↓
       qwen3.8-flash
```

就使：

- Correctness：59.72% → 93.61%
- Faithfulness：78.37% → 94.29%
- Citation Coverage：30.44% → 95.61%
- Unsupported Claim Rate：21.63% → 5.71%
- WRONG：4 → 0
- False Abstention：3 → 0
- Unanswerable Abstention：2/5 → 5/5

因此当前可以认为：

> **弱模型在同时执行 Grounding、Abstention、Citation、JSON 和完整回答等多项约束时存在明显能力瓶颈。Prompt 简化能够缓解规则竞争，但更强 Generator 才真正解决了大部分剩余问题。**

---

## 6. Generation 阶段结论

当前 Generation 实验链：

```text
E2  G0 + 7B
Correctness 72.5%

        ↓

E3  Strict G1 + 7B
Correctness 52.5%
→ 规则竞争、过度拒答、Citation Coverage 崩溃

        ↓

E3.1  Refined G1.1 + 7B
Correctness 59.72%
→ 部分恢复，但仍受弱模型能力限制

        ↓

E4  G1.1 + qwen3.8-flash
Correctness 93.61%
Faithfulness 94.29%
Citation Coverage 95.61%
WRONG 0
Abstention 5/5
```

至此不再继续围绕固定 Benchmark 微调 Prompt。

当前冻结：

```text
Retrieval          FROZEN
Prompt             G1.1_grounded
Generator          qwen3.8-flash
Evaluation         FROZEN
```

下一阶段进入端到端 RAG Pipeline、FastAPI 与 Demo / MVP 集成。

---

## 7. 数据来源

E3.1：

- `evaluation/runs/generation/e3_1_prompt_refined/summary.json`
- `evaluation/runs/generation/e3_1_prompt_refined/eval_trace.jsonl`

E4：

- `evaluation/runs/generation/e4_generator_qwen38_flash/summary.json`
- `evaluation/runs/generation/e4_generator_qwen38_flash/eval_trace.jsonl`
