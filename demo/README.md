# Demo

冻结后的端到端问答演示。检索与生成都复用已经固定的 Pipeline，不在这里改 Chunking、Rerank 或 Prompt。

```text
Heading-aware Section
→ Recursive Chunking (500 / 100)
→ BM25 Top20 + Dense Top20
→ RRF Top20
→ Qwen Reranker
→ Final Top5
→ qwen3.8-flash + G1.1
```

包含两个入口：

- `cli.py`：终端里逐条提问
- `api.py`：FastAPI，并托管 `static/index.html`

当前只做单轮问答。没有 Query Rewrite，也不保留多轮对话历史。Top5 证据支撑不了问题核心时，回答是 `根据现有资料无法确定。`

---

## 目录

```text
demo/
├─ api.py              # FastAPI 入口
├─ cli.py              # CLI 入口，检索逻辑也供 API 复用
├─ static/index.html   # Web UI
└─ README.md
```

命令都在仓库根目录执行。`demo` 会导入 `src/` 和 `evaluation/`，不在 `demo/` 目录里启动。

---

## 启动前

在仓库根目录安装依赖，并按 `.env.example` 准备 `.env`：

```powershell
pip install -r requirements.txt
```

```env
DASHSCOPE_API_KEY=your_api_key
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
```

Embedding、Reranker 和 Generator 都读这两个变量。没有 `DASHSCOPE_API_KEY` 时，初始化或提问会直接失败。

---

## CLI

```powershell
python -m demo.cli
```

启动时会加载语料 Chunk、Embedding 和 BM25。看到 `Ready.` 之后输入问题。`exit`、`quit` 或 `q` 退出。

每次提问打印三块结果：

- **Answer**：带 `[S1]` 这类行内引用的回答
- **Sources**：Top5 的文件、标题路径和 Rerank 分数
- **Trace**：检索耗时、生成耗时、总耗时、Token 和 JSON 是否解析成功

---

## Web

```powershell
python -m uvicorn demo.api:app --host 127.0.0.1 --port 8000
```

| 地址 | 作用 |
| --- | --- |
| http://127.0.0.1:8000 | 问答页面 |
| http://127.0.0.1:8000/docs | Swagger |
| `GET /api/health` | 当前检索链路和生成模型 |
| `POST /api/ask` | 提交问题，请求体为 `{"question": "..."}` |

页面展示回答、行内引用、Top5 来源（文件、标题路径、证据正文、Rerank 分数），以及检索、生成、总耗时、Token 和解析状态。

`POST /api/ask` 的响应字段：

```text
question
answer
citations
sources[]        source_id / source / heading / content / rerank_score
trace            retrieval_ms / generation_ms / total_ms / tokens / parse_success
config           query_rewrite / candidate_k / final_k / generator
```

问题不能为空，最长 1000 字。

在线 Demo：https://project-knowledge-rag.onrender.com
