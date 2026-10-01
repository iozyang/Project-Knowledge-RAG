# Final Freeze Audit

## 1. 总体结论

**FAIL。** 逐题复核 `q001`–`q050` 后，发现 6 道题的 multi-hop / cross-document 核心标注不能由题目所需的证据链成立，另有 5 道题的 Gold Evidence 未完整覆盖答案或题目要求的事实。当前 `benchmark_v1.jsonl` **不建议进入 Freeze**。以下只提出最小修复建议；本轮没有改动 Benchmark、Corpus 或验证脚本。

审计范围严格限于 `manifest.json` 中 `include_in_chunking=true` 的 10 篇 Markdown，以及指定的 5 个 Benchmark 文件。`python benchmark/validate_benchmark.py` 返回 PASS；这证明结构、原文摘录和文件哈希满足脚本约束，不证明语义充分性。5 道不可回答题均在 10 篇语料范围内检索并核对相关章节，未发现足以回答其具体数值或归属的证据。

## 2. 问题清单

### q002 — MAJOR

**问题类型：** Gold Evidence。

**当前内容：** Gold Answer 称“功能 5 只注册 SparkSQL 临时视图”；`q002_e01` 只摘录“本项**没有调用 `write_result`**，不会写出到 HDFS，无需在 MySQL 建表、无需 Sqoop 导出。”

**问题：** 当前引文足以证明不落盘、无 MySQL 表，却没有证明“只注册临时视图”这一答案子结论。

**Corpus 依据：** `data/数据分析结果结构说明.md`，Section `5. 按上映年份统计电影数量（SQL 版）`，原文：“- **临时视图名**：`stat_movie_year_sql`”；“仅供 SparkSQL 内查询使用。”

**为什么当前标注不成立：** Gold Answer 的视图事实需要从未收录在 Gold Evidence 中的相邻原文补入。

**最小修改建议：** 将 `q002_e01` 扩为连续包含“临时视图名”与“不落盘”两行的原文，保留 single-hop。

### q005 — MAJOR

**问题类型：** Gold Evidence。

**当前内容：** Gold Answer 称 Sqoop 导入 MySQL `movie_stat_db` 的“同名结果表”；现有引文只说 HDFS 子路径为 `<name>`，以及导入 MySQL 的“对应表”。

**问题：** “对应”并不能单独证明目标表与 HDFS 子目录**同名**。

**Corpus 依据：** `data/Sqoop导出命令脚本.md`，Section `Sqoop 导出命令脚本`，原文：“`--table`：MySQL 目标表（与 HDFS 子目录同名）”。

**为什么当前标注不成立：** 答案多了一个未进入 Gold Evidence 的精确映射关系。

**最小修改建议：** 将 Gold Answer 中“同名结果表”改为“对应结果表”；若必须保留“同名”，则补入上述原文。

### q014 — BLOCKER

**问题类型：** Hop Type。

**当前内容：** Question 只问“用户手册提供了页面内的退出登录按钮吗？”，却标为 `multi`，列出清除数据、无痕模式和无按钮三段证据。

**问题：** `q014_e03` 已能独立回答该是非题；另外两段只是答案附带的退出方法。

**Corpus 依据：** `frontend/用户使用手册.md`，Section `6.3.2 方法二：浏览器无痕模式`，原文：“> **注意**：系统当前版本未提供退出登录按钮，建议使用上述方法退出。”

**为什么当前标注不成立：** 完成 Question 不需要联合三个 Evidence 单元，`multi` 的评测目的由额外答案细节制造。

**最小修改建议：** 将 Question 改为同时询问“是否有退出按钮，以及手册推荐的两种退出方法”；保留当前答案与三段证据。也可只保留无按钮引文并改为 `single`。

### q015 — MAJOR

**问题类型：** Gold Evidence；历史状态边界。

**当前内容：** Question 问“最终对多少张问题表进行了整体替换”，`q015_e01` 仅摘录 Section `4. 修复策略` 中的“**范围**：5 张表……”。

**问题：** 策略中列出的修复范围不等于已经执行的修复结果。

