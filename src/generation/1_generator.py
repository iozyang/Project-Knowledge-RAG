import json
import os
import re
import time

from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()


# ============================================================
# 配置
# ============================================================

# GENERATOR_MODEL = os.getenv("GENERATOR_MODEL")
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

client = OpenAI(api_key=API_KEY, base_url=BASE_URL)


# ============================================================
# G0 Baseline Prompt
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


# ============================================================
# Context 格式化
# ============================================================

def build_context_text(contexts):
    """
    将 Top5 Context 格式化为：

    [S1]
    Source: ...
    Heading: ...
    Content:
    ...
    """

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


# ============================================================
# Citation 兜底提取
# ============================================================

def extract_citations(text):
    """
    如果模型 JSON 格式异常，
    从原始文本中兜底提取 S1 / S2 / ...
    """

    citations = re.findall(r"\bS\d+\b", text)

    # 去重并保持原顺序
    return list(dict.fromkeys(citations))


# ============================================================
# JSON 解析
# ============================================================

def parse_response(raw_text):
    """
    正常情况：解析模型返回的 JSON。

    异常情况：
    保留原始回答，并尝试提取 Citation。
    """

    text = raw_text.strip()

    # 去掉 ```json ... ```
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


# ============================================================
# Generation
# ============================================================

def generate_answer(question, contexts):
    """
    G0 Generation Baseline。

    输入：
        question
        Frozen Retrieval Top5 Context

    输出：
        answer
        citations
        latency
        token usage
    """

    context_text = build_context_text(contexts)

    user_prompt = f"""
Question:

{question}

Context:

{context_text}
""".strip()

    # --------------------------------------------------------
    # API
    # --------------------------------------------------------

    start_time = time.perf_counter()

    response = client.chat.completions.create(
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
        extra_body={"enable_thinking": False},
    )

    latency_ms = (time.perf_counter() - start_time) * 1000

    # --------------------------------------------------------
    # Response
    # --------------------------------------------------------

    raw_text = response.choices[0].message.content or ""
    parsed = parse_response(raw_text)

    # --------------------------------------------------------
    # Token Usage
    # --------------------------------------------------------

    usage = getattr(response, "usage", None)

    input_tokens = getattr(usage, "prompt_tokens", None) if usage else None
    output_tokens = getattr(usage, "completion_tokens", None) if usage else None
    total_tokens = getattr(usage, "total_tokens", None) if usage else None

    # --------------------------------------------------------
    # Result
    # --------------------------------------------------------

    return {
        "model": GENERATOR_MODEL,
        "answer": parsed["answer"],
        "citations": parsed["citations"],
        "parse_success": parsed["parse_success"],
        "latency_ms": round(latency_ms, 2),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "raw_response": raw_text,
    }


# ============================================================
# Manual Test
# ============================================================


# if __name__ == "__main__":
#     test_question = "项目后端使用了什么技术？"

#     test_contexts = [
#         {
#             "source": "backend/API手册.md",
#             "heading_path": "后端技术",
#             "content": "项目后端基于 Spring Boot 构建，负责向前端提供数据接口。",
#         },
#         {
#             "source": "frontend/前端设计.md",
#             "heading_path": "前端技术",
#             "content": "前端使用 Vue 和 ECharts 实现数据可视化。",
#         },
#     ]

#     result = generate_answer(
#         question=test_question,
#         contexts=test_contexts,
#     )

#     print(json.dumps(result, ensure_ascii=False, indent=2))


# 测试无证据情况是否能正确返回 "根据现有资料无法确定。"
if __name__ == "__main__":
    test_question = "这个项目使用了哪种推荐算法？"
    test_contexts = []

    result = generate_answer(
        question=test_question,
        contexts=test_contexts,
    )

    print(json.dumps(result, ensure_ascii=False, indent=2))