import asyncio
import importlib
import inspect
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from demo import cli

generator = importlib.import_module("src.generation.4_qwen_flash_generator")
STATIC_DIR = Path(__file__).resolve().parent / "static"


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)


@asynccontextmanager
async def lifespan(app: FastAPI):
    cli.initialize()
    yield

    client = getattr(generator, "client", None)
    if client is not None:
        close = getattr(client, "close", None)
        if close is not None:
            result = close()
            if inspect.isawaitable(result):
                await result


app = FastAPI(
    title="RAG Project Knowledge Demo",
    version="1.0.1",
    lifespan=lifespan,
)


@app.get("/")
async def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "retrieval": "heading-aware + BM25 Top20 + Dense Top20 + RRF Top20 + Rerank Top5",
        "generator": generator.GENERATOR_MODEL,
        "query_rewrite": False,
    }


@app.post("/api/ask")
async def ask(request: AskRequest):
    question = request.question.strip()

    if not question:
        raise HTTPException(status_code=400, detail="question 不能为空")

    total_start = time.perf_counter()

    try:
        reranked, retrieval_ms = await asyncio.to_thread(
            cli.retrieve,
            question,
        )

        contexts = cli.build_contexts(reranked)

        generation = await generator.generate_answer(
            question=question,
            contexts=contexts,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"{type(exc).__name__}: {exc}",
        ) from exc

    total_ms = (time.perf_counter() - total_start) * 1000

    sources = []
    for source_id, item in enumerate(reranked, start=1):
        chunk = item["chunk"]
        sources.append(
            {
                "source_id": f"S{source_id}",
                "source": chunk["source"],
                "heading": chunk["heading_path"],
                "content": chunk["content"],
                "rerank_score": round(float(item["rerank_score"]), 6),
            }
        )

    return {
        "question": question,
        "answer": generation["answer"],
        "citations": generation["citations"],
        "sources": sources,
        "trace": {
            "retrieval_ms": retrieval_ms,
            "generation_ms": generation["latency_ms"],
            "total_ms": round(total_ms, 2),
            "tokens": generation["total_tokens"],
            "parse_success": generation["parse_success"],
        },
        "config": {
            "query_rewrite": False,
            "candidate_k": 20,
            "final_k": 5,
            "generator": generator.GENERATOR_MODEL,
        },
    }