**Corpus 依据：** `backend/数据库检查与修复报告.md`，Section `5. 修复执行结果`，原文依次记录“`>>> 修复 stat_year_region_count: TRUNCATE + 插入 SQL 文件数据`”、“`>>> 修复 stat_year_top20_movie: TRUNCATE + 插入 SQL 文件数据`”、“`>>> 修复 stat_region_count: TRUNCATE + 插入 SQL 文件数据`”、“`>>> 修复 stat_language: TRUNCATE + 插入 SQL 文件数据`”、“`>>> 修复 stat_region_year_avg_score: TRUNCATE + 插入 SQL 文件数据`”。

**为什么当前标注不成立：** Gold Evidence 仅证明计划/策略，不足以支持 Question 中“最终进行了”的完成态。

**最小修改建议：** 用 Section `5. 修复执行结果` 中连续列出五张表执行结果的原文替换 `q015_e01`，保留 `single` 与历史报告作用域。

### q025 — MAJOR

**问题类型：** Gold Evidence。

**当前内容：** Question 明确询问 `src/api/request.js` 的职责，但现有 `q025_e01` 从“`const request = axios.create({`”开始，没有收录紧邻其前的文件标识。

**问题：** 当前证据集合说明了 Axios 配置和响应处理，却没有把这些配置明确归属到 Question 指定的文件。

**Corpus 依据：** `frontend/前端实施方案.md`，Section `3.3.1 请求配置`，原文连续两行：“`// src/api/request.js`”和“`const request = axios.create({`”。

**为什么当前标注不成立：** 对文件职责题，代码段的文件归属是证据链的一部分；目前需要读者自行补读未摘录的上一行。

**最小修改建议：** 将 `q025_e01` 向前扩一行纳入文件注释，其余证据与标注不变。

### q027 — BLOCKER

**问题类型：** Hop Type。

**当前内容：** Question 只问离线分析后结果“先在哪里形成”，标为 `multi`；`q027_e01` 已给出 HDFS 统计结果路径，`q027_e02` 补充其文件格式为 CSV。

**问题：** Question 没有要求结果格式；第二段证据只支撑答案里额外加入的“CSV”。

**Corpus 依据：** `data/MovieAnalysis实施手册.md`，Section `1.3 整体数据流`，原文：“`HDFS 统计结果(/movies/analysis_results/<表名>/part-*)`”。`data/数据分析结果结构说明.md`，Section `0.1 结果落盘通用规则`，原文：“文件格式 | CSV，**无表头**（`header=false`）”。

**为什么当前标注不成立：** 第一段已经完整回答位置问题；第二段不是完成 Question 所必需。

**最小修改建议：** 在 Question 中明确加问“结果文件是什么格式”，使两段证据各自不可少；或删去 CSV 子结论及第二段证据，改为 `single`。

### q038 — MAJOR

**问题类型：** Gold Evidence。

**当前内容：** Question 与 Gold Answer 概括“参数错误”返回 HTTP 400、业务 `code=400`；`q038_e02` 只摘录了“缺少必填参数”的 400 行。

**问题：** 仅一类错误示例不足以支持所有参数错误的概括，包括类型不合法和取值不合法。

**Corpus 依据：** `backend/API手册.md`，Section `2.3 响应码说明`，原文另有：

```text
| 400 | 400 | 参数类型不合法：`Invalid parameter type: {参数名}` |
| 400 | 400 | 参数取值不合法（如页码≤0、开始年份>结束年份、文本为空白），`message` 为具体校验说明 |
```

**为什么当前标注不成立：** 现有 Gold Evidence 的 400 行只代表缺参，不能作为一般参数错误行为的完整依据。

**最小修改建议：** 将 `q038_e02` 扩为响应码表中连续的三行 400 情况，保留现有答案和 `multi`。

### q041 — BLOCKER

**问题类型：** Hop Type；Gold Documents。

**当前内容：** 标为 `multi`，同时引用结果结构文档与数据库设计文档，回答 `DOUBAN_VOTES` 未 cast、仍为字符串，故 MySQL 设为 `VARCHAR(32)`。

**问题：** `q041_e02` 单独就包含未 cast、字符串和 `VARCHAR(32)` 三项完整事实；`q041_e01` 重复其中两项。

**Corpus 依据：** `backend/数据库设计文档.md`，Section “3.11 `stat_year_top20_movie` —— 功能 B · 每年评分 Top20 电影”，原文：

```text
| `DOUBAN_VOTES` | `VARCHAR(32)` | 文本 | 豆瓣投票数（代码中未做 cast，仍为字符串） |
```

