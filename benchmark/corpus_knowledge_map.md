# P1-10MD-v1 语料知识地图

**范围**：`corpus/dalian-neusoft-movie-analysis/manifest.json` 中 `include_in_chunking=true` 的 10 篇 Markdown。本文只审计这些语料副本；项目源码、SQL 文件和其他报告不作为 Gold Truth。语料中的演示凭据已经脱敏。

**整体链路**：电影 CSV → HDFS → `MovieAnalysis.py`（PySpark / Spark Core / SparkSQL）→ HDFS 无表头结果 CSV → Sqoop export → MySQL `movie_stat_db` 的 13 张结果表 → Spring Boot / MyBatis-Plus 只读统计 API → Vue 3 / ECharts 仪表板。功能 5 仅是与功能 1 等价的 SparkSQL 临时视图，没有 HDFS 结果、MySQL 表或 API。该链路是文档描述，不能推断全部环节已通过端到端测试。

## 逐篇审计

### 1. `data/MovieAnalysis实施手册.md`

- **主题与章节**：一/整体功能（功能全景、产出物、数据流）；二/实施思路（分层解耦、输出规范、质量规则）；三/14 项功能逐项实现及后续 Sqoop；四/六类实施故障；附录/排查方法。
- **实体、技术、参数**：`MovieAnalysis.py`、Spark Core/DataFrame、SparkSQL、HDFS、`write_result()`、`movie_stat_db`、13 个 `stat_*` 结果；`YEAR=0`、`DOUBAN_SCORE=0`、`MINS=0` 的缺失口径；评分 ≥7.5；`row_number()` 每年 Top20；多值字段 split/explode。
- **流程与关联**：将统计结果写入 `/movies/analysis_results/<表名>/`；与结果结构说明、Sqoop 脚本、数据库设计构成数据链路；功能 5 不落盘。
- **证据风险**：四/问题 4 对 DOUBLE 解析仅给“解决方向”，不是已确认修复；“全脚本统一过滤伪 0”与数据库文档所记功能 B 的 `movie_year=0` 残留不完全一致。不要把排查建议写成完成事实。

### 2. `data/Sqoop导出命令脚本.md`

- **主题与章节**：执行前提、通用参数；功能 1–4、6–10、A/B/C/F 的 13 条 export 命令；功能 5 跳过；一键批量脚本。
- **实体、参数、流程**：`sqoop export`、JDBC MySQL、`--table`、`--export-dir`、HDFS 子目录与目标表同名，库为 `movie_stat_db`；示例连接 `localhost:3306`，密码在语料副本中已脱敏。
- **关联与冲突**：脚本使用 `--input-lines-terminated-by '\001'`，而《MovieAnalysis实施手册》四/问题 1 明确称该参数用于 import、export 应使用 `--lines-terminated-by` 且实际行结尾为 `\n`；《数据分析结果结构说明》附录 B 的修订示例也使用逗号字段分隔与 `\n`。因此不能将此脚本中的原命令当作可靠已修复方案。

### 3. `data/数据分析结果结构说明.md`

- **主题与章节**：0/通用落盘规则与 Spark→MySQL 类型；1–14/各功能字段结构和 HDFS 路径；附录 A/路径速查；附录 B/Sqoop 编写要点；附录 C/建表脚本。
- **实体、参数、流程**：`/movies/analysis_results`；CSV 无表头、逗号分隔、覆盖写；计数 `bigint`、均值 `double`；各表列顺序；功能 5 仅内存视图。
- **关联**：是 PySpark 输出、Sqoop 输入与 MySQL schema 对齐的主要数据契约；可与数据库设计及 API 字段进行跨文档问答。
- **模糊点**：附录称独立 `movie_stat_db.sql` 为建表事实来源，但该 SQL 不在 10MD 范围内，不能依据此语料核实真实 DDL。

### 4. `backend/API手册.md`

- **主题与章节**：1/13 个只读统计模块；2/基础地址、统一响应、状态码、分页、年份范围；3/13 模块 43 个 GET 接口及示例；4/速查表。
- **实体、参数、接口**：`Result<T>` 的 `code/message/data/timestamp`；成功 `code=0`，参数错误 400；`current=1`、`size=10`；闭区间 `startYear/endYear`；单对象无结果 `null`、列表无结果 `[]`；`/statYearRegionCount/getByRegionAndYear` 等。
- **关联与冲突**：读 MySQL 13 张结果表，供前端图表；2.1 写统计 API “鉴权：无”，但前端有本地 token 登录。两者作用域不同，不能推断后端验证前端登录。示例 JSON 数值是接口示意，不应视为真实统计数据。

### 5. `backend/后端项目实施手册.md`

- **主题与章节**：1/项目背景、技术架构、13 模块、工程结构；2/环境依赖与版本；3/本地建库、配置、启动、验证；4/Result、Entity、Mapper、Service、Controller、异常处理和分层测试；附录。
- **实体、技术、参数**：Spring Boot、MyBatis-Plus、MySQL、Maven、JDK 17；`Result<T>`；`@TableName`、`BaseMapper`、`QueryWrapper`、分页插件、`ServiceQueryChecks`、`ApiExceptionHandler`；默认 API 端口 8080。
- **流程与关联**：`Controller → Service → Mapper → Entity/表`；配合 API 手册解释接口与结果表对应；配合测试报告解释四层验证。
- **证据风险**：部署响应样例是示例值；“war 支持外部 Tomcat”是手册陈述，不能据此断言曾在外部 Tomcat 成功部署。

### 6. `backend/数据库检查与修复报告.md`

