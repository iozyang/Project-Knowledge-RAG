# 电影分析管理平台 —— 实施手册

> 本文档基于 `MovieAnalysis.py`（PySpark 电影分析脚本）及其配套的建库建表、Sqoop 导出流程编写，记录本阶段的整体功能、实施思路、具体步骤，以及实施过程中遇到的问题与解决方式。

---

## 一、本阶段完成的整体功能

本阶段实现了一条完整的「大数据电影分析」链路，将豆瓣电影数据从 HDFS 原始数据，经过 Spark 统计分析，最终导入 MySQL 供前端（ECharts）可视化展示。

### 1.1 功能全景

| 编号 | 功能点 | 实现方式 | 结果表 / 视图 |
| --- | --- | --- | --- |
| 1 | 每年电影数量 | Spark Core | `stat_movie_year` |
| 2 | 高分电影平均分 | Spark Core | `stat_high_score_avg` |
| 3 | 电影时长分布（最长/最短/平均） | Spark Core | `stat_mins_total` |
| 4 | 不同地区电影数量 | Spark Core | `stat_region_count` |
| 5 | 按上映年份统计电影数量 | SparkSQL | `stat_movie_year_sql`（仅视图，不落盘） |
| 6 | 按评分区间统计电影数量 | SparkSQL | `stat_score_section` |
| 7 | 地域发行量 Top50 | SparkSQL | `stat_region_top50` |
| 8 | 每年各国发行量对比统计 | SparkSQL | `stat_year_region_count` |
| 9 | 各国每年平均评分统计 | SparkSQL | `stat_region_year_avg_score` |
| 10 | 电影语言类型统计 | SparkSQL | `stat_language` |
| A | 各电影类型（GENRES）数量统计 | SparkSQL（ECharts） | `stat_genre_count` |
| B | 每年豆瓣评分 Top20 电影 | 窗口函数（ECharts） | `stat_year_top20_movie` |
| C | 演员参演电影数量 Top50 | Spark Core（ECharts） | `stat_actor_top50` |
| F | 各年代平均片长变化趋势 | Spark Core（ECharts） | `stat_year_avg_mins` |

### 1.2 配套产出物

- `MovieAnalysis.py`：PySpark 统计分析脚本（核心）
- `数据分析结果结构说明.md`：各功能结果的数据结构、HDFS 路径说明
- `movie_stat_db.sql`：MySQL 建库建表脚本（库名 `movie_stat_db`，13 张表）
- `Sqoop导出命令脚本.md`：13 条 Sqoop 导出命令
- 本实施手册

### 1.3 整体数据流

```
HDFS 原始数据(movies.csv)
      │  spark-submit MovieAnalysis.py
      ▼
HDFS 统计结果(/movies/analysis_results/<表名>/part-*)
      │  sqoop export
      ▼
MySQL 统计库(movie_stat_db, 13 张表)
      │  后端查询
      ▼
前端 ECharts 可视化展示
```

---

## 二、实施思路

### 2.1 总体思路

1. **分层解耦**：分析脚本只负责「统计 + 落盘」，结果以标准 CSV 写入 HDFS；数据入库与展示交给 Sqoop 和前端，各层职责清晰。
2. **双实现对照**：功能 1-4 用 Spark Core（DataFrame API），功能 5-10 用 SparkSQL，既覆盖两种编程范式，也便于相互印证结果。
3. **统一输出规范**：所有统计结果通过 `write_result()` 统一写出，保证格式一致（无表头 CSV、`,` 分隔），为 Sqoop 导出和 MySQL 建表提供唯一依据。
4. **数据质量约定**：全脚本统一「脏数据」的过滤规则（`YEAR=0`、`DOUBAN_SCORE=0`、`MINS=0` 均视为缺失）。

### 2.2 关键设计原则

| 原则 | 说明 |
| --- | --- |
| 单值统计补主键 | 功能 2、3 的 `agg` 结果只有一行，用 `lit(1)` 补 `stat_id` 主键列，便于入库 |
| 多值字段拆分 | `REGIONS/LANGUAGES/GENRES/ACTOR_IDS` 用 `split + explode` 展开后再聚合 |
| 类型显式转换 | CSV 读入全为 string，数值运算前必须 `cast`，避免字符串比较错误 |
| TopN 用窗口函数 | 功能 B 的「每年 Top20」必须用 `row_number` 窗口函数，`groupBy` 取不到具体行 |
| 不落盘的功能 | 功能 5 与功能 1 结果等价，只注册视图、不重复落盘 |

---

## 三、每个功能实现的具体步骤

### 3.1 功能 1：每年电影数量（Spark Core）

**步骤**：
1. 过滤 `YEAR` 非空且不等于 0 的记录（排除未上映数据）
2. 将 `YEAR` 转成 `int` 并命名为 `movie_year`
3. 按 `movie_year` 分组计数，重命名为 `movie_count`
4. 按年份升序排序
5. 注册视图 `stat_movie_year_core`，写出到 HDFS `stat_movie_year`

**输出结构**：`movie_year(int)`, `movie_count(bigint)`