**为什么当前标注不成立：** 一段 Evidence 已能完整回答 Question，另一篇文档对答案没有不可替代的贡献。

**最小修改建议：** 保留当前 `q041_e02` 并重编号为 `q041_e01`，只保留《数据库设计文档》为 Gold Document，将 `hop_type` 改为 `single`。

### q042 — BLOCKER

**问题类型：** Cross-document；Gold Documents / Evidence 最小性。

**当前内容：** 标为 `cross_document`，用五篇文档拼接“原始 CSV → PySpark → HDFS → Sqoop → MySQL → API → ECharts”的交接链。

**问题：** 一篇未列为 Gold Document 的 Corpus 文档已经连续记载该链路，足以回答当前 Question 要求的交接点；现有五篇 Gold Documents 不是答案所必需。

**Corpus 依据：** `backend/数据库设计文档.md`，Section `1.2 整体数据链路`，原文连续记载：“`原始电影数据(CSV)`”；“`PySpark 离线统计 (MovieAnalysis.py)`”；“`HDFS 落盘  /movies/analysis_results/<表名>/   (CSV, 无表头, 逗号分隔)`”；“`Sqoop 导出 export ( --fields-terminated-by ',' )`”；“`MySQL  movie_stat_db  (13 张 stat_* 结果表)`”；“`Spring Boot + MyBatis-Plus (Entity/Mapper/Service/Controller)`”；“`REST API ──▶ 前端 ECharts 可视化`”。

**为什么当前标注不成立：** 当前 Question 不要求前端组件更新等独有细节，完整路径已在单篇文档中呈现；把同一链路拆为五份引用未形成真正跨文档推理。

**最小修改建议：** 若保留跨文档评测目的，在 Question 中同时要求数据库链路和“前端收到返回数据后如何更新组件并交给 ECharts”，将 Gold Evidence 精简为《数据库设计文档》`1.2` 与《前端实施方案》`2.3.2` 的必要片段，并使 Gold Answer 明确“更新组件”这一步。

### q044 — BLOCKER

**问题类型：** Cross-document；Gold Evidence。

**当前内容：** Question 问 Sqoop 重导后以哪种数据为验收基准，标为 `cross_document`；Gold Answer 还称直通结果可能留有空格变体并使计数偏低。

**问题：** 《数据库设计文档》单独给出了清洗 SQL 的权威地位、Sqoop 直通数据的差异及双空格变体和计数偏低。现有两段 Gold Evidence 又未直接摘录 `src/db/` 路径和空格变体/偏低这两个答案细节。

**Corpus 依据：** `backend/数据库设计文档.md`，Section `4.4 数据说明与注意事项`，原文：“若通过 Sqoop 直通流程重新导入，库中将是未经归一的原始统计，与本项目 SQL 文件存在差异（如 `('西班牙', 4179)` vs `('西班牙', 4180)`、`('印地语 Hindi', 113)` vs `('印地语 Hindi', 120)`），**两者冲突时以 `src/db/` 下 SQL 文件为唯一权威数据源**（详见《数据库检查与修复报告》）。”；同 Section 另记：“而 Sqoop 直通数据中会出现 `'印度  India'` 类双空格脏行并伴随计数偏低”。

**为什么当前标注不成立：** 一篇文档足以回答题目；当前 Gold Evidence 也未覆盖 Gold Answer 的全部细节。

**最小修改建议：** 若维持 `cross_document`，把 Question 改为同时询问修复报告在 2026-09-15 实际完成的 13 表比对结果，以及设计文档对未来 Sqoop 重导冲突的处理规则；分别引用报告 Section `6. 最终验证（修复后全库比对）` 和设计文档 Section `4.4`，并相应收束 Gold Answer。

### q046 — BLOCKER

**问题类型：** Cross-document；Hop Type。

**当前内容：** Question 已把“用户手册列出的 12 个图表”作为前提，只问后端 381 个通过用例能否证明前端端到端验收，标为 `cross_document`。

**问题：** 在 Question 已给出图表数的情况下，只需测试报告的范围便能回答“不能”；用户手册证据只是重复题干前提。

