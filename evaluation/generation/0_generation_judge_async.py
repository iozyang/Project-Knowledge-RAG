import json
import os
import re

from dotenv import load_dotenv
from openai import AsyncOpenAI


load_dotenv()


# ============================================================
# 配置
# ============================================================

API_KEY = os.getenv("DASHSCOPE_API_KEY")

BASE_URL = os.getenv(
    "DASHSCOPE_BASE_URL",
    "https://dashscope.aliyuncs.com/compatible-mode/v1",
)

CLAIM_SPLITTER_MODEL = os.getenv(
    "CLAIM_SPLITTER_MODEL",
    "qwen3.8-flash",
)

JUDGE_MODEL = os.getenv(
    "JUDGE_MODEL",
    "qwen3.8-max-0902",
)

if not API_KEY:
    raise RuntimeError("未找到 DASHSCOPE_API_KEY")

client = AsyncOpenAI(
    api_key=API_KEY,
    base_url=BASE_URL,
)


# ============================================================
# Claim Splitter Prompt
# ============================================================

CLAIM_SYSTEM_PROMPT = """
你负责把 Generated Answer 拆分为 Atomic Claims（原子主张）。

你会同时得到 Question 和 Generated Answer。

规则：

1. 每个 Claim 必须是可以独立判断真假的完整事实单元。
2. 不得加入回答中没有表达的信息。
3. 可以利用 Question 补全回答省略的主语、对象或语境，
   使 Claim 成为可以独立判断的完整命题。
4. 这种补全只能恢复 Question 已明确提供的语义，不得增加新事实。

例如：

Question:
“离线分析结果先在哪里形成？”

Generated Answer:
“HDFS [S1]”

可以还原为：
“离线分析结果先形成于 HDFS。”

不能只输出“HDFS”。

5. 如果回答包含多个可独立判断的事实，应合理拆分。
6. 数值、条件、范围、否定和因果关系不能丢失。
7. 保留 Claim 在原回答中直接关联的 Citation。
8. Citation 本身不是 Claim 内容。
9. 只有回答表示无法根据资料确定时，才返回空 claims。
10. 其他非空回答至少产生一个 Claim。

只输出合法 JSON：

{
  "claims": [
    {
      "claim_id": "C1",
      "claim": "...",
      "citations": ["S1"]
    }
  ]
}
""".strip()


# ============================================================
# Answer Correctness Prompt
# ============================================================

CORRECTNESS_SYSTEM_PROMPT = """
你负责根据冻结的 Gold Answer Points 评估 Generated Answer 的答案正确性。

你会得到：

- Question
- Gold Answer Points
- Generated Answer

请逐个判断 Gold Answer Point 是否被 Generated Answer 支持。

标签：

SUPPORTED
= Generated Answer 明确、正确地表达了该评分点的核心事实。

PARTIAL
= Generated Answer 表达了评分点的一部分，但遗漏了影响答案完整性的关键信息。

NOT_SUPPORTED
= Generated Answer 没有表达该评分点，或表达错误。

规则：

1. 评价的是“是否回答了 Question 所要求的信息”，不是文字是否与 Gold 完全一致。
2. 不要求逐字复述 Gold Answer。
3. Question 已经明确限定来源时，不要求回答重复“某文档称”“某报告称”等来源描述。
4. 只有以下情况，来源身份本身才属于必要内容：
   - Question 明确询问来源；
   - Question 要求比较不同来源；
   - 不同来源之间存在冲突；
   - 来源身份会改变事实含义。
5. 不因表达简短、措辞不同而扣分。
6. 数值、条件、范围、否定、时间、因果关系和关键技术关系不能错误。
7. 文件路径、类名、框架名等细节，只有 Question 明确要求或缺失会改变答案含义时才是必要信息。
8. 不得使用外部知识补全 Generated Answer。
9. 只根据 Generated Answer 实际表达的内容评分。

每个 Gold Answer Point：

SUPPORTED = 1
PARTIAL = 0.5
NOT_SUPPORTED = 0

最终 score 为所有 Gold Answer Points 得分平均值。

整体 label：

CORRECT
= score == 1

PARTIAL
= 0 < score < 1

WRONG
= score == 0

只输出合法 JSON：

{
  "score": 0.0,
  "label": "CORRECT | PARTIAL | WRONG",
  "results": [
    {
      "fact_id": "F1",
      "label": "SUPPORTED | PARTIAL | NOT_SUPPORTED",
      "reason": "..."
    }
  ]
}
""".strip()