---

### 3.2 功能 2：高分电影平均分（Spark Core）

**步骤**：
1. 过滤评分 `>= 7.5` 的记录（先 `cast("double")` 再比较）
2. 用 `avg()` 求平均分，命名为 `high_score_avg`
3. 用 `lit(1)` 补常量主键列 `stat_id`
4. 写出到 HDFS `stat_high_score_avg`

**输出结构**：`stat_id(int)`, `high_score_avg(double)`

---

### 3.3 功能 3：电影时长分布（Spark Core）

**步骤**：
1. 过滤 `MINS > 0` 的记录（排除片长缺失）
2. 一次 `agg` 同时计算 `max/min/avg`
3. 补 `stat_id` 主键列
4. 写出到 HDFS `stat_mins_total`

**输出结构**：`stat_id(int)`, `max_mins(double)`, `min_mins(double)`, `avg_mins(double)`

---

### 3.4 功能 4：不同地区电影数量（Spark Core）

**步骤**：
1. 过滤 `REGIONS` 非空
2. 按 `' / '` 分隔符 `split` 拆分，`explode` 展开成多行
3. 过滤拆分后为空的行
4. 按 `region_name` 分组计数，降序排列
5. 写出到 HDFS `stat_region_count`

**输出结构**：`region_name(string)`, `movie_cnt(bigint)`

---

### 3.5 功能 5：按上映年份统计电影数量（SparkSQL）

**步骤**：
1. 将 `moviesDF` 注册为临时视图 `movies`
2. 用 SQL 的 `CAST + COUNT + GROUP BY` 实现与功能 1 等价的统计
3. 注册视图 `stat_movie_year_sql`

**说明**：与功能 1 结果等价，仅注册视图、不落盘，用于 SparkSQL 对照演示。

---

### 3.6 功能 6：按评分区间统计电影数量（SparkSQL）

**步骤**：
1. 用 `CASE WHEN` 将评分离散化为 4 个区间：`0-6分` / `6-8分` / `8-10分` / `无评分`
2. 按区间分组计数
3. 写出到 HDFS `stat_score_section`

**输出结构**：`score_section(string)`, `movie_count(bigint)`

---

### 3.7 功能 7：地域发行量 Top50（SparkSQL）

**步骤**：
1. 子查询里 `explode(split(REGIONS, ' / '))` 展开地区
2. 按地区分组计数，降序取前 50
3. 写出到 HDFS `stat_region_top50`

**输出结构**：`region_name(string)`, `total(bigint)`

---

### 3.8 功能 8：每年各国发行量对比统计（SparkSQL）

**步骤**：
1. 子查询同时 `CAST(YEAR)` 和 `explode(split(REGIONS))`
2. 外层过滤 `movie_year` 非空且不为 0
3. 按 `(movie_year, region_name)` 分组计数
4. 写出到 HDFS `stat_year_region_count`

**输出结构**：`movie_year(int)`, `region_name(string)`, `region_year_count(bigint)`

---

### 3.9 功能 9：各国每年平均评分统计（SparkSQL）

**步骤**：
1. 子查询展开地区、转换年份和评分，并过滤 `DOUBAN_SCORE > 0`
2. 按 `(region_name, movie_year)` 分组求 `AVG`
3. 写出到 HDFS `stat_region_year_avg_score`

**输出结构**：`region_name(string)`, `movie_year(int)`, `region_score_avg(double)`

---

### 3.10 功能 10：电影语言类型统计（SparkSQL）

**步骤**：
1. `explode(split(LANGUAGES, ' / '))` 展开语言
2. 按语言分组计数，降序
3. 写出到 HDFS `stat_language`

**输出结构**：`language_name(string)`, `language_count(bigint)`

---

### 3.11 功能 A：各电影类型（GENRES）数量统计

**步骤**：
1. 按 `/`（无空格）分隔符拆分 `GENRES` 并展开
2. 按类型分组计数，降序
3. 写出到 HDFS `stat_genre_count`

**输出结构**：`genre_name(string)`, `genre_count(bigint)`

---

### 3.12 功能 B：每年豆瓣评分 Top20 电影

**步骤**：
1. 定义窗口 `Window.partitionBy("YEAR").orderBy(评分 desc)`
2. 用 `row_number()` 给每年内按评分排名
3. 过滤 `rn <= 20` 取前 20
4. 选择年份、电影ID、名称、评分、投票数
5. 写出到 HDFS `stat_year_top20_movie`

**输出结构**：`movie_year(int)`, `MOVIE_ID(string)`, `NAME(string)`, `DOUBAN_SCORE(double)`, `DOUBAN_VOTES(string)`

---

### 3.13 功能 C：演员参演电影数量 Top50

**步骤**：
1. 按 `\\|` 拆分 `ACTOR_IDS` 并展开
2. 取 `:` 前的演员姓名
3. 按姓名分组计数，降序取前 50
4. 写出到 HDFS `stat_actor_top50`

**输出结构**：`person_name(string)`, `acted_movie_cnt(bigint)`

---

### 3.14 功能 F：各年代平均片长变化趋势

