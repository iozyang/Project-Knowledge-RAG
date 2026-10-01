# Benchmark v1 覆盖情况

**Corpus Version**：`P1-10MD-v1`  
**Benchmark Version**：`v1`  
**题数**：50（45 可回答、5 不可回答）  
**证据片段数**：73（同一题可以引用同文档的多个不同片段）

## Question Type Distribution

| question_type | 数量 |
| --- | ---: |
| `factual` | 8 |
| `parameter` | 5 |
| `module_responsibility` | 7 |
| `data_flow` | 7 |
| `architecture_reasoning` | 6 |
| `implementation_detail` | 5 |
| `cross_document` | 7 |
| `unanswerable` | 5 |
| **合计** | **50** |

分布与任务建议的 8/5/7/7/6/5/7/5 完全一致，未因文档缺口调整。

## Difficulty Distribution

| difficulty | 数量 |
| --- | ---: |
| `easy` | 13 |
| `medium` | 28 |
| `hard` | 9 |

## Hop Distribution

| hop_type | 数量 | 说明 |
| --- | ---: | --- |
| `single` | 26 | 一个连续证据区域即可回答 |
| `multi` | 19 | 需要至少两个必要证据片段；其中 7 题为真正跨文档联合或冲突识别 |
| `none` | 5 | 不可回答，Gold Answer 与证据均为空 |

## Document Coverage

“Gold Document 题数”按题目去重计数；“Gold Evidence 片段数”按原文摘录计数。同一题可能覆盖多个文件，所以各文档题数之和大于 45。

| 文档 | Gold Document 题数 | Gold Evidence 片段数 |
| --- | ---: | ---: |
| `MovieAnalysis实施手册.md` | 13 | 17 |
| `Sqoop导出命令脚本.md` | 2 | 3 |
| `数据分析结果结构说明.md` | 5 | 5 |
| `API手册.md` | 6 | 9 |
| `后端项目实施手册.md` | 6 | 6 |
| `数据库检查与修复报告.md` | 4 | 5 |
| `数据库设计文档.md` | 8 | 9 |
| `测试报告.md` | 3 | 3 |
| `前端实施方案.md` | 6 | 13 |
| `用户使用手册.md` | 3 | 3 |

**10/10 篇文档均进入至少一道可回答题的 Gold Evidence。**分析实施手册覆盖较多（13 题），因为它承载计算口径、流程、故障与设计理由；其他文档均有独立测试目的。引用最多的 Section 包括《数据分析结果结构说明》的“0.1 结果落盘通用规则”和《MovieAnalysis实施手册》的 3.13，均为 4/73 个片段，没有出现一个 Section 支撑 10 道题的情况。

## 需要注意的覆盖边界

- 13 张统计表与 43 个查询端点不逐一枚举成题；只选择能检验数据契约、条件查询、类型映射和跨层追踪的代表项。
- Sqoop 脚本文档在 2 题中有 3 个证据片段，覆盖导入职责、表名映射和命令冲突；避免对 13 条几乎同形的命令重复出题。
- 测试报告 3 次引用，分别测历史结果、实体映射约束和“后端测试不能证明前端 E2E”的证据边界。
- 用户手册 3 次引用，覆盖阈值冲突、退出按钮和 12 图表的验收边界。
- 不可回答题经过 10 篇全文关键词检查；详见 `benchmark_quality_report.md`。不将无证据的个人贡献、推荐算法、Kubernetes、前端 E2E 成绩和生产 p95 写成事实。