**Corpus 依据：** `backend/测试报告.md`，Section `1.3 测试范围`，原文列出“`| Entity | 字段映射、getter/setter、equals/hashCode、toString、注解约束 |`”、“`| Mapper | 分页查询、条件查询、全量查询与数据合法性校验 |`”、“`| Service | 业务查询、分页、参数校验、去重/冲突处理 |`”、“`| Controller | 接口请求响应、参数校验、全局异常处理 |`”、“`| 应用 | Spring 上下文加载 |`”。`frontend/用户使用手册.md`，Section `4.1 仪表板概览`，原文：“**图表展示区域**：展示 12 个可视化图表”。

**为什么当前标注不成立：** 对当前是非问题，后端测试范围已足以限定 381 个用例的证明力；第二篇文档没有提供答案必需的新事实。

**最小修改建议：** 将 Question 改成“用户手册列出多少个图表，测试报告的 381 个用例覆盖哪些层，能否据此证明这些图表完成前端 E2E 验收？”，使两篇文档分别承担不可省略的答案部分；保留原有证据并据新 Question 调整 Gold Answer。

## 3. 其他检查结果

- **结构与指纹：** 验证器返回 PASS；50 题（45 可回答、5 不可回答）、79 个 Evidence、类型/难度/Hop 分布、10/10 文档覆盖及逐文档计数与 `benchmark_coverage.md` 一致。`manifest.json` SHA-256 为 `dfad7019c8850df3025a242219bc624667000c965b8949363dd73fab62ba515c`；`benchmark_v1.jsonl` SHA-256 为 `6bfb2132f6d3ff1b3c8daf0d6df76f66fcc05fbce87effa8d435029fc526294b`，均与质量报告一致。API 手册的业务接口小节数为 43；覆盖报告的“0.1 结果落盘通用规则”引用数为 6。
- **不可回答：** `q010`、`q047`–`q050` 均未在 10 篇 Markdown 中找到足以给出推荐模型及离线指标、个人独立贡献及提交量、生产 Kubernetes 节点/命名空间、前端 Playwright 实际通过数、公开部署后 API p95 的证据。前端方案只列 E2E 测试方案，381 例仅是后端历史测试结果；不可回答不等于现实中不存在。
- **冲突与边界：** `q008`、`q009`、`q043`、`q045` 均明确呈现相应的阈值、Sqoop 参数、0 年份、Spark Core / SparkSQL 文档冲突；没有把历史报告自动推为当前状态，也没有把前端本地登录与后端统计 API 鉴权合并。
- **其余语义项：** 除上列问题外，未发现明确的同答案同证据重复题、明显影响区分度的词面泄漏、严重失真的 Difficulty 或 Question Type 标注。`corpus_knowledge_map.md` 未见可由选定语料证明的实质错误。
- **验证器：** 白名单、Corpus SHA-256、50 行 JSONL、顺序 ID / Evidence ID、原文与 Section、Gold Document 与 Evidence Document、single/multi 数量、cross-document 数量及 unanswerable 空字段约束均有效。脚本不能验证“证据是否必要或语义上充分”；本报告的问题正落在这一人工审核范围内。未发现需要修改脚本职责的明显逻辑错误。
- **报告一致性：** 现有覆盖和质量报告的数值与当前 JSONL 一致；质量报告所称“7 题为真正跨文档联合”与 `q042`、`q044`、`q046` 的当前题意不符。修复后须重新核算并改写该定性结论及受影响的分布/覆盖统计。

## 4. 最终回答

1. **是否存在 BLOCKER？** 是：`q014`、`q027`、`q041`、`q042`、`q044`、`q046`。
2. **是否存在 MAJOR？** 是：`q002`、`q005`、`q015`、`q025`、`q038`。
3. **是否建议当前 `benchmark_v1.jsonl` 进入 Freeze？** 否。
4. **若不能 Freeze，需要修复哪些具体题？** 上述 11 题；按各题的最小修改建议处理，不需重写 50 题或新增题。
5. **修复后是否只需重新运行 `validate_benchmark.py` 并更新 Hash / Report？** 否。还须人工复核这 11 题的新 Question → Gold Answer → Gold Evidence → Corpus 证据链，特别是 `multi` / `cross_document` 的必要性；随后运行验证器，重算 JSONL 指纹，并更新受影响的覆盖与质量报告。若 Benchmark 已实际冻结，应按现有冻结规则记录修订并升级版本；Corpus 未改变时无需改变其哈希。

**剩余风险：** 语料仅为当前 10 篇 Markdown，题量为 50；人工语义审核无法形式化证明绝对无误。这些边界本身不是本次 FAIL 的原因。
