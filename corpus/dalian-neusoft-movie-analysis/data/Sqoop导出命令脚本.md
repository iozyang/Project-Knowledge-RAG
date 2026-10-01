# Sqoop 导出命令脚本

> 以下 13 个 Sqoop 导出命令，将 `MovieAnalysis.py` 统计后写入 HDFS 的结果，导入 MySQL 库 `movie_stat_db` 的对应表。
>
> **执行前提**：
> 1. 已执行 `movie_stat_db.sql` 完成建库建表；
> 2. `MovieAnalysis.py` 已运行完成，结果已写入 HDFS `/movies/analysis_results/` 目录；
> 3. MySQL 服务已启动，账号密码为 `root/[REDACTED]`，连接地址 `localhost:3306`。
>
> **命令通用参数说明**：
> - `--connect`：JDBC 连接串，`useUnicode=true&characterEncoding=utf8` 保证中文不乱码，`useSSL=false` 关闭 SSL
> - `--export-dir`：HDFS 中结果数据的子目录（与 `write_result` 写出的文件夹名一致）
> - `--table`：MySQL 目标表（与 HDFS 子目录同名）
> - `--input-lines-terminated-by '\001'`：指定 HDFS 源文件的行结束符

---

## 功能 1：每年电影数量

将统计结果「各上映年份的电影数量」从 HDFS 导入 MySQL 表 `stat_movie_year`。

```bash
sqoop export \
  --connect 'jdbc:mysql://localhost:3306/movie_stat_db?useUnicode=true&characterEncoding=utf8&useSSL=false' \
  --username root \
  --password [REDACTED] \
  --table stat_movie_year \
  --export-dir /movies/analysis_results/stat_movie_year \
  --input-lines-terminated-by '\001'
```

## 功能 2：高分电影平均分

将统计结果「高分电影（评分>=7.5）的平均分」从 HDFS 导入 MySQL 表 `stat_high_score_avg`。

```bash
sqoop export \
  --connect 'jdbc:mysql://localhost:3306/movie_stat_db?useUnicode=true&characterEncoding=utf8&useSSL=false' \
  --username root \
  --password [REDACTED] \
  --table stat_high_score_avg \
  --export-dir /movies/analysis_results/stat_high_score_avg \
  --input-lines-terminated-by '\001'
```

## 功能 3：电影时长分布（最长/最短/平均）

将统计结果「电影片长的最长、最短、平均值」从 HDFS 导入 MySQL 表 `stat_mins_total`。

```bash
sqoop export \
  --connect 'jdbc:mysql://localhost:3306/movie_stat_db?useUnicode=true&characterEncoding=utf8&useSSL=false' \
  --username root \
  --password [REDACTED] \
  --table stat_mins_total \
  --export-dir /movies/analysis_results/stat_mins_total \
  --input-lines-terminated-by '\001'
```

## 功能 4：不同地区电影数量

将统计结果「各制片国家/地区的电影数量」从 HDFS 导入 MySQL 表 `stat_region_count`。

```bash
sqoop export \
  --connect 'jdbc:mysql://localhost:3306/movie_stat_db?useUnicode=true&characterEncoding=utf8&useSSL=false' \
  --username root \
  --password [REDACTED] \
  --table stat_region_count \
  --export-dir /movies/analysis_results/stat_region_count \
  --input-lines-terminated-by '\001' \
  --num-mappers 1 \
  --verbose
```

## 功能 5：按上映年份统计电影数量（SQL 版）

该功能仅注册临时视图、**不落盘到 HDFS**，无需 Sqoop 导出，跳过。

## 功能 6：按评分区间统计电影数量

将统计结果「各评分区间的电影数量」从 HDFS 导入 MySQL 表 `stat_score_section`。

```bash
sqoop export \
  --connect 'jdbc:mysql://localhost:3306/movie_stat_db?useUnicode=true&characterEncoding=utf8&useSSL=false' \
  --username root \
  --password [REDACTED] \
  --table stat_score_section \
  --export-dir /movies/analysis_results/stat_score_section \
  --input-lines-terminated-by '\001'
```

## 功能 7：地域发行量 Top50

将统计结果「电影发行量最多的前 50 个地区」从 HDFS 导入 MySQL 表 `stat_region_top50`。

```bash
sqoop export \
  --connect 'jdbc:mysql://localhost:3306/movie_stat_db?useUnicode=true&characterEncoding=utf8&useSSL=false' \
  --username root \
  --password [REDACTED] \
  --table stat_region_top50 \
  --export-dir /movies/analysis_results/stat_region_top50 \
  --input-lines-terminated-by '\001'
```

## 功能 8：每年各国发行量对比统计

将统计结果「各年份×各地区的电影发行量」从 HDFS 导入 MySQL 表 `stat_year_region_count`。