# ============================================================
# Evidence Judge Prompt
# ============================================================

EVIDENCE_SYSTEM_PROMPT = """
你负责统一评估 Generated Claims 的证据支持情况和 Citation 是否有效。

你会得到：

- Atomic Claims
- Context，编号为 S1、S2、S3...

对每个 Claim 同时判断：

1. context_support
2. supporting_sources
3. citation_support

context_support：

SUPPORTED
= Context 明确支持完整 Claim。

CONTRADICTED
= Context 明确与 Claim 冲突。

INSUFFICIENT
= Context 没有足够信息支持完整 Claim。

严格遵守 Evidence Boundary：

1. 必须支持完整的 subject-action-object 关系。
2. 仅出现相同实体、关键词、文件名或概念，不等于支持完整 Claim。
3. 如果 Context 没有明确证明某个责任、关系、状态、归属、时间、因果或实现位置，应判 INSUFFICIENT。
4. 不得使用架构常识、编程常识或外部知识补全证据关系。
5. 多个 Context 可以联合支持一个 Claim。

citation_support：

VALID
= Claim 提供的 Citation 中至少有一项能够支持完整 Claim。

UNSUPPORTED
= Claim 提供了 Citation，但这些 Citation 不能支持完整 Claim。

MISSING
= Claim 没有 Citation。

INVALID_ID
= Citation 引用了 Context 中不存在的编号。

逻辑约束：

如果 citation_support == VALID，
则 context_support 必须 == SUPPORTED。

只输出合法 JSON：

{
  "results": [
    {
      "claim_id": "C1",
      "context_support": "SUPPORTED | CONTRADICTED | INSUFFICIENT",
      "supporting_sources": ["S1"],
      "citation_support": "VALID | UNSUPPORTED | MISSING | INVALID_ID",
      "reason": "..."
    }
  ]
}
""".strip()


# ============================================================
# 基础工具
# ============================================================

def is_abstention(answer):
    text = re.sub(r"\s+", "", answer or "")
    text = text.strip("。！？!?，,；; ")

    core = "根据现有资料无法确定"

    if text == core:
        return True

    if text in {
        f"抱歉{core}",
        f"很抱歉{core}",
    }:
        return True

    return False


def extract_inline_citations(answer):
    return list(
        dict.fromkeys(
            re.findall(
                r"\[(S[1-9]\d*)\]",
                answer or "",
            )
        )
    )


def build_context_text(contexts):
    blocks = []

    for index, context in enumerate(contexts, start=1):
        source_id = f"S{index}"

        source = context.get(
            "source",
            "unknown",
        )

        heading = context.get(
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

        if heading:
            block.append(
                f"Heading: {heading}"
            )

        block.append(
            f"Content:\n{content}"
        )

        blocks.append(
            "\n".join(block)
        )

    return "\n\n".join(blocks)


def parse_json_response(raw_text):
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

    return json.loads(text)


def merge_usage(first, second):
    if not first and not second:
        return None

    result = {
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
    }

    for usage in [first, second]:
        if not usage:
            continue

        for key in result:
            result[key] += (
                usage.get(key, 0)
                or 0
            )

    return result


# ============================================================
# 异步模型调用
# ============================================================

async def request_model(
    model,
    system_prompt,
    user_prompt,
):
    response = await client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": user_prompt,
            },
        ],
        temperature=0,
        max_tokens=2000,
        extra_body={
            "enable_thinking": False,
        },
    )

    raw_text = (
        response.choices[0].message.content
        or ""
    )

    usage_obj = getattr(
        response,
        "usage",
        None,
    )

    usage = None

    if usage_obj:
        usage = {
            "input_tokens": getattr(
                usage_obj,
                "prompt_tokens",
                0,
            )
            or 0,

            "output_tokens": getattr(
                usage_obj,
                "completion_tokens",
                0,
            )
            or 0,

            "total_tokens": getattr(
                usage_obj,
                "total_tokens",
                0,
            )
            or 0,
        }

    return {
        "raw_text": raw_text,
        "usage": usage,
    }


