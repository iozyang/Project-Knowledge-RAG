# RAG Web Demo

放到你现有项目：

```text
rag/
├─ demo/
│  ├─ cli.py
│  ├─ api.py
│  └─ static/
│     └─ index.html
├─ src/
├─ evaluation/
├─ cache/
└─ corpus/
```

如果还没有 FastAPI / Uvicorn：

```powershell
pip install fastapi uvicorn
```

启动：

```powershell
python -m uvicorn demo.api:app --reload --port 8000
```

浏览器：

```text
http://127.0.0.1:8000
```

Swagger：

```text
http://127.0.0.1:8000/docs
```

当前范围：单轮问答；不做 Query Rewrite；不做多轮历史；不修改 Frozen Retrieval / Generation。