```bash
sqoop export \
  --connect 'jdbc:mysql://localhost:3306/movie_stat_db?useUnicode=true&characterEncoding=utf8&useSSL=false' \
  --username root \
  --password [REDACTED] \
  --table stat_year_region_count \
  --export-dir /movies/analysis_results/stat_year_region_count \
  --input-lines-terminated-by '\001'
```

## 功能 9：各国每年平均评分统计

将统计结果「各地区×各年份电影的平均评分」从 HDFS 导入 MySQL 表 `stat_region_year_avg_score`。

```bash
sqoop export \
  --connect 'jdbc:mysql://localhost:3306/movie_stat_db?useUnicode=true&characterEncoding=utf8&useSSL=false' \
  --username root \
  --password [REDACTED] \
  --table stat_region_year_avg_score \
  --export-dir /movies/analysis_results/stat_region_year_avg_score \
  --input-lines-terminated-by '\001'
```

## 功能 10：电影语言类型统计

将统计结果「各语言的电影数量」从 HDFS 导入 MySQL 表 `stat_language`。

```bash
sqoop export \
  --connect 'jdbc:mysql://localhost:3306/movie_stat_db?useUnicode=true&characterEncoding=utf8&useSSL=false' \
  --username root \
  --password [REDACTED] \
  --table stat_language \
  --export-dir /movies/analysis_results/stat_language \
  --input-lines-terminated-by '\001'
```

## 功能 A：各电影类型（GENRES）数量统计

将统计结果「各电影类型的数量」从 HDFS 导入 MySQL 表 `stat_genre_count`。

```bash
sqoop export \
  --connect 'jdbc:mysql://localhost:3306/movie_stat_db?useUnicode=true&characterEncoding=utf8&useSSL=false' \
  --username root \
  --password [REDACTED] \
  --table stat_genre_count \
  --export-dir /movies/analysis_results/stat_genre_count \
  --input-lines-terminated-by '\001'
```

## 功能 B：每年豆瓣评分 Top20 电影

将统计结果「各年份评分最高的前 20 部电影」从 HDFS 导入 MySQL 表 `stat_year_top20_movie`。

```bash
sqoop export \
  --connect 'jdbc:mysql://localhost:3306/movie_stat_db?useUnicode=true&characterEncoding=utf8&useSSL=false' \
  --username root \
  --password [REDACTED] \
  --table stat_year_top20_movie \
  --export-dir /movies/analysis_results/stat_year_top20_movie \
  --input-lines-terminated-by '\001'
```

## 功能 C：演员参演电影数量 Top50

将统计结果「参演电影数量最多的前 50 名演员」从 HDFS 导入 MySQL 表 `stat_actor_top50`。

```bash
sqoop export \
  --connect 'jdbc:mysql://localhost:3306/movie_stat_db?useUnicode=true&characterEncoding=utf8&useSSL=false' \
  --username root \
  --password [REDACTED] \
  --table stat_actor_top50 \
  --export-dir /movies/analysis_results/stat_actor_top50 \
  --input-lines-terminated-by '\001'
```

## 功能 F：各年代平均片长变化趋势

将统计结果「各年份电影的平均片长」从 HDFS 导入 MySQL 表 `stat_year_avg_mins`。

```bash
sqoop export \
  --connect 'jdbc:mysql://localhost:3306/movie_stat_db?useUnicode=true&characterEncoding=utf8&useSSL=false' \
  --username root \
  --password [REDACTED] \
  --table stat_year_avg_mins \
  --export-dir /movies/analysis_results/stat_year_avg_mins \
  --input-lines-terminated-by '\001'
```

---

## 一键批量执行（可选）

以下脚本按顺序执行上述 13 条 Sqoop 导出命令，方便一次性完成全部导入：

```bash
#!/bin/bash
# 电影分析结果批量导出脚本：HDFS -> MySQL

CONNECT='jdbc:mysql://localhost:3306/movie_stat_db?useUnicode=true&characterEncoding=utf8&useSSL=false'
USERNAME='root'
PASSWORD='[REDACTED]'

# 定义 表名=HDFS子目录 的映射
tables=(
  stat_movie_year
  stat_high_score_avg
  stat_mins_total
  stat_region_count
  stat_score_section
  stat_region_top50
  stat_year_region_count
  stat_region_year_avg_score
  stat_language
  stat_genre_count
  stat_year_top20_movie
  stat_actor_top50
  stat_year_avg_mins
)

for t in "${tables[@]}"; do
  echo ">>> 正在导出 ${t} ..."
  sqoop export \
    --connect "$CONNECT" \
    --username "$USERNAME" \
    --password "$PASSWORD" \
    --table "$t" \
    --export-dir "/movies/analysis_results/$t" \
    --input-lines-terminated-by '\001'
  echo ">>> ${t} 导出完成"
done
```
