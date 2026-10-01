# P1-10MD-v1 QA / Evidence Benchmark 质量报告

**Benchmark Version: v1**  
**Corpus Version: P1-10MD-v1**  
**Question Count: 50**  
**Evidence Count: 73**  
**冻结前修订日期：2026-09-28**

本报告只评价这 10 篇 Markdown 作为问答语料的质量。Gold Answer 表示“这些文档支持的答案”，不是对项目源码、现网部署或个人贡献的独立审计结论。没有实施 Embedding、检索、生成、Judge 或 RAG Baseline。

## 1. 方法与 Pilot 10

1. 先完整检查 `manifest.json` 指定的 10 篇 Markdown，记录章节、计算口径、字段、接口、测试报告、重叠、冲突与缺口，形成 `corpus_knowledge_map.md`。
2. 按“文档 → 知识 → 原文证据 → 问题”顺序编写 Pilot `q001`–`q010`。它覆盖事实、参数、模块职责、数据流、设计逻辑、实现、真正跨文档冲突和不可回答题。
3. 对 Pilot 运行 `python benchmark/validate_benchmark.py --pilot`，检查 Schema、ID、10MD 文件白名单、语料哈希、Gold Answer/Evidence 关系、真实 Markdown heading 和 Evidence 原文匹配。Pilot 通过后再扩展。
4. Pilot 人工复核发现：职责答案中不应顺带断言未被摘录直接支持的否定；冲突题应并列给出两种文档口径，而非私自选择一个；同一表格的两个参数需要分别引用。
5. 扩展 `q011`–`q050` 后，又按答案逐题检查最小充分证据。将连续流程步骤合并为一个证据区域，给原先缺少环节的答案补上对应引用，并重新校准难度。

Gold Evidence 由源 Markdown 的精确原文摘录组成；自动脚本逐条确认摘录仍在选定文件及所标 Markdown Section 下。人工复核回答是否只说证据确实支持的内容。验证脚本无法自动判断语义充分性或证明全语料不存在某事实，所以人工审核仍是冻结条件的一部分。

## 2. 最终分布与覆盖

| 维度 | 分布 |
| --- | --- |
| 类型 | factual 8；parameter 5；module_responsibility 7；data_flow 7；architecture_reasoning 6；implementation_detail 5；cross_document 7；unanswerable 5 |
| 难度 | easy 13；medium 28；hard 9 |
| Hop | single 26；multi 19；none 5 |
| 文档覆盖 | 10/10 篇至少出现在一道 Gold Evidence 中；共 73 个证据片段 |

修复后的逐文档计数见 [`benchmark_coverage.md`](benchmark_coverage.md)。`cross_document` 的 7 题分别要求两篇文件提供不可替代的信息；`q042` 结合离线主链路与前端组件更新步骤，`q044` 分述历史修复验证与未来重导的权威规则，`q046` 分述图表数量与后端测试范围。`multi` 的其他题可能在同一文件的不同条件或环节中联合取证。

## 3. 重复、冲突与资料缺口

### 内容重复与出题去重

- 13 个统计功能在分析手册、结果结构、数据库设计、API 与前端文档中多次出现。题目分别检验计算口径、无表头导入、库表/字段、接口和页面呈现，避免以同一答案换词重复提问。
- Sqoop 脚本的 13 条命令结构相近，只选取入库职责及表名映射、错误参数冲突两种不同评测目的。
- 手工比较全部题目，未发现答案和证据均相同的明显语义重复。相似表述中，`q037` 问双实现的设计理由，`q045` 问功能 F 的跨文档分类冲突；`q005` 只追 HDFS→MySQL，`q042` 还追踪 API 返回后的前端组件更新与 ECharts 渲染。
- 题目仅在核对历史记录与跨文档边界时指明文档作用域；必要的表名、字段名和接口名保留，用于测试真实技术查询。

### 已记录冲突与处理

| 冲突/边界 | 题目 | Gold 处理 |
| --- | --- | --- |
| Sqoop 命令脚本仍用 `--input-lines-terminated-by '\001'`，实施手册指出 export 应用 `--lines-terminated-by '\n'` | `q009` | 呈现两处原文及风险，不把旧命令写成正确执行方案 |
| 高分均分：API/分析/数据库写 ≥7.5，用户手册指标卡写 ≥8.0 | `q008` | 明示阈值冲突，不裁定真实前端口径 |
| 功能 F 在实施手册标 Spark Core，在数据库功能清单标 SparkSQL | `q045` | 明示冲突，需源码才可裁定 |
| “统一过滤 `YEAR=0`”的总原则与功能 B/F 结果中仍有 0 年份 | `q043` | 同时记录原则和已知例外 |
| 前端 token/localStorage 登录与统计 API 文档“无鉴权” | 知识地图 | 分清前端路由认证和后端统计接口作用域；不写成同一认证链 |
| `/db` 与 `src/db` 的数据 SQL 路径写法、数据脚本个数表述不同 | `q044`、知识地图 | 分述历史报告的 `/db` 预期数据与设计文档的 `src/db/` 权威规则，不推断两种路径写法完全等价 |