**步骤**：
1. 过滤 `YEAR` 非空且 `MINS > 0`
2. 按年份分组求片长均值
3. 按年份升序
4. 写出到 HDFS `stat_year_avg_mins`

**输出结构**：`movie_year(int)`, `avg_mins_year(double)`

---

### 3.15 后续环节（建库建表 + Sqoop 导出）

**建库建表**：
```bash
mysql -uroot -proot < movie_stat_db.sql
```

**Sqoop 导出**（以功能 1 为例）：
```bash
sqoop export \
  --connect 'jdbc:mysql://localhost:3306/movie_stat_db?useUnicode=true&characterEncoding=utf8&useSSL=false' \
  --username root \
  --password [REDACTED] \
  --table stat_movie_year \
  --columns 'movie_year,movie_count' \
  --export-dir /movies/analysis_results/stat_movie_year \
  --fields-terminated-by ',' \
  --lines-terminated-by '\n' \
  --input-null-string '\\N' \
  --input-null-non-string '\\N' \
  --num-mappers 1
```

---

## 四、总结：实现过程中出现的问题

### 问题 1：Sqoop 参数用错（`--input-lines-terminated-by '\001'`）

- **现象**：Sqoop 导出时 `Map input records=0`、`Exported 0 records`，任务失败。
- **原因**：
  1. `--input-lines-terminated-by` 是 **import** 的参数，export 应使用 `--lines-terminated-by`；
  2. `\001`（SOH 控制符）与 HDFS 文件实际的 `\n`（换行）不匹配。
- **解决**：改用正确参数 `--fields-terminated-by ',' --lines-terminated-by '\n'`，并明确字段分隔符。

### 问题 2：`_SUCCESS` 文件干扰

- **现象**：Spark 写出的目录里含 `_SUCCESS`（0 字节标志文件），Sqoop 可能将其误当作输入。
- **解决**：导出前可先删除 `hdfs dfs -rm <目录>/_SUCCESS`，或用 `--num-mappers 1` 规避。

### 问题 3：列顺序错位（`movie_year` 与 `movie_count` 反了）

- **现象**：`stat_movie_year` 表里 `movie_year` 列存的是数量，`movie_count` 列存的是年份。
- **排查**：确认 HDFS 文件顺序正确（年份在前）、MySQL 表结构正确，问题出在 Sqoop 的列映射。
- **解决**：导出时显式指定 `--columns 'movie_year,movie_count'`，强制列顺序映射。

### 问题 4：小数（DOUBLE）字段导入报 `NumberFormatException`

- **现象**：功能 2、3 等含 `DOUBLE` 字段的表导出失败，报错：
  ```
  NumberFormatException: For input string: "8.015465249856296"
  at java.lang.Integer.parseInt(...)
  ```
- **排查过程**：
  1. 确认 MySQL 表字段类型正确（`double`），排除建表错误；
  2. 升级 MySQL 驱动 `5.1.49 → 8.0.33`，问题依旧；
  3. 定位到 Sqoop 生成代码时错误地用 `Integer.parseInt` 解析 `DOUBLE` 字段（列映射/类型映射异常）。
- **解决方向**：
  1. 优先尝试加 `--columns` 显式声明列顺序（与问题 3 同源，很可能是列映射错乱导致 `DOUBLE` 值被映射到 `INT` 列上）；
  2. 若仍未解决，可临时将 `DOUBLE` 列改为 `VARCHAR` 绕过 `Integer.parseInt`。

### 问题 5：YARN 日志聚合未开启，故障难排查

- **现象**：任务失败后 `yarn logs` 查不到日志（`Can not find any log file`）。
- **解决**：
  1. 直接查本地 `userlogs`：`/usr/local/hadoop/logs/userlogs/<application_id>/container_*/syslog`；
  2. 建议在 `yarn-site.xml` 开启日志聚合：
     ```xml
     <property>
       <name>yarn.log-aggregation-enable</name>
       <value>true</value>
     </property>
     ```

### 问题 6：数据质量约定（易忽略）

- **现象**：`YEAR=0`、`DOUBAN_SCORE=0.0`、`MINS=0.0` 在数据集中表示「缺失/未上映」，若不过滤会导致统计结果失真（如平均分被 0 分拉低、最长片长统计出 0）。
- **解决**：全脚本统一在统计前过滤这些「伪 0 值」，规则见脚本顶部注释。

---

## 附：问题排查方法论总结

1. **先看 map 任务真实异常**：`Export job failed` 只是表象，真正错误在 `userlogs` 的 syslog 里；
2. **分隔符必须三处一致**：Spark 写出（`CSV_SEP`）、Sqoop 参数（`--fields-terminated-by`）、MySQL 表结构；
3. **列顺序必须严格对齐**：结果 CSV 无表头，Sqoop 按列顺序导入，任何错位都会导致数据错乱或类型解析错误；
4. **类型映射是高频坑**：`DOUBLE` 字段在 Sqoop 1.4.7 中存在映射异常，必要时用 `--columns` 显式指定或改 `VARCHAR` 绕过。
