# Final Freeze Repair Report

## 1. 修复范围

按独立审计记录对 11 题做冻结前定向修复：6 个 BLOCKER（`q014`、`q027`、`q041`、`q042`、`q044`、`q046`）与 5 个 MAJOR（`q002`、`q005`、`q015`、`q025`、`q038`）。其余 39 条 JSONL 行保持原样；题数、Question Type、Difficulty 与 Benchmark Version `v1` 不变。Corpus、`corpus_knowledge_map.md`、`validate_benchmark.py` 和 `final_freeze_audit_report.md` 未修改。

## 2. 逐题修改

### q002

- **Before：** 单段 Evidence 只证明功能 5 不落盘、无需 MySQL 表及 Sqoop。
- **After：** 将 `q002_e01` 扩为同一 Section 中连续的“临时视图名 `stat_movie_year_sql`”与“不落盘、仅供 SparkSQL 内查询”两行；Question、Gold Answer、`single` 均保留。
- **Why：** Gold Answer 中的临时视图事实现在有直接原文。

### q005

- **Before：** 两段 Evidence 未明确证明 HDFS 子目录与 MySQL 表同名。
- **After：** 增加《Sqoop导出命令脚本》原文“`--table`：MySQL 目标表（与 HDFS 子目录同名）”为 `q005_e03`；Gold Answer 保留。
- **Why：** 路径、Sqoop 入库和同名表映射均有证据。

### q014

- **Before：** 只问是否有退出按钮，却以三段证据标为 `multi`，答案附带两种退出方法。
- **After：** Question 保留；Gold Answer 收束为当前版本没有页面内退出按钮；仅保留原 `q014_e03` 并编号为 `q014_e01`，`hop_type=single`。
- **Why：** 一段原文已足以回答是非题。

### q015

- **Before：** Evidence 来自“4. 修复策略”，仅证明五张表被列入修复范围。
- **After：** 用“5. 修复执行结果”连续记录的五张表 `TRUNCATE + 插入 SQL 文件数据` 与执行行数替换证据；Question、Gold Answer、`single` 保留。
- **Why：** 完成态由执行记录支持，限定为报告记载的历史修复。

### q025

- **Before：** 首段 Evidence 从 `const request = axios.create({` 开始，缺少文件归属。
- **After：** `q025_e01` 向前扩一行，纳入 `// src/api/request.js`；其余 Evidence 与标注保留。
- **Why：** Axios 配置可以直接归属到 Question 指定文件。

### q027

- **Before：** Question 只问结果位置，却以两个文档支持位置与额外的 CSV 输出格式，标为 `multi`。
- **After：** Gold Answer 去掉结果“以 CSV 写入”的子结论；只保留《MovieAnalysis实施手册》的 HDFS 结果路径 Evidence，`gold_documents` 收束为该文档，`hop_type=single`。
- **Why：** 位置问题由一个连续数据流片段完整回答。

### q038

- **Before：** `q038_e02` 只列出“缺少必填参数”一种 400 情况。
- **After：** 扩为 API 响应码表中连续的三类 400 情况：缺参、类型错误和取值错误；Question、Gold Answer、`multi` 保留。
- **Why：** 一般参数错误的 HTTP 400 与业务 `code=400` 概括获得完整支持。

### q041

- **Before：** 两篇文档、两段 Evidence 标为 `multi`；数据库设计文档一段已包含未 cast、字符串及 `VARCHAR(32)`。
- **After：** 只保留《数据库设计文档》为 Gold Document，原 `q041_e02` 编号为 `q041_e01`，`hop_type=single`；Question、Gold Answer 保留。
- **Why：** 去掉没有独立贡献的重复文档和假多跳。

### q042

