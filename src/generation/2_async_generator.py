import json
import os
import re
import time

from dotenv import load_dotenv
from openai import AsyncOpenAI


load_dotenv()


GENERATOR_MODEL = os.getenv(
    "GENERATOR_MODEL",
    "deepseek-r1-distill-qwen-7b",
)

API_KEY = os.getenv("DASHSCOPE_API_KEY")

BASE_URL = os.getenv(
    "DASHSCOPE_BASE_URL",
    "https://dashscope.aliyuncs.com/compatible-mode/v1",
)

if not API_KEY:
    raise RuntimeError("未找到 DASHSCOPE_API_KEY")

client = AsyncOpenAI(
    api_key=API_KEY,
    base_url=BASE_URL,
)


# ============================================================
# G0 Naive Prompt
# 与 v1 完全一致
# ============================================================

SYSTEM_PROMPT = """
你是一个软件项目知识问答助手。

请根据提供的 Context 回答 Question。
回答应简洁、准确。

如果引用了 Context 中的信息，请在回答中使用对应的证据编号，
例如 [S1]、[S2]。

最终输出 JSON：

{
  "answer": "回答正文",
  "citations": ["S1", "S2"]
}
""".strip()


def build_context_text(contexts):
    blocks = []

    for index, context in enumerate(contexts, start=1):
        source_id = f"S{index}"
        source = context.get("source", "unknown")
        heading_path = context.get("heading_path", "")
        content = context.get("content", "")

        block = [
            f"[{source_id}]",
            f"Source: {source}",
        ]

        if heading_path:
            block.append(f"Heading: {heading_path}")

        block.append(f"Content:\n{content}")
        blocks.append("\n".join(block))

    return "\n\n".join(blocks)


def extract_citations(text):
    citations = re.findall(r"\bS\d+\b", text)
    return list(dict.fromkeys(citations))


def parse_response(raw_text):
    text = raw_text.strip()

    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

    try:
        data = json.loads(text)

        answer = str(data.get("answer", "")).strip()
        citations = data.get("citations", [])

        if not isinstance(citations, list):
            citations = []

        citations = [
            str(citation).strip()
            for citation in citations
            if str(citation).strip()
        ]

        return {
            "answer": answer,
            "citations": citations,
            "parse_success": True,
        }

    except json.JSONDecodeError:
        return {
            "answer": raw_text.strip(),
            "citations": extract_citations(raw_text),
            "parse_success": False,
        }


async def generate_answer(question, contexts):
    context_text = build_context_text(contexts)

    user_prompt = f"""
Question:

{question}

Context:

{context_text}
""".strip()

    start = time.perf_counter()

    response = await client.chat.completions.create(
        model=GENERATOR_MODEL,
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": user_prompt,
            },
        ],
        temperature=0,
        max_tokens=800,
        extra_body={
            "enable_thinking": False,
        },
    )

    latency_ms = (time.perf_counter() - start) * 1000

    raw_text = response.choices[0].message.content or ""
    parsed = parse_response(raw_text)

    usage = response.usage

    return {
        "model": GENERATOR_MODEL,
        "answer": parsed["answer"],
        "citations": parsed["citations"],
        "parse_success": parsed["parse_success"],
        "latency_ms": round(latency_ms, 2),

        "input_tokens": usage.prompt_tokens if usage else None,
        "output_tokens": usage.completion_tokens if usage else None,
        "total_tokens": usage.total_tokens if usage else None,

        "raw_response": raw_text,
    }