### 缺失信息与不可回答审核

对全部 10 篇文件按关键词和相关章节复查后，以下问题保留为 `answerable=false`：

- `q010`：具体推荐模型与离线评估指标。项目名称提“智能推荐”，文档没有推荐算法/评测细节。
- `q047`：个人独立贡献和代码提交量。团队文档没有可靠的个人归属证据。
- `q048`：生产 Kubernetes 节点与命名空间。文档只包含前端部署方案，无已实施 Kubernetes 生产配置。
- `q049`：前端 Playwright E2E 实际通过数。方案只提出 Playwright/Cypress；381 项是后端报告。
- `q050`：公开部署后 API p95 延迟。没有测量结果。

“没有语料证据”不等于现实中绝对没有该系统或数据；受测 RAG 应基于本版本语料拒答或限定说法。

## Final Freeze Audit 修复记录

独立 Final Freeze Audit 指出的 11 题已按 Corpus 做冻结前最小修复：6 个 BLOCKER（`q014`、`q027`、`q041`、`q042`、`q044`、`q046`）与 5 个 MAJOR（`q002`、`q005`、`q015`、`q025`、`q038`）。修复内容限于补足 Gold Evidence、收束假 multi-hop、使 cross-document 的两篇文档各有必要信息，并将已执行的历史修复结果与修复策略区分。详见 `final_freeze_repair_report.md`；独立审计记录 `final_freeze_audit_report.md` 保持原样。

## 4. 后续检索实验的诊断用途

这些是未来实验假设，不代表已运行任何检索器。

- **Dense Retrieval 候选**：`q021`（“数据脚本职责”的面试式改写）、`q031`（从行数异常追到差异行）、`q033`（无表头与列序因果）、`q036`（整体重灌理由）。关键词不完全照抄标题，适合检验语义匹配。
- **Keyword / Hybrid 候选**：`q003`（`current/size`）、`q018`（`ACTOR_IDS` 与分隔符）、`q029`（`stat_year_top20_movie` / endpoint）、`q039`（`@TableId` / `updateById`）、`q041`（`DOUBAN_VOTES`）。精确标识符可能使词面检索占优。
- **Reranker 候选**：`q008`、`q009`、`q043`、`q045` 需要区分新旧或冲突叙述，不能只返回一个看似相关片段；`q046` 需要区分后端测试与前端验收的证据范围。
- **Graph Retrieval 候选**：`q042` 的 CSV→HDFS→Sqoop→MySQL→API→ECharts 链路、`q029` 的结果表→接口、`q044` 的直通数据→修复版 SQL 权威关系。这里只标注多实体关系，不实施图检索。
- **Abstention / Hallucination 候选**：`q010`、`q047`–`q050` 必须拒绝无证据的具体事实；`q008`、`q045` 应陈述冲突而非捏造唯一答案。

## 5. 验证与冻结规则

执行 `python benchmark/validate_benchmark.py` 应返回 PASS，检查 50 题、合法枚举、ID/Evidence ID 唯一、答案与可回答性一致、Gold Document 与 Evidence Document 一致、每段引文为 10MD 原文、Section 匹配、跨文档题至少引用两篇文件，以及全部 10 篇文件的 SHA-256 与 manifest 一致。不可回答题的“全语料无足够证据”与语义去重已人工复核，不能只靠此脚本证明。

本版指纹：

```text
Benchmark Version: v1
Corpus Version: P1-10MD-v1
Question Count: 50
Corpus manifest SHA256: dfad7019c8850df3025a242219bc624667000c965b8949363dd73fab62ba515c
Benchmark JSONL SHA256: a5762ec7264a059186ab85cccd409b421d8de1e6f7f77cc840b804110d7149d1
```

本轮修复发生在正式 Freeze 前，因此 Benchmark Version 仍为 `v1`。验证与修复报告完成后，等待用户确认再冻结 `benchmark_v1.jsonl` 与 10MD 语料副本。后续 Baseline、Hybrid 或 Reranker 实验使用同一版本；看到模型失败后不得暗中修改问题、答案或证据。Freeze 后若证实 Benchmark 本身有错，应记录更改原因，创建 `v2` 并重新报告版本与指纹。源 Markdown 本身有若干冲突，未来修订语料也需升级 Corpus Version，不能沿用 `P1-10MD-v1` 名称。
