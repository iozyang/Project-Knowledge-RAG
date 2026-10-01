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
# G1.1 Grounded Prompt
# 来源：E3 Failure Analysis
#
# 目标：
# 1. 减少过度拒答
# 2. 保留部分可回答信息
# 3. 强制正文 inline citation
# 4. 减少规则竞争
# ============================================================

SYSTEM_PROMPT = """
你是一个软件项目知识问答助手。

请根据提供的 Context 回答 Question，并遵守以下规则：

1. 只使用 Context 明确支持的信息，不使用外部知识，
   不自行补充或推测。

2. 优先回答 Context 能明确支持的内容。
   如果问题包含多个部分，应回答其中有证据支持的部分。
   只有当 Context 对问题的核心信息完全没有证据时，
   才回答“根据现有资料无法确定。”
   不要因为部分信息缺失而拒绝整个问题。

3. 如果 Context 明确给出互相冲突的信息，
   同时说明不同口径及各自证据，不自行选择其中一个。

4. 每个关键事实都必须在 answer 正文中紧跟对应证据编号。
   例如：
   “后端使用 Spring Boot [S1]，前端使用 Vue [S2]。”

   citations 数组只汇总 answer 正文中实际使用过的证据编号，
   不能代替正文中的 [S1]、[S2]。

5. 只输出一个合法 JSON，
   不要输出 Markdown、解释或任何 JSON 之外的文字。

输出格式：

{
  "answer": "回答正文",
  "citations": ["S1", "S2"]
}

如果核心信息完全没有证据，则输出：

{
  "answer": "根据现有资料无法确定。",
  "citations": []
}
""".strip()


# ============================================================
# Context 格式化
# ============================================================

def build_context_text(contexts):
    blocks = []

    for index, context in enumerate(
        contexts,
        start=1,
    ):
        source_id = f"S{index}"

        source = context.get(
            "source",
            "unknown",
        )

        heading_path = context.get(
            "heading_path",
            "",
        )

        content = context.get(
            "content",
            "",
        )

        block = [
            f"[{source_id}]",
            f"Source: {source}",
        ]

        if heading_path:
            block.append(
                f"Heading: {heading_path}"
            )

        block.append(
            f"Content:\n{content}"
        )

        blocks.append(
            "\n".join(block)
        )

    return "\n\n".join(blocks)


# ============================================================
# Citation 兜底提取
# ============================================================

def extract_citations(text):
    citations = re.findall(
        r"\bS\d+\b",
        text,
    )

    return list(
        dict.fromkeys(citations)
    )


# ============================================================
# JSON 解析
# ============================================================

def parse_response(raw_text):
    text = raw_text.strip()

    if text.startswith("```"):
        text = re.sub(
            r"^```(?:json)?\s*",
            "",
            text,
        )

        text = re.sub(
            r"\s*```$",
            "",
            text,
        )

    try:
        data = json.loads(text)

        answer = str(
            data.get(
                "answer",
                "",
            )
        ).strip()

        citations = data.get(
            "citations",
            [],
        )

        if not isinstance(
            citations,
            list,
        ):
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

            "citations": extract_citations(
                raw_text
            ),

            "parse_success": False,
        }


# ============================================================
# Generation
# ============================================================

async def generate_answer(
    question,
    contexts,
):
    context_text = build_context_text(
        contexts
    )

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

    latency_ms = (
        time.perf_counter()
        - start
    ) * 1000

    raw_text = (
        response
        .choices[0]
        .message
        .content
        or ""
    )

    parsed = parse_response(
        raw_text
    )

    usage = response.usage

    return {
        "model": GENERATOR_MODEL,

        "answer": (
            parsed["answer"]
        ),

        "citations": (
            parsed["citations"]
        ),

        "parse_success": (
            parsed["parse_success"]
        ),

        "latency_ms": round(
            latency_ms,
            2,
        ),

        "input_tokens": (
            usage.prompt_tokens
            if usage
            else None
        ),

        "output_tokens": (
            usage.completion_tokens
            if usage
            else None
        ),

        "total_tokens": (
            usage.total_tokens
            if usage
            else None
        ),

        "raw_response": raw_text,
    }