- **Before：** 原 Question 的主链路可由一篇数据库设计文档回答，却列出五篇 Gold Documents。
- **After：** Question 同时询问原始 CSV 到 REST API / ECharts 的主链路，以及 API 返回后前端组件如何更新并交给 ECharts；Gold Answer 增加组件更新步骤；Gold Evidence 精简为《数据库设计文档》`1.2` 的完整主链路与《前端实施方案》`2.3.2` 的“返回数据 → 更新组件 → ECharts 渲染”。保留 `cross_document`、`multi`。
- **Why：** 第一篇没有组件更新步骤，第二篇没有离线入库主链路，两者各不可少。

### q044

- **Before：** 单篇数据库设计文档即可回答权威数据版本；原 Evidence 又未摘录 Gold Answer 的全部细节。
- **After：** Question 分问 2026-09-15 修复后的历史全库比对结果与将来 Sqoop 重导冲突时的权威规则。Gold Answer 分述报告中的 13/13 表与 `/db` 预期数据一致，以及设计文档规定 `src/db/` SQL 为未来冲突时唯一权威。Evidence 分别取自修复报告 Section `6` 与设计文档 Section `4.4`，保留 `cross_document`、`multi`。
- **Why：** 历史实际结果与未来规则分别由不同文档证明，没有把两种路径写法或两个时间作用域暗中合并。

### q046

- **Before：** Question 已给出用户手册的“12 个图表”，用户手册 Evidence 对原问题并非必需。
- **After：** Question 改为先询问图表数量，再询问 381 个后端用例的测试范围及能否证明前端 E2E；Gold Answer、两篇 Gold Documents 与 Evidence 保留，继续使用 `cross_document`、`multi`。
- **Why：** 用户手册提供图表数，测试报告提供后端层级范围，二者均为完整答案所需。

## 3. Validator

执行：`python benchmark/validate_benchmark.py`。

结果：**PASS**，50 题；Benchmark JSONL SHA-256 为 `a5762ec7264a059186ab85cccd409b421d8de1e6f7f77cc840b804110d7149d1`。验证器确认所有 Gold Evidence 为白名单 Corpus 原文、Section 与文档一致、Evidence ID 规范，并核验 10 篇语料文件哈希。

已逐题人工复核上述 11 题的 Question → Gold Answer → Gold Evidence → Corpus 链：新增答案细节均有原文，`q014`、`q027`、`q041` 的单段证据足够；`q042`、`q044`、`q046` 的两篇文档分别承担不可替代的信息；`q015` 仅将报告记载的已执行修复作为历史事实。未以验证器 PASS 代替语义判断。

## 4. 修复后统计

- **Question Count：** 50（45 可回答、5 不可回答）。
- **Evidence Count：** 73。
- **Question Type：** factual 8；parameter 5；module_responsibility 7；data_flow 7；architecture_reasoning 6；implementation_detail 5；cross_document 7；unanswerable 5。
- **Difficulty：** easy 13；medium 28；hard 9。
- **Hop：** single 26；multi 19；none 5。
- **Document Coverage：** 10/10 篇仍被可回答题引用；逐文档 Gold Document 题数 / Gold Evidence 片段数如下。

| 文档 | 题数 | Evidence 数 |
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

## 5. Hash

- **Corpus Version：** `P1-10MD-v1`。
- **Corpus manifest SHA-256：** `dfad7019c8850df3025a242219bc624667000c965b8949363dd73fab62ba515c`，与修复前一致；10 篇 Markdown 的 SHA-256 均与 manifest 记录一致。
- **Benchmark Version：** `v1`（正式 Freeze 前修订）。
- **Benchmark JSONL SHA-256：** `a5762ec7264a059186ab85cccd409b421d8de1e6f7f77cc840b804110d7149d1`。

## 6. Freeze Readiness

**YES — Benchmark v1 Ready to Freeze。** 11 题已按 Corpus 最小修复并重新做语义复核，验证器 PASS，Corpus 指纹未变，覆盖与质量报告及本修复报告已更新。Benchmark 尚未正式 Freeze，等待用户确认。