- **主题与章节**：1/修复目标；2/行数与多重集合比对；3/五张问题表及根因；4/整体重灌；5/执行结果；6/13 表修复后验证；7/遗留问题。
- **实体、参数、测试事实**：2026-09-15 的 `movie_stat_db`；`stat_year_region_count` 1→5421 行、`stat_year_top20_movie` 1819→1968 行；地区、语言、地区年均分三个脏维度表；修复后 13/13 行数与预期一致。
- **关联**：说明 Sqoop 直通原始统计与 `/db` 中清洗归一 SQL 数据的差异；补充数据库设计文档的权威数据版本说明。
- **不确定性**：功能 8 导出失败、功能 B 特殊字符丢行被写为“推断原因”，不能在 Gold Answer 中提升为已证实根因；报告验证的是与 SQL 预期数据一致，不是重新计算全链路正确性。

### 7. `backend/数据库设计文档.md`

- **主题与章节**：一/项目链路与约束；二/结果表设计原则；三/13 张表逐表字段与口径；四/测试数据规模、样例和清洗边界；五/物理/逻辑关系与实体映射；六/SQL 文件位置。
- **实体、参数、结构**：`movie_stat_db`、13 张 ADS 结果表、`utf8mb4`、无跨表物理外键；单值表 `stat_id=1`；多表按年份/地区共享逻辑维度；`stat_year_top20_movie.DOUBAN_VOTES` 为文本；13 表测试数据合计 11572 行。
- **关联**：与分析结果结构说明对齐列序、路径；与后端 Entity/Mapper 和 API 模块一一对应；与修复报告共同说明 SQL 清洗版与 Sqoop 直通版的差异。
- **冲突/边界**：本文功能 F 在功能清单标 SparkSQL，实施手册标 Spark Core；`DIM_*` 仅逻辑维度而非实际表；已知 `movie_year=0/2049` 等脏值。测试数据表中“13 个数据脚本”与修复报告“13 个 SQL 文件（建表 1、数据 12）”的文件数量描述不一致，避免以此出精确文件数题。

### 8. `backend/测试报告.md`

- **主题与章节**：一/测试目标、范围、环境、策略；二/57 类、381 用例和分层分布；三/Entity、Mapper、Service、Controller 具体覆盖；四/结论与改进建议。
- **测试事实与边界**：报告记载 381/381 通过、0 失败/错误/跳过；Mapper 集成测试连接真实 MySQL，部分查询构造测试使用 Mockito；覆盖映射、分页、条件、参数边界和 HTTP 响应。
- **关联**：可和后端实施手册共同说明测试结构；不能据此断言前端、Sqoop、HDFS 或端到端数据链路通过测试，也不能等同于覆盖率 100%。

### 9. `frontend/前端实施方案.md`

- **主题与章节**：1/目标；2/Vue 技术栈和架构；3/路由、认证、Axios、主题、12 图表、响应式及性能；4/规范；5/部署方案；6/测试方案；7/安全方案；8/监控；9/扩展计划。
- **实体、技术、参数**：Vue 3、Vite、Vue Router、ECharts、Axios、autofit.js；`/login`、`/dashboard`；`VITE_API_BASE_URL` 或 `http://${hostname}:8080`；`code===0` 业务成功；桌面 ≥1024px 用 autofit，小屏流式布局；本地登录 token 在 `localStorage`。
- **关联与边界**：调用后端统计 API 生成图表；部署/测试/监控章节包含方案和建议，不能推断已上线 Nginx/Docker/CDN 或已执行 Vitest/Playwright。前端本地认证不等于后端统计 API 鉴权。

### 10. `frontend/用户使用手册.md`

- **主题与章节**：1/系统功能；2/访问与登录；3/验证码；4/仪表板、6 指标卡、12 图表；5/图表说明；6/主题、修改密码、退出方式；7/FAQ；8/要求与版本；附录。
- **实体、参数、使用流程**：`http://localhost:8081`；4 位验证码；三种主题；登录后仪表板；未提供页面内退出按钮；数据导出、电影详情、图表类型自定义均未支持。
- **冲突/模糊**：4.3 将高分均分口径写为评分 ≥8.0，分析、数据库和 API 文档均写 ≥7.5。不能无说明地给出唯一跨系统阈值；某些宣传性“智能推荐/实时”表述没有推荐算法或实时数据管道的细节证据。默认密码已从语料副本脱敏。

## 横向关系、冲突与缺口

1. **重复且互补**：13 项统计功能在分析手册、结构说明、数据库设计、API 手册和前端两份文档重复出现。分别提供计算口径、字段契约、库表、查询端点与页面呈现；跨文档题应要求不同环节各自的证据，不能把同一句链路总述重复引用当 multi-hop。
2. **明确冲突**：Sqoop 命令脚本的 `--input-lines-terminated-by '\001'` 与实施手册修正的 `--lines-terminated-by '\n'`；高分均分阈值前端用户手册 ≥8.0 与分析/数据库/API ≥7.5；功能 F 的 Spark Core/SparkSQL 标签；SQL 数据文件数量表述。
3. **作用域差异**：前端 localStorage/token 登录与 API 手册“无需鉴权”并非直接互斥，分别描述前端路由与后端统计接口。Benchmark 应能要求受试系统区分作用域。
4. **历史快照**：数据库检查报告、后端测试报告仅证明各自记载的 2026-09-15 检查；不能推断今天的数据库或全链路状态。
5. **缺失**：这 10 篇未给出可核实的个人贡献边界、实际生产部署域名、推荐算法训练/评估、前端 E2E 测试通过数、全链路性能数据。适合作为不可回答题，但答案应表述“语料不足”，不能断言现实中不存在。
6. **敏感信息**：仅引用语料副本；不要回读来源文件中的原始演示密码。Gold Evidence 不含 `[REDACTED]` 附近的账户行。