async def call_model(
    model,
    system_prompt,
    user_prompt,
):
    first = await request_model(
        model,
        system_prompt,
        user_prompt,
    )

    try:
        data = parse_json_response(
            first["raw_text"]
        )

        data["_usage"] = first["usage"]

        return data

    except json.JSONDecodeError:
        retry_prompt = f"""
{user_prompt}

上一次输出不是合法 JSON。

请重新输出。

要求：
1. 只输出合法 JSON。
2. 不要使用 Markdown 代码块。
3. 正确转义字符串中的双引号和反斜杠。
4. 不要添加任何 JSON 之外的解释。
""".strip()

        second = await request_model(
            model,
            system_prompt,
            retry_prompt,
        )

        data = parse_json_response(
            second["raw_text"]
        )

        data["_usage"] = merge_usage(
            first["usage"],
            second["usage"],
        )

        return data


# ============================================================
# Claim Splitter
# ============================================================

def normalize_claim_citations(
    claims,
    answer,
):
    inline_citations = (
        extract_inline_citations(answer)
    )

    valid_pattern = re.compile(
        r"^S[1-9]\d*$"
    )

    for claim in claims:
        citations = claim.get(
            "citations",
            [],
        )

        if not isinstance(
            citations,
            list,
        ):
            citations = []

        claim["citations"] = [
            citation
            for citation in citations
            if isinstance(citation, str)
            and valid_pattern.match(citation)
        ]

    if (
        len(inline_citations) == 1
        and claims
        and all(
            not claim["citations"]
            for claim in claims
        )
    ):
        citation = inline_citations[0]

        for claim in claims:
            claim["citations"] = [
                citation
            ]

    return claims


async def extract_atomic_claims(
    question,
    answer,
):
    inline_citations = (
        extract_inline_citations(answer)
    )

    if is_abstention(answer):
        return {
            "claims": [],
            "inline_citations": inline_citations,
            "model": None,
            "usage": None,
        }

    user_prompt = f"""
Question:

{question}

Generated Answer:

{answer}
""".strip()

    result = await call_model(
        CLAIM_SPLITTER_MODEL,
        CLAIM_SYSTEM_PROMPT,
        user_prompt,
    )

    claims = result.get(
        "claims",
        [],
    )

    if not isinstance(claims, list):
        claims = []

    claims = normalize_claim_citations(
        claims,
        answer,
    )

    return {
        "claims": claims,
        "inline_citations": inline_citations,
        "model": CLAIM_SPLITTER_MODEL,
        "usage": result.get("_usage"),
    }


# ============================================================
# Correctness Judge
# ============================================================

async def judge_answer_correctness(
    question,
    gold_points,
    generated_answer,
):
    if not gold_points:
        return {
            "score": None,
            "label": "N/A",
            "results": [],
            "model": None,
            "usage": None,
        }

    gold_text = json.dumps(
        gold_points,
        ensure_ascii=False,
        indent=2,
    )

    user_prompt = f"""
Question:

{question}

Gold Answer Points:

{gold_text}

Generated Answer:

{generated_answer}
""".strip()

    result = await call_model(
        JUDGE_MODEL,
        CORRECTNESS_SYSTEM_PROMPT,
        user_prompt,
    )

    return {
        "score": result.get("score"),
        "label": result.get("label"),
        "results": result.get(
            "results",
            [],
        ),
        "model": JUDGE_MODEL,
        "usage": result.get("_usage"),
    }


# ============================================================
# Evidence Judge
# ============================================================

def find_logic_errors(results):
    errors = []

    for result in results:
        if (
            result.get("citation_support")
            == "VALID"
            and result.get("context_support")
            != "SUPPORTED"
        ):
            errors.append(
                result.get("claim_id")
            )

    return errors


