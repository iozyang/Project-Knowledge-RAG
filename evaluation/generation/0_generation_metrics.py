import json
import re
import statistics
from pathlib import Path


ABSTAIN_TEXT = "根据现有资料无法确定。"
CITATION_PATTERN = re.compile(r"^S([1-9]\d*)$")
INLINE_CITATION_PATTERN = re.compile(r"\[(S[1-9]\d*)\]")


def load_jsonl(path):
    rows = []

    with Path(path).open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))

    return rows


def is_abstention(answer):
    return answer.strip() == ABSTAIN_TEXT


def extract_inline_citations(answer):
    citations = INLINE_CITATION_PATTERN.findall(answer)
    return list(dict.fromkeys(citations))


def citation_id_valid(citation, context_count):
    match = CITATION_PATTERN.fullmatch(citation)

    if not match:
        return False

    number = int(match.group(1))
    return 1 <= number <= context_count


def evaluate_row(row):
    answer = row.get("answer", "")
    structured_citations = row.get("citations", [])
    context_count = row.get("context_count", 0)

    inline_citations = extract_inline_citations(answer)

    citation_format_valid = all(
        citation_id_valid(citation, context_count)
        for citation in structured_citations
    )

    inline_citation_valid = all(
        citation_id_valid(citation, context_count)
        for citation in inline_citations
    )

    citation_consistent = set(structured_citations) == set(inline_citations)

    abstained = is_abstention(answer)

    return {
        "id": row["id"],
        "answerable": row["answerable"],
        "parse_success": bool(row.get("parse_success")),
        "abstained": abstained,
        "correct_abstention": not row["answerable"] and abstained,
        "false_abstention": row["answerable"] and abstained,
        "citation_format_valid": citation_format_valid,
        "inline_citation_valid": inline_citation_valid,
        "citation_consistent": citation_consistent,
        "inline_citations": inline_citations,
        "structured_citations": structured_citations,
    }


def percentile(values, p):
    if not values:
        return None

    values = sorted(values)

    if len(values) == 1:
        return values[0]

    position = (len(values) - 1) * p
    lower = int(position)
    upper = min(lower + 1, len(values) - 1)

    weight = position - lower

    return values[lower] * (1 - weight) + values[upper] * weight


def safe_rate(numerator, denominator):
    if denominator == 0:
        return None

    return numerator / denominator


def summarize_outputs(rows):
    evaluations = [evaluate_row(row) for row in rows]

    total = len(rows)

    answerable_rows = [row for row in rows if row["answerable"]]
    unanswerable_rows = [row for row in rows if not row["answerable"]]

    parse_success_count = sum(item["parse_success"] for item in evaluations)

    correct_abstention_count = sum(
        item["correct_abstention"]
        for item in evaluations
    )

    false_abstention_count = sum(
        item["false_abstention"]
        for item in evaluations
    )

    citation_format_valid_count = sum(
        item["citation_format_valid"]
        and item["inline_citation_valid"]
        for item in evaluations
    )

    citation_consistency_count = sum(
        item["citation_consistent"]
        for item in evaluations
    )

    input_tokens = [
        row["input_tokens"]
        for row in rows
        if row.get("input_tokens") is not None
    ]

    output_tokens = [
        row["output_tokens"]
        for row in rows
        if row.get("output_tokens") is not None
    ]

    total_tokens = [
        row["total_tokens"]
        for row in rows
        if row.get("total_tokens") is not None
    ]

    latencies = [
        row["latency_ms"]
        for row in rows
        if row.get("latency_ms") is not None
    ]

    return {
        "questions": total,
        "answerable": len(answerable_rows),
        "unanswerable": len(unanswerable_rows),

        "parse_success": {
            "count": parse_success_count,
            "rate": safe_rate(parse_success_count, total),
        },

        "abstention": {
            "correct_unanswerable": correct_abstention_count,
            "unanswerable_rate": safe_rate(
                correct_abstention_count,
                len(unanswerable_rows),
            ),
            "false_abstention": false_abstention_count,
            "false_abstention_rate": safe_rate(
                false_abstention_count,
                len(answerable_rows),
            ),
        },

        "citation_format": {
            "valid_count": citation_format_valid_count,
            "valid_rate": safe_rate(citation_format_valid_count, total),
            "consistent_count": citation_consistency_count,
            "consistent_rate": safe_rate(citation_consistency_count, total),
        },

        "tokens": {
            "total_input_tokens": sum(input_tokens),
            "total_output_tokens": sum(output_tokens),
            "total_tokens": sum(total_tokens),

            "avg_input_tokens": (
                statistics.mean(input_tokens)
                if input_tokens else None
            ),

            "avg_output_tokens": (
                statistics.mean(output_tokens)
                if output_tokens else None
            ),

            "avg_total_tokens": (
                statistics.mean(total_tokens)
                if total_tokens else None
            ),
        },

        "latency": {
            "avg_ms": (
                statistics.mean(latencies)
                if latencies else None
            ),

            "median_ms": (
                statistics.median(latencies)
                if latencies else None
            ),

            "p95_ms": percentile(latencies, 0.95),
        },

        "row_metrics": evaluations,
    }