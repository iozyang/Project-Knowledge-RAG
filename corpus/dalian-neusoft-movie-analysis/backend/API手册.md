# API 手册

> 项目名称：MovieAnalysisAPI（电影分析管理平台后端）
> 文档版本：v1.0
> 更新日期：2026-09-15
> 文档用途：作为前端与后端项目之间进行数据交换的接口参考文档

---

## 目录

1. [功能概述](#1-功能概述)
2. [通用约定](#2-通用约定)
3. [业务接口](#3-业务接口)
   - [3.1 每年电影数量（功能1）](#31-每年电影数量功能1)
   - [3.2 高分电影平均分（功能2）](#32-高分电影平均分功能2)
   - [3.3 电影时长分布（功能3）](#33-电影时长分布功能3)
   - [3.4 不同地区电影数量（功能4）](#34-不同地区电影数量功能4)
   - [3.5 按评分区间统计电影数量（功能6）](#35-按评分区间统计电影数量功能6)
   - [3.6 地区发行量 Top50（功能7）](#36-地区发行量-top50功能7)
   - [3.7 每年各国发行量对比（功能8）](#37-每年各国发行量对比功能8)
   - [3.8 各国每年平均评分（功能9）](#38-各国每年平均评分功能9)
   - [3.9 电影语言类型统计（功能10）](#39-电影语言类型统计功能10)
   - [3.10 各电影类型数量（功能A）](#310-各电影类型数量功能a)
   - [3.11 每年评分 Top20 电影（功能B）](#311-每年评分-top20-电影功能b)
   - [3.12 演员参演电影数量 Top50（功能C）](#312-演员参演电影数量-top50功能c)
   - [3.13 各年代平均片长变化趋势（功能F）](#313-各年代平均片长变化趋势功能f)

---

## 1. 功能概述

MovieAnalysisAPI 是电影分析管理平台的 Web 后端服务，负责读取 MySQL（`movie_stat_db`）中由 PySpark 统计分析生成、并经 Sqoop 导入的 13 张统计结果表，以统一的 RESTful JSON 接口对外提供查询服务，支撑前端 ECharts 图表（柱状图、饼图、折线图、热力图、排行榜等）的数据展示。

全部接口均为**只读查询接口**（GET 请求），共覆盖 13 个统计功能模块：

| 编号 | 功能点 | 数据表 | 可视化建议 |
|------|--------|--------|-----------|
| 1 | 每年电影数量 | `stat_movie_year` | 折线/柱状图 |
| 2 | 高分电影（评分≥7.5）平均分 | `stat_high_score_avg` | 指标卡 |
| 3 | 片长最长/最短/平均 | `stat_mins_total` | 指标卡 |
| 4 | 各地区电影数量 | `stat_region_count` | 柱状图 |
| 6 | 评分区间电影数量 | `stat_score_section` | 饼图 |
| 7 | 地区发行量 Top50 | `stat_region_top50` | 条形图 |
| 8 | 每年各国发行量（年份×地区） | `stat_year_region_count` | 堆叠柱状图/热力图 |
| 9 | 各国每年平均评分 | `stat_region_year_avg_score` | 折线图 |
| 10 | 各语言电影数量 | `stat_language` | 柱状图 |
| A | 各电影类型数量 | `stat_genre_count` | 饼图/柱状图 |
| B | 每年豆瓣评分 Top20 电影 | `stat_year_top20_movie` | 排行榜/条形图 |
| C | 演员参演电影数量 Top50 | `stat_actor_top50` | 条形图 |
| F | 各年代平均片长趋势 | `stat_year_avg_mins` | 折线图 |

---

## 2. 通用约定

### 2.1 基础信息

| 项目 | 约定 |
|------|------|
| 基础地址（Base URL） | `http://{服务器IP}:8080`（本地开发默认为 `http://localhost:8080`） |
| 通信协议 | HTTP |
| 接口风格 | RESTful |
| 请求方式 | 全部为 `GET` |
| 传参方式 | URL 查询参数（Query String） |
| 返回格式 | JSON（`application/json;charset=UTF-8`） |
| 字符编码 | UTF-8 |
| 鉴权 | 无（当前版本不要求登录/令牌） |

### 2.2 统一返回结果结构

所有接口均返回如下统一结构（对应后端 `Result<T>` 类）：

| 字段 | 类型 | 说明 |
|------|------|------|
| `code` | Integer | 响应码。`0` 表示成功；`400` 表示请求参数错误 |
| `message` | String | 响应描述。成功时为 `"success"`；失败时为具体错误原因 |
| `data` | T | 业务数据。成功时为查询结果（对象或数组）；失败时为 `null` |
| `timestamp` | Long | 服务端生成响应时的时间戳（毫秒） |

**成功响应示例：**

```json
{
  "code": 0,
  "message": "success",
  "data": [
    { "movieYear": 2012, "movieCount": 128 }
  ],
  "timestamp": 1768521600000
}
```

**失败响应示例：**

```json
{
  "code": 400,
  "message": "Missing required parameter: startYear",
  "data": null,
  "timestamp": 1768521600000
}
```

### 2.3 响应码说明

| code | HTTP 状态码 | 含义 |
|------|------------|------|
| 0 | 200 | 查询成功（`data` 为空数组时也表示成功，只是无符合条件的记录） |
| 400 | 400 | 缺少必填参数：`Missing required parameter: {参数名}` |
| 400 | 400 | 参数类型不合法：`Invalid parameter type: {参数名}` |
| 400 | 400 | 参数取值不合法（如页码≤0、开始年份>结束年份、文本为空白），`message` 为具体校验说明 |

### 2.4 分页参数约定

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `current` | int | 否 | 1 | 当前页码，从 1 开始；小于等于 0 时返回 400 |
| `size` | int | 否 | 10 | 每页条数；小于等于 0 时返回 400 |

### 2.5 年份范围参数约定

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `startYear` | Integer | 是 | 开始年份（包含） |
| `endYear` | Integer | 是 | 结束年份（包含） |

- 范围查询**包含两端年份**；
- 任一年份缺失、非整数，或 `startYear > endYear` 时返回 400。

### 2.6 其他约定

- 所有接口均不需要请求体（Request Body）；
- 查询结果为空时返回 `code=0`、`data=[]`（列表）或 `data=null`（单对象），**不属于失败**；
- 名称类参数（地区名、语言名、类型名等）需与数据库中的值精确匹配（区分大小写），传空白字符串会返回 400；
- 前端应以 `code` 字段（而非 HTTP 状态码）作为业务成功/失败的判断依据。

---

## 3. 业务接口

### 3.1 每年电影数量（功能1）

对应数据表 `stat_movie_year`，返回字段：`movieYear`（上映年份，Integer）、`movieCount`（该年份电影数量，Long）。

#### 3.1.1 查询全部年份数据

| 项目 | 内容 |
|------|------|
| 功能点名 | 查询全部每年电影数量 |
| URL | `/statMovieYear/listAll` |
| 请求方式 | GET |
| 传入参数 | 无 |

**返回结果（正确）：**

```json
{
  "code": 0,
  "message": "success",
  "data": [
    { "movieYear": 2012, "movieCount": 128 },
    { "movieYear": 2013, "movieCount": 145 }
  ],
  "timestamp": 1768521600000
}
```

**返回结果（失败）：** 服务异常时返回非 0 的 `code` 与错误 `message`。

**注意事项：** 数据量较大时建议前端使用 3.1.2 的年份范围接口按需加载。

#### 3.1.2 按年份范围查询

| 项目 | 内容 |
|------|------|
| 功能点名 | 查询指定年份范围内的每年电影数量 |
| URL | `/statMovieYear/listByYearRange` |
| 请求方式 | GET |
| 传入参数 | `startYear`（Integer，必填）：开始年份；`endYear`（Integer，必填）：结束年份 |

**请求示例：** `GET /statMovieYear/listByYearRange?startYear=2010&endYear=2015`

**返回结果（正确）：** 同 3.1.1，仅包含范围内的年份数据。

**返回结果（失败）：**

```json
{
  "code": 400,
  "message": "startYear must be less than or equal to endYear",
  "data": null,
  "timestamp": 1768521600000
}
```

**注意事项：** 范围包含两端年份；参数缺失或类型不合法同样返回 400。

---

### 3.2 高分电影平均分（功能2）

对应数据表 `stat_high_score_avg`，返回字段：`statId`（常量主键，固定为 1，Integer）、`highScoreAvg`（评分≥7.5 电影的平均分，Double）。表中仅一条记录。

#### 3.2.1 查询全部数据

| 项目 | 内容 |
|------|------|
| 功能点名 | 查询高分电影平均分（全部） |
| URL | `/statHighScoreAvg/listAll` |
| 请求方式 | GET |
| 传入参数 | 无 |

**返回结果（正确）：**

```json
{
  "code": 0,
  "message": "success",
  "data": [
    { "statId": 1, "highScoreAvg": 8.21 }
  ],
  "timestamp": 1768521600000
}
```

**注意事项：** 该表为单记录表，推荐前端直接使用 3.2.2 接口。

#### 3.2.2 按统计 ID 查询

| 项目 | 内容 |
|------|------|
| 功能点名 | 按统计 ID 查询高分电影平均分 |
| URL | `/statHighScoreAvg/getByStatId` |
| 请求方式 | GET |
| 传入参数 | `statId`（Integer，必填）：统计 ID，固定传 `1` |

**请求示例：** `GET /statHighScoreAvg/getByStatId?statId=1`

**返回结果（正确）：**

```json
{
  "code": 0,
  "message": "success",
  "data": { "statId": 1, "highScoreAvg": 8.21 },
  "timestamp": 1768521600000
}
```

**返回结果（失败）：** `statId` 缺失或非整数时返回 400（`Missing required parameter: statId` 或 `Invalid parameter type: statId`）。

**注意事项：** `statId` 固定为 `1`，传其他值时 `data` 为 `null`（仍为成功响应）。

---

### 3.3 电影时长分布（功能3）

对应数据表 `stat_mins_total`，返回字段：`statId`（常量主键，固定为 1，Integer）、`maxMins`（最长片长/分钟，Double）、`minMins`（最短片长/分钟，Double）、`avgMins`（平均片长/分钟，Double）。表中仅一条记录。

#### 3.3.1 查询全部数据

| 项目 | 内容 |
|------|------|
| 功能点名 | 查询电影时长统计（全部） |
| URL | `/statMinsTotal/listAll` |
| 请求方式 | GET |
| 传入参数 | 无 |

**返回结果（正确）：**

```json
{
  "code": 0,
  "message": "success",
  "data": [
    { "statId": 1, "maxMins": 321.0, "minMins": 45.0, "avgMins": 104.56 }
  ],
  "timestamp": 1768521600000
}
```

#### 3.3.2 按统计 ID 查询

| 项目 | 内容 |
|------|------|
| 功能点名 | 按统计 ID 查询电影时长统计 |
| URL | `/statMinsTotal/getByStatId` |
| 请求方式 | GET |
| 传入参数 | `statId`（Integer，必填）：统计 ID，固定传 `1` |

**请求示例：** `GET /statMinsTotal/getByStatId?statId=1`

**返回结果（正确）：**

```json
{
  "code": 0,
  "message": "success",
  "data": { "statId": 1, "maxMins": 321.0, "minMins": 45.0, "avgMins": 104.56 },
  "timestamp": 1768521600000
}
```

**返回结果（失败）：** `statId` 缺失或非整数时返回 400。

**注意事项：** 适合前端"指标卡"展示；`statId` 固定为 `1`。

---

### 3.4 不同地区电影数量（功能4）

对应数据表 `stat_region_count`，返回字段：`regionName`（制片国家/地区名称，String）、`movieCnt`（该地区电影数量，Long）。

#### 3.4.1 查询全部数据

| 项目 | 内容 |
|------|------|
| 功能点名 | 查询各地区电影数量（全部） |
| URL | `/statRegionCount/listAll` |
| 请求方式 | GET |
| 传入参数 | 无 |

**返回结果（正确）：**

```json
{
  "code": 0,
  "message": "success",
  "data": [
    { "regionName": "美国", "movieCnt": 5200 },
    { "regionName": "中国大陆", "movieCnt": 3100 }
  ],
  "timestamp": 1768521600000
}
```

#### 3.4.2 分页查询

| 项目 | 内容 |
|------|------|
| 功能点名 | 分页查询各地区电影数量 |
| URL | `/statRegionCount/listByPage` |
| 请求方式 | GET |
| 传入参数 | `current`（int，选填，默认 1）：页码；`size`（int，选填，默认 10）：每页条数 |

**请求示例：** `GET /statRegionCount/listByPage?current=1&size=10`

**返回结果（正确）：** 同 3.4.1，仅返回当前页数据。

**返回结果（失败）：** `current` 或 `size` ≤ 0 时返回 400。

#### 3.4.3 按地区名称查询

| 项目 | 内容 |
|------|------|
| 功能点名 | 按地区名称查询电影数量 |
| URL | `/statRegionCount/getByRegionName` |
| 请求方式 | GET |
| 传入参数 | `regionName`（String，必填）：制片国家/地区名称 |

**请求示例：** `GET /statRegionCount/getByRegionName?regionName=美国`

**返回结果（正确）：**

```json
{
  "code": 0,
  "message": "success",
  "data": { "regionName": "美国", "movieCnt": 5200 },
  "timestamp": 1768521600000
}
```

**返回结果（失败）：** `regionName` 缺失或传空白字符串时返回 400。

**注意事项：** 名称需与库中数据精确匹配；不存在时 `data` 为 `null`（仍为成功响应）。

---

### 3.5 按评分区间统计电影数量（功能6）

对应数据表 `stat_score_section`，返回字段：`scoreSection`（评分区间，String，取值：`0-6分`/`6-8分`/`8-10分`/`无评分`）、`movieCount`（该区间电影数量，Long）。

#### 3.5.1 查询全部数据

| 项目 | 内容 |
|------|------|
| 功能点名 | 查询各评分区间电影数量（全部） |
| URL | `/statScoreSection/listAll` |
| 请求方式 | GET |
| 传入参数 | 无 |

**返回结果（正确）：**

```json
{
  "code": 0,
  "message": "success",
  "data": [
    { "scoreSection": "0-6分", "movieCount": 1800 },
    { "scoreSection": "6-8分", "movieCount": 5600 },
    { "scoreSection": "8-10分", "movieCount": 2400 },
    { "scoreSection": "无评分", "movieCount": 700 }
  ],
  "timestamp": 1768521600000
}
```

#### 3.5.2 分页查询

| 项目 | 内容 |
|------|------|
| 功能点名 | 分页查询各评分区间电影数量 |
| URL | `/statScoreSection/listByPage` |
| 请求方式 | GET |
| 传入参数 | `current`（int，选填，默认 1）：页码；`size`（int，选填，默认 10）：每页条数 |

**请求示例：** `GET /statScoreSection/listByPage?current=1&size=10`

**返回结果（正确）：** 同 3.5.1，仅返回当前页数据。

**返回结果（失败）：** `current` 或 `size` ≤ 0 时返回 400。

#### 3.5.3 按评分区间查询

| 项目 | 内容 |
|------|------|
| 功能点名 | 按评分区间查询电影数量 |
| URL | `/statScoreSection/getByScoreSection` |
| 请求方式 | GET |
| 传入参数 | `scoreSection`（String，必填）：评分区间，取值 `0-6分`/`6-8分`/`8-10分`/`无评分` |

**请求示例：** `GET /statScoreSection/getByScoreSection?scoreSection=8-10分`

**返回结果（正确）：**

```json
{
  "code": 0,
  "message": "success",
  "data": { "scoreSection": "8-10分", "movieCount": 2400 },
  "timestamp": 1768521600000
}
```

**返回结果（失败）：** `scoreSection` 缺失或传空白字符串时返回 400。

**注意事项：** 参数值须带"分"字（如 `8-10分`），URL 中中文需进行 UTF-8 编码。

---

### 3.6 地区发行量 Top50（功能7）

对应数据表 `stat_region_top50`，返回字段：`regionName`（制片国家/地区名称，String）、`total`（该地区电影发行量，Long）。

#### 3.6.1 查询全部数据

| 项目 | 内容 |
|------|------|
| 功能点名 | 查询地区发行量 Top50（全部） |
| URL | `/statRegionTop50/listAll` |
| 请求方式 | GET |
| 传入参数 | 无 |

**返回结果（正确）：**

```json
{
  "code": 0,
  "message": "success",
  "data": [
    { "regionName": "美国", "total": 5200 },
    { "regionName": "中国大陆", "total": 3100 }
  ],
  "timestamp": 1768521600000
}
```

#### 3.6.2 分页查询

| 项目 | 内容 |
|------|------|
| 功能点名 | 分页查询地区发行量 Top50 |
| URL | `/statRegionTop50/listByPage` |
| 请求方式 | GET |
| 传入参数 | `current`（int，选填，默认 1）：页码；`size`（int，选填，默认 10）：每页条数 |

**请求示例：** `GET /statRegionTop50/listByPage?current=1&size=10`

**返回结果（正确）：** 同 3.6.1，仅返回当前页数据。

**返回结果（失败）：** `current` 或 `size` ≤ 0 时返回 400。

#### 3.6.3 按地区名称查询

| 项目 | 内容 |
|------|------|
| 功能点名 | 按地区名称查询发行量 |
| URL | `/statRegionTop50/getByRegionName` |
| 请求方式 | GET |
| 传入参数 | `regionName`（String，必填）：制片国家/地区名称 |

**请求示例：** `GET /statRegionTop50/getByRegionName?regionName=美国`

**返回结果（正确）：**

```json
{
  "code": 0,
  "message": "success",
  "data": { "regionName": "美国", "total": 5200 },
  "timestamp": 1768521600000
}
```

**返回结果（失败）：** `regionName` 缺失或传空白字符串时返回 400。

**注意事项：** 仅收录发行量排名前 50 的地区；不存在时 `data` 为 `null`。

---

### 3.7 每年各国发行量对比（功能8）

对应数据表 `stat_year_region_count`，返回字段：`movieYear`（上映年份，Integer）、`regionName`（制片国家/地区名称，String）、`regionYearCount`（该年份该地区电影数量，Long）。

#### 3.7.1 查询全部数据

| 项目 | 内容 |
|------|------|
| 功能点名 | 查询每年各国发行量（全部） |
| URL | `/statYearRegionCount/listAll` |
| 请求方式 | GET |
| 传入参数 | 无 |

**返回结果（正确）：**

```json
{
  "code": 0,
  "message": "success",
  "data": [
    { "movieYear": 2012, "regionName": "美国", "regionYearCount": 320 },
    { "movieYear": 2012, "regionName": "中国大陆", "regionYearCount": 210 }
  ],
  "timestamp": 1768521600000
}
```

**注意事项：** 数据量为"年份×地区"笛卡尔积，建议前端优先使用 3.7.3～3.7.6 的条件查询接口。

#### 3.7.2 分页查询

| 项目 | 内容 |
|------|------|
| 功能点名 | 分页查询每年各国发行量 |
| URL | `/statYearRegionCount/listByPage` |
| 请求方式 | GET |
| 传入参数 | `current`（int，选填，默认 1）：页码；`size`（int，选填，默认 10）：每页条数 |

**请求示例：** `GET /statYearRegionCount/listByPage?current=1&size=10`

**返回结果（正确）：** 同 3.7.1，仅返回当前页数据。

**返回结果（失败）：** `current` 或 `size` ≤ 0 时返回 400。

#### 3.7.3 按地区名称查询

| 项目 | 内容 |
|------|------|
| 功能点名 | 按地区名称查询历年发行量 |
| URL | `/statYearRegionCount/listByRegionName` |
| 请求方式 | GET |
| 传入参数 | `regionName`（String，必填）：制片国家/地区名称 |

**请求示例：** `GET /statYearRegionCount/listByRegionName?regionName=美国`

**返回结果（正确）：** 同 3.7.1，仅返回该地区的历年数据。

**返回结果（失败）：** `regionName` 缺失或传空白字符串时返回 400。

#### 3.7.4 按年份查询

| 项目 | 内容 |
|------|------|
| 功能点名 | 按年份查询各国发行量 |
| URL | `/statYearRegionCount/listByMovieYear` |
| 请求方式 | GET |
| 传入参数 | `movieYear`（Integer，必填）：上映年份 |

**请求示例：** `GET /statYearRegionCount/listByMovieYear?movieYear=2012`

**返回结果（正确）：** 同 3.7.1，仅返回该年份各地区数据。

**返回结果（失败）：** `movieYear` 缺失、为 null 或非整数时返回 400。

#### 3.7.5 按年份范围查询

| 项目 | 内容 |
|------|------|
| 功能点名 | 按年份范围查询各国发行量 |
| URL | `/statYearRegionCount/listByYearRange` |
| 请求方式 | GET |
| 传入参数 | `startYear`（Integer，必填）：开始年份（含）；`endYear`（Integer，必填）：结束年份（含） |

**请求示例：** `GET /statYearRegionCount/listByYearRange?startYear=2010&endYear=2015`

**返回结果（正确）：** 同 3.7.1，仅返回范围内的数据。

**返回结果（失败）：** 年份缺失、非整数或 `startYear > endYear` 时返回 400。

#### 3.7.6 按地区+年份精确查询

| 项目 | 内容 |
|------|------|
| 功能点名 | 按地区和年份查询发行量 |
| URL | `/statYearRegionCount/getByRegionAndYear` |
| 请求方式 | GET |
| 传入参数 | `regionName`（String，必填）：地区名称；`movieYear`（Integer，必填）：年份 |

**请求示例：** `GET /statYearRegionCount/getByRegionAndYear?regionName=美国&movieYear=2012`

**返回结果（正确）：**

```json
{
  "code": 0,
  "message": "success",
  "data": { "movieYear": 2012, "regionName": "美国", "regionYearCount": 320 },
  "timestamp": 1768521600000
}
```

**返回结果（失败）：** 任一参数缺失、名称空白或年份为 null 时返回 400。

**注意事项：** 不存在时 `data` 为 `null`；若库中存在统计值冲突的重复记录，后端会抛出异常。

---

### 3.8 各国每年平均评分（功能9）

对应数据表 `stat_region_year_avg_score`，返回字段：`regionName`（制片国家/地区名称，String）、`movieYear`（上映年份，Integer）、`regionScoreAvg`（该地区该年份电影平均豆瓣评分，Double）。

#### 3.8.1 查询全部数据

| 项目 | 内容 |
|------|------|
| 功能点名 | 查询各国每年平均评分（全部） |
| URL | `/statRegionYearAvgScore/listAll` |
| 请求方式 | GET |
| 传入参数 | 无 |

**返回结果（正确）：**

```json
{
  "code": 0,
  "message": "success",
  "data": [
    { "regionName": "美国", "movieYear": 2012, "regionScoreAvg": 7.12 },
    { "regionName": "中国大陆", "movieYear": 2012, "regionScoreAvg": 6.58 }
  ],
  "timestamp": 1768521600000
}
```

**注意事项：** 数据量为"年份×地区"笛卡尔积，建议前端优先使用 3.8.3～3.8.6 的条件查询接口。

#### 3.8.2 分页查询

| 项目 | 内容 |
|------|------|
| 功能点名 | 分页查询各国每年平均评分 |
| URL | `/statRegionYearAvgScore/listByPage` |
| 请求方式 | GET |
| 传入参数 | `current`（int，选填，默认 1）：页码；`size`（int，选填，默认 10）：每页条数 |

**请求示例：** `GET /statRegionYearAvgScore/listByPage?current=1&size=10`

**返回结果（正确）：** 同 3.8.1，仅返回当前页数据。

**返回结果（失败）：** `current` 或 `size` ≤ 0 时返回 400。

#### 3.8.3 按地区名称查询

| 项目 | 内容 |
|------|------|
| 功能点名 | 按地区名称查询历年平均评分 |
| URL | `/statRegionYearAvgScore/listByRegionName` |
| 请求方式 | GET |
| 传入参数 | `regionName`（String，必填）：制片国家/地区名称 |

**请求示例：** `GET /statRegionYearAvgScore/listByRegionName?regionName=美国`

**返回结果（正确）：** 同 3.8.1，仅返回该地区历年数据。

**返回结果（失败）：** `regionName` 缺失或传空白字符串时返回 400。

#### 3.8.4 按年份查询

| 项目 | 内容 |
|------|------|
| 功能点名 | 按年份查询各国平均评分 |
| URL | `/statRegionYearAvgScore/listByMovieYear` |
| 请求方式 | GET |
| 传入参数 | `movieYear`（Integer，必填）：上映年份 |

**请求示例：** `GET /statRegionYearAvgScore/listByMovieYear?movieYear=2012`

**返回结果（正确）：** 同 3.8.1，仅返回该年份各地区数据。

**返回结果（失败）：** `movieYear` 缺失、为 null 或非整数时返回 400。

#### 3.8.5 按年份范围查询

| 项目 | 内容 |
|------|------|
| 功能点名 | 按年份范围查询各国平均评分 |
| URL | `/statRegionYearAvgScore/listByYearRange` |
| 请求方式 | GET |
| 传入参数 | `startYear`（Integer，必填）：开始年份（含）；`endYear`（Integer，必填）：结束年份（含） |

**请求示例：** `GET /statRegionYearAvgScore/listByYearRange?startYear=2010&endYear=2015`

**返回结果（正确）：** 同 3.8.1，仅返回范围内的数据。

**返回结果（失败）：** 年份缺失、非整数或 `startYear > endYear` 时返回 400。

#### 3.8.6 按地区+年份精确查询

| 项目 | 内容 |
|------|------|
| 功能点名 | 按地区和年份查询平均评分 |
| URL | `/statRegionYearAvgScore/getByRegionAndYear` |
| 请求方式 | GET |
| 传入参数 | `regionName`（String，必填）：地区名称；`movieYear`（Integer，必填）：年份 |

**请求示例：** `GET /statRegionYearAvgScore/getByRegionAndYear?regionName=美国&movieYear=2012`

**返回结果（正确）：**

```json
{
  "code": 0,
  "message": "success",
  "data": { "regionName": "美国", "movieYear": 2012, "regionScoreAvg": 7.12 },
  "timestamp": 1768521600000
}
```

**返回结果（失败）：** 任一参数缺失、名称空白或年份为 null 时返回 400。

**注意事项：** 不存在时 `data` 为 `null`；若库中存在统计值冲突的重复记录，后端会抛出异常。

---

### 3.9 电影语言类型统计（功能10）

对应数据表 `stat_language`，返回字段：`languageName`（语言名称，String，如"汉语普通话"）、`languageCount`（该语言电影数量，Long）。

#### 3.9.1 查询全部数据

| 项目 | 内容 |
|------|------|
| 功能点名 | 查询各语言电影数量（全部） |
| URL | `/statLanguage/listAll` |
| 请求方式 | GET |
| 传入参数 | 无 |

**返回结果（正确）：**

```json
{
  "code": 0,
  "message": "success",
  "data": [
    { "languageName": "汉语普通话", "languageCount": 4100 },
    { "languageName": "英语", "languageCount": 6200 }
  ],
  "timestamp": 1768521600000
}
```

#### 3.9.2 分页查询

| 项目 | 内容 |
|------|------|
| 功能点名 | 分页查询各语言电影数量 |
| URL | `/statLanguage/listByPage` |
| 请求方式 | GET |
| 传入参数 | `current`（int，选填，默认 1）：页码；`size`（int，选填，默认 10）：每页条数 |

**请求示例：** `GET /statLanguage/listByPage?current=1&size=10`

**返回结果（正确）：** 同 3.9.1，仅返回当前页数据。

**返回结果（失败）：** `current` 或 `size` ≤ 0 时返回 400。

#### 3.9.3 按语言名称查询

| 项目 | 内容 |
|------|------|
| 功能点名 | 按语言名称查询电影数量 |
| URL | `/statLanguage/getByLanguageName` |
| 请求方式 | GET |
| 传入参数 | `languageName`（String，必填）：语言名称 |

**请求示例：** `GET /statLanguage/getByLanguageName?languageName=汉语普通话`

**返回结果（正确）：**

```json
{
  "code": 0,
  "message": "success",
  "data": { "languageName": "汉语普通话", "languageCount": 4100 },
  "timestamp": 1768521600000
}
```

**返回结果（失败）：** `languageName` 缺失或传空白字符串时返回 400。

**注意事项：** 名称需精确匹配；URL 中中文需进行 UTF-8 编码。

---

### 3.10 各电影类型数量（功能A）

对应数据表 `stat_genre_count`，返回字段：`genreName`（电影类型名称，String，如"喜剧"）、`genreCount`（该类型电影数量，Long）。

#### 3.10.1 查询全部数据

| 项目 | 内容 |
|------|------|
| 功能点名 | 查询各电影类型数量（全部） |
| URL | `/statGenreCount/listAll` |
| 请求方式 | GET |
| 传入参数 | 无 |

**返回结果（正确）：**

```json
{
  "code": 0,
  "message": "success",
  "data": [
    { "genreName": "喜剧", "genreCount": 2600 },
    { "genreName": "剧情", "genreCount": 4100 }
  ],
  "timestamp": 1768521600000
}
```

#### 3.10.2 按类型名称查询

| 项目 | 内容 |
|------|------|
| 功能点名 | 按电影类型名称查询数量 |
| URL | `/statGenreCount/getByGenreName` |
| 请求方式 | GET |
| 传入参数 | `genreName`（String，必填）：电影类型名称 |

**请求示例：** `GET /statGenreCount/getByGenreName?genreName=喜剧`

**返回结果（正确）：**

```json
{
  "code": 0,
  "message": "success",
  "data": { "genreName": "喜剧", "genreCount": 2600 },
  "timestamp": 1768521600000
}
```

**返回结果（失败）：** `genreName` 缺失或传空白字符串时返回 400。

**注意事项：** 名称需精确匹配；URL 中中文需进行 UTF-8 编码。

---

### 3.11 每年评分 Top20 电影（功能B）

对应数据表 `stat_year_top20_movie`，返回字段：`movieYear`（上映年份，Integer）、`movieId`（电影 ID，对应豆瓣 DOUBAN_ID，String）、`name`（电影名称，String）、`doubanScore`（豆瓣评分，Double）、`doubanVotes`（豆瓣投票数，String，原文本未做类型转换）。

#### 3.11.1 查询全部数据

| 项目 | 内容 |
|------|------|
| 功能点名 | 查询每年评分 Top20 电影（全部） |
| URL | `/statYearTop20Movie/listAll` |
| 请求方式 | GET |
| 传入参数 | 无 |

**返回结果（正确）：**

```json
{
  "code": 0,
  "message": "success",
  "data": [
    { "movieYear": 2012, "movieId": "1292052", "name": "肖申克的救赎", "doubanScore": 9.7, "doubanVotes": "1000000" }
  ],
  "timestamp": 1768521600000
}
```

**注意事项：** 数据量较大（每年最多 20 条），建议前端优先使用 3.11.3～3.11.4 的条件查询接口。

#### 3.11.2 分页查询

| 项目 | 内容 |
|------|------|
| 功能点名 | 分页查询每年评分 Top20 电影 |
| URL | `/statYearTop20Movie/listByPage` |
| 请求方式 | GET |
| 传入参数 | `current`（int，选填，默认 1）：页码；`size`（int，选填，默认 10）：每页条数 |

**请求示例：** `GET /statYearTop20Movie/listByPage?current=1&size=10`

**返回结果（正确）：** 同 3.11.1，仅返回当前页数据。

**返回结果（失败）：** `current` 或 `size` ≤ 0 时返回 400。

#### 3.11.3 按年份查询

| 项目 | 内容 |
|------|------|
| 功能点名 | 按年份查询评分 Top20 电影 |
| URL | `/statYearTop20Movie/listByMovieYear` |
| 请求方式 | GET |
| 传入参数 | `movieYear`（Integer，必填）：上映年份 |

**请求示例：** `GET /statYearTop20Movie/listByMovieYear?movieYear=2012`

**返回结果（正确）：** 同 3.11.1，仅返回该年份的 Top20 电影数据。

**返回结果（失败）：** `movieYear` 缺失、为 null 或非整数时返回 400。

#### 3.11.4 按年份范围查询

| 项目 | 内容 |
|------|------|
| 功能点名 | 按年份范围查询评分 Top20 电影 |
| URL | `/statYearTop20Movie/listByYearRange` |
| 请求方式 | GET |
| 传入参数 | `startYear`（Integer，必填）：开始年份（含）；`endYear`（Integer，必填）：结束年份（含） |

**请求示例：** `GET /statYearTop20Movie/listByYearRange?startYear=2010&endYear=2015`

**返回结果（正确）：** 同 3.11.1，仅返回范围内的数据。

**返回结果（失败）：** 年份缺失、非整数或 `startYear > endYear` 时返回 400。

**注意事项：** `doubanVotes` 为文本类型，前端如需数值排序请自行转换（注意可能存在非数字内容）。

---

### 3.12 演员参演电影数量 Top50（功能C）

对应数据表 `stat_actor_top50`，返回字段：`personName`（演员姓名，String）、`actedMovieCnt`（该演员参演的电影数量，Long）。

#### 3.12.1 查询全部数据

| 项目 | 内容 |
|------|------|
| 功能点名 | 查询演员参演电影数量 Top50（全部） |
| URL | `/statActorTop50/listAll` |
| 请求方式 | GET |
| 传入参数 | 无 |

**返回结果（正确）：**

```json
{
  "code": 0,
  "message": "success",
  "data": [
    { "personName": "演员甲", "actedMovieCnt": 85 },
    { "personName": "演员乙", "actedMovieCnt": 72 }
  ],
  "timestamp": 1768521600000
}
```

#### 3.12.2 按演员姓名查询

| 项目 | 内容 |
|------|------|
| 功能点名 | 按演员姓名查询参演数量 |
| URL | `/statActorTop50/listByActorName` |
| 请求方式 | GET |
| 传入参数 | `personName`（String，必填）：演员姓名 |

**请求示例：** `GET /statActorTop50/listByActorName?personName=演员甲`

**返回结果（正确）：**

```json
{
  "code": 0,
  "message": "success",
  "data": [
    { "personName": "演员甲", "actedMovieCnt": 85 }
  ],
  "timestamp": 1768521600000
}
```

**返回结果（失败）：** `personName` 缺失时返回 400。

#### 3.12.3 分页查询

| 项目 | 内容 |
|------|------|
| 功能点名 | 分页查询演员参演数量 Top50 |
| URL | `/statActorTop50/listByPage` |
| 请求方式 | GET |
| 传入参数 | `current`（int，选填，默认 1）：页码；`size`（int，选填，默认 10）：每页条数 |

**请求示例：** `GET /statActorTop50/listByPage?current=1&size=10`

**返回结果（正确）：** 同 3.12.1，仅返回当前页数据。

**返回结果（失败）：** `current` 或 `size` ≤ 0 时返回 400。

**注意事项：** 仅收录参演数量排名前 50 的演员；按姓名查询不存在时 `data` 为空数组。

---

### 3.13 各年代平均片长变化趋势（功能F）

对应数据表 `stat_year_avg_mins`，返回字段：`movieYear`（上映年份，Integer）、`avgMinsYear`（该年份电影平均片长/分钟，Double）。

#### 3.13.1 查询全部数据

| 项目 | 内容 |
|------|------|
| 功能点名 | 查询各年份平均片长（全部） |
| URL | `/statYearAvgMins/listAll` |
| 请求方式 | GET |
| 传入参数 | 无 |

**返回结果（正确）：**

```json
{
  "code": 0,
  "message": "success",
  "data": [
    { "movieYear": 2012, "avgMinsYear": 101.5 },
    { "movieYear": 2013, "avgMinsYear": 103.2 }
  ],
  "timestamp": 1768521600000
}
```

#### 3.13.2 分页查询

| 项目 | 内容 |
|------|------|
| 功能点名 | 分页查询各年份平均片长 |
| URL | `/statYearAvgMins/listByPage` |
| 请求方式 | GET |
| 传入参数 | `current`（int，选填，默认 1）：页码；`size`（int，选填，默认 10）：每页条数 |

**请求示例：** `GET /statYearAvgMins/listByPage?current=1&size=10`

**返回结果（正确）：** 同 3.13.1，仅返回当前页数据。

**返回结果（失败）：** `current` 或 `size` ≤ 0 时返回 400。

#### 3.13.3 按年份查询

| 项目 | 内容 |
|------|------|
| 功能点名 | 按年份查询平均片长 |
| URL | `/statYearAvgMins/getByMovieYear` |
| 请求方式 | GET |
| 传入参数 | `movieYear`（Integer，必填）：上映年份 |

**请求示例：** `GET /statYearAvgMins/getByMovieYear?movieYear=2012`

**返回结果（正确）：**

```json
{
  "code": 0,
  "message": "success",
  "data": { "movieYear": 2012, "avgMinsYear": 101.5 },
  "timestamp": 1768521600000
}
```

**返回结果（失败）：** `movieYear` 缺失、为 null 或非整数时返回 400。

#### 3.13.4 按年份范围查询

| 项目 | 内容 |
|------|------|
| 功能点名 | 按年份范围查询平均片长 |
| URL | `/statYearAvgMins/listByYearRange` |
| 请求方式 | GET |
| 传入参数 | `startYear`（Integer，必填）：开始年份（含）；`endYear`（Integer，必填）：结束年份（含） |

**请求示例：** `GET /statYearAvgMins/listByYearRange?startYear=2010&endYear=2015`

**返回结果（正确）：** 同 3.13.1，仅返回范围内的数据。

**返回结果（失败）：** 年份缺失、非整数或 `startYear > endYear` 时返回 400。

---

## 4. 附录：接口清单速查表

| 序号 | 功能模块 | URL | 请求方式 | 参数 |
|------|---------|-----|---------|------|
| 1 | 每年电影数量 | `/statMovieYear/listAll` | GET | 无 |
| 2 | 每年电影数量 | `/statMovieYear/listByYearRange` | GET | startYear, endYear |
| 3 | 高分电影平均分 | `/statHighScoreAvg/listAll` | GET | 无 |
| 4 | 高分电影平均分 | `/statHighScoreAvg/getByStatId` | GET | statId |
| 5 | 电影时长分布 | `/statMinsTotal/listAll` | GET | 无 |
| 6 | 电影时长分布 | `/statMinsTotal/getByStatId` | GET | statId |
| 7 | 地区电影数量 | `/statRegionCount/listAll` | GET | 无 |
| 8 | 地区电影数量 | `/statRegionCount/listByPage` | GET | current, size |
| 9 | 地区电影数量 | `/statRegionCount/getByRegionName` | GET | regionName |
| 10 | 评分区间统计 | `/statScoreSection/listAll` | GET | 无 |
| 11 | 评分区间统计 | `/statScoreSection/listByPage` | GET | current, size |
| 12 | 评分区间统计 | `/statScoreSection/getByScoreSection` | GET | scoreSection |
| 13 | 地区发行量 Top50 | `/statRegionTop50/listAll` | GET | 无 |
| 14 | 地区发行量 Top50 | `/statRegionTop50/listByPage` | GET | current, size |
| 15 | 地区发行量 Top50 | `/statRegionTop50/getByRegionName` | GET | regionName |
| 16 | 每年各国发行量 | `/statYearRegionCount/listAll` | GET | 无 |
| 17 | 每年各国发行量 | `/statYearRegionCount/listByPage` | GET | current, size |
| 18 | 每年各国发行量 | `/statYearRegionCount/listByRegionName` | GET | regionName |
| 19 | 每年各国发行量 | `/statYearRegionCount/listByMovieYear` | GET | movieYear |
| 20 | 每年各国发行量 | `/statYearRegionCount/listByYearRange` | GET | startYear, endYear |
| 21 | 每年各国发行量 | `/statYearRegionCount/getByRegionAndYear` | GET | regionName, movieYear |
| 22 | 各国每年平均评分 | `/statRegionYearAvgScore/listAll` | GET | 无 |
| 23 | 各国每年平均评分 | `/statRegionYearAvgScore/listByPage` | GET | current, size |
| 24 | 各国每年平均评分 | `/statRegionYearAvgScore/listByRegionName` | GET | regionName |
| 25 | 各国每年平均评分 | `/statRegionYearAvgScore/listByMovieYear` | GET | movieYear |
| 26 | 各国每年平均评分 | `/statRegionYearAvgScore/listByYearRange` | GET | startYear, endYear |
| 27 | 各国每年平均评分 | `/statRegionYearAvgScore/getByRegionAndYear` | GET | regionName, movieYear |
| 28 | 语言类型统计 | `/statLanguage/listAll` | GET | 无 |
| 29 | 语言类型统计 | `/statLanguage/listByPage` | GET | current, size |
| 30 | 语言类型统计 | `/statLanguage/getByLanguageName` | GET | languageName |
| 31 | 电影类型数量 | `/statGenreCount/listAll` | GET | 无 |
| 32 | 电影类型数量 | `/statGenreCount/getByGenreName` | GET | genreName |
| 33 | 每年 Top20 电影 | `/statYearTop20Movie/listAll` | GET | 无 |
| 34 | 每年 Top20 电影 | `/statYearTop20Movie/listByPage` | GET | current, size |
| 35 | 每年 Top20 电影 | `/statYearTop20Movie/listByMovieYear` | GET | movieYear |
| 36 | 每年 Top20 电影 | `/statYearTop20Movie/listByYearRange` | GET | startYear, endYear |
| 37 | 演员 Top50 | `/statActorTop50/listAll` | GET | 无 |
| 38 | 演员 Top50 | `/statActorTop50/listByActorName` | GET | personName |
| 39 | 演员 Top50 | `/statActorTop50/listByPage` | GET | current, size |
| 40 | 年均片长趋势 | `/statYearAvgMins/listAll` | GET | 无 |
| 41 | 年均片长趋势 | `/statYearAvgMins/listByPage` | GET | current, size |
| 42 | 年均片长趋势 | `/statYearAvgMins/getByMovieYear` | GET | movieYear |
| 43 | 年均片长趋势 | `/statYearAvgMins/listByYearRange` | GET | startYear, endYear |