async def retry_evidence_logic(
    claims,
    contexts,
    previous_results,
    logic_errors,
):
    context_text = build_context_text(
        contexts
    )

    claim_text = json.dumps(
        claims,
        ensure_ascii=False,
        indent=2,
    )

    previous_text = json.dumps(
        previous_results,
        ensure_ascii=False,
        indent=2,
    )

    user_prompt = f"""
Atomic Claims:

{claim_text}

Context:

{context_text}

你上一次的判断存在逻辑冲突。

冲突 Claim：

{json.dumps(logic_errors, ensure_ascii=False)}

上一次结果：

{previous_text}

请重新检查这些 Claim。

必须满足：

citation_support == VALID
只能出现在
context_support == SUPPORTED
时。

重新输出全部 results。
""".strip()

    return await call_model(
        JUDGE_MODEL,
        EVIDENCE_SYSTEM_PROMPT,
        user_prompt,
    )


async def judge_evidence(
    claims,
    contexts,
):
    if not claims:
        return {
            "faithfulness": None,
            "unsupported_claim_rate": None,
            "citation_accuracy": None,
            "citation_coverage": None,
            "logic_error_count": 0,
            "logic_error_claims": [],
            "results": [],
            "model": None,
            "usage": None,
        }

    context_text = build_context_text(
        contexts
    )

    claim_text = json.dumps(
        claims,
        ensure_ascii=False,
        indent=2,
    )

    user_prompt = f"""
Atomic Claims:

{claim_text}

Context:

{context_text}
""".strip()

    result = await call_model(
        JUDGE_MODEL,
        EVIDENCE_SYSTEM_PROMPT,
        user_prompt,
    )

    results = result.get(
        "results",
        [],
    )

    usage = result.get(
        "_usage"
    )

    logic_errors = find_logic_errors(
        results
    )

    if logic_errors:
        retry = await retry_evidence_logic(
            claims,
            contexts,
            results,
            logic_errors,
        )

        results = retry.get(
            "results",
            [],
        )

        usage = merge_usage(
            usage,
            retry.get("_usage"),
        )

        logic_errors = (
            find_logic_errors(
                results
            )
        )

    logic_error_set = set(
        logic_errors
    )

    for item in results:
        if (
            item.get("claim_id")
            in logic_error_set
        ):
            item["context_support"] = (
                "LOGIC_ERROR"
            )

            item["citation_support"] = (
                "LOGIC_ERROR"
            )

    evaluated_results = [
        item
        for item in results
        if item.get("context_support")
        != "LOGIC_ERROR"
    ]

    evaluated_count = len(
        evaluated_results
    )

    supported_count = sum(
        item.get("context_support")
        == "SUPPORTED"
        for item in evaluated_results
    )

    if evaluated_count:
        faithfulness = (
            supported_count
            / evaluated_count
        )

        unsupported_rate = (
            1 - faithfulness
        )

    else:
        faithfulness = None
        unsupported_rate = None

    citation_attempts = 0
    valid_citations = 0

    claim_map = {
        claim.get("claim_id"): claim
        for claim in claims
    }

    cited_claims = 0

    for item in evaluated_results:
        claim_id = item.get(
            "claim_id"
        )

        claim = claim_map.get(
            claim_id,
            {},
        )

        citations = claim.get(
            "citations",
            [],
        )

        if citations:
            cited_claims += 1
            citation_attempts += 1

            if (
                item.get("citation_support")
                == "VALID"
            ):
                valid_citations += 1

    citation_accuracy = None

    if citation_attempts:
        citation_accuracy = (
            valid_citations
            / citation_attempts
        )

    citation_coverage = None

    if evaluated_count:
        citation_coverage = (
            cited_claims
            / evaluated_count
        )

    return {
        "faithfulness": faithfulness,
        "unsupported_claim_rate": unsupported_rate,
        "citation_accuracy": citation_accuracy,
        "citation_coverage": citation_coverage,
        "logic_error_count": len(
            logic_errors
        ),
        "logic_error_claims": logic_errors,
        "results": results,
        "model": JUDGE_MODEL,
        "usage": usage,
    }