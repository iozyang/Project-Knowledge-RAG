"""Validate the frozen P1-10MD-v1 QA/evidence benchmark (stdlib only)."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BENCHMARK = Path(__file__).resolve().parent / "benchmark_v1.jsonl"
CORPUS = ROOT / "corpus" / "dalian-neusoft-movie-analysis"
MANIFEST = CORPUS / "manifest.json"

QUESTION_TYPES = {
    "factual", "parameter", "module_responsibility", "data_flow",
    "architecture_reasoning", "implementation_detail", "cross_document",
    "unanswerable",
}
DIFFICULTIES = {"easy", "medium", "hard"}
HOPS = {"single", "multi", "none"}
REQUIRED = {
    "id", "question", "question_type", "difficulty", "answerable",
    "hop_type", "gold_answer", "gold_documents", "gold_evidence", "tags", "notes",
}


def headings_by_line(content: str) -> list[str]:
    """Return the real Markdown heading active on each 1-based source line."""
    result = [""]
    active = ""
    fence = False
    for line in content.splitlines():
        if re.match(r"^\s*(```|~~~)", line):
            fence = not fence
        if not fence:
            match = re.match(r"^#{1,6}\s+(.+?)\s*$", line)
            if match:
                active = match.group(1).strip()
        result.append(active)
    return result


def validate(pilot: bool = False) -> tuple[list[str], Counter[str]]:
    errors: list[str] = []
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    allowed: dict[str, tuple[Path, str]] = {}
    for entry in manifest["documents"]:
        if not entry.get("include_in_chunking"):
            continue
        name = Path(entry["path"]).name
        path = ROOT / "corpus" / entry["path"]
        if name in allowed:
            errors.append(f"duplicate corpus basename: {name}")
        if not path.is_file():
            errors.append(f"missing corpus file: {path}")
            continue
        actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual_hash != entry["corpus_sha256"]:
            errors.append(f"corpus hash changed: {name}")
        allowed[name] = (path, path.read_text(encoding="utf-8"))
    if len(allowed) != 10:
        errors.append(f"expected 10 corpus documents, found {len(allowed)}")

    records = []
    for number, line in enumerate(BENCHMARK.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            errors.append(f"blank JSONL line {number}")
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as exc:
            errors.append(f"invalid JSONL line {number}: {exc}")
    expected_count = 10 if pilot else 50
    if len(records) != expected_count:
        errors.append(f"expected {expected_count} questions, found {len(records)}")

    ids: set[str] = set()
    evidence_ids: set[str] = set()
    normalized_questions: set[str] = set()
    counts: Counter[str] = Counter()
    for number, item in enumerate(records, 1):
        label = item.get("id", f"line {number}")
        missing = REQUIRED - item.keys()
        if missing:
            errors.append(f"{label}: missing fields {sorted(missing)}")
            continue
        if label != f"q{number:03d}":
            errors.append(f"{label}: id/order mismatch, expected q{number:03d}")
        if label in ids:
            errors.append(f"{label}: duplicate id")
        ids.add(label)
        question = item["question"]
        if not isinstance(question, str) or not question.strip():
            errors.append(f"{label}: empty question")
            question = ""
        normalized = re.sub(r"[\s\W_]+", "", question, flags=re.UNICODE)
        if normalized in normalized_questions:
            errors.append(f"{label}: duplicate normalized question")
        normalized_questions.add(normalized)
        if item["question_type"] not in QUESTION_TYPES:
            errors.append(f"{label}: invalid question_type")
        if item["difficulty"] not in DIFFICULTIES:
            errors.append(f"{label}: invalid difficulty")
        if item["hop_type"] not in HOPS:
            errors.append(f"{label}: invalid hop_type")
        if not isinstance(item["tags"], list) or not all(isinstance(t, str) and t for t in item["tags"]):
            errors.append(f"{label}: invalid tags")
        if not isinstance(item["notes"], str):
            errors.append(f"{label}: invalid notes")
        if not isinstance(item["answerable"], bool):
            errors.append(f"{label}: answerable must be boolean")
            continue
        answerable = item["answerable"]
        docs = item["gold_documents"]
        evs = item["gold_evidence"]
        if not isinstance(docs, list) or not isinstance(evs, list):
            errors.append(f"{label}: gold_documents/evidence must be lists")
            continue
        if answerable:
            if not isinstance(item["gold_answer"], str) or not item["gold_answer"].strip():
                errors.append(f"{label}: missing gold_answer")
            if not docs or not evs:
                errors.append(f"{label}: missing answerable evidence")
            if item["hop_type"] == "none":
                errors.append(f"{label}: answerable question has hop_type none")
            if item["question_type"] == "unanswerable":
                errors.append(f"{label}: answerable question has unanswerable type")
        else:
            if item["gold_answer"] is not None or docs or evs or item["hop_type"] != "none":
                errors.append(f"{label}: invalid unanswerable gold fields")
            if item["question_type"] != "unanswerable":
                errors.append(f"{label}: false answerable must use unanswerable type")
            if not item["notes"].strip():
                errors.append(f"{label}: unanswerable needs a scope note")
        ev_docs: list[str] = []
        for idx, evidence in enumerate(evs, 1):
            if not isinstance(evidence, dict):
                errors.append(f"{label}: evidence {idx} not an object")
                continue
            for key in ("evidence_id", "document", "section", "evidence"):
                if not evidence.get(key):
                    errors.append(f"{label}: evidence {idx} missing {key}")
            evid = evidence.get("evidence_id", "")
            if evid != f"{label}_e{idx:02d}":
                errors.append(f"{label}: noncanonical evidence id {evid}")
            if evid in evidence_ids:
                errors.append(f"{label}: duplicate evidence id {evid}")
            evidence_ids.add(evid)
            doc = evidence.get("document", "")
            ev_docs.append(doc)
            if doc not in allowed:
                errors.append(f"{label}: evidence refers to non-corpus document {doc}")
                continue
            content = allowed[doc][1]
            quote = evidence.get("evidence", "")
            section = evidence.get("section", "")
            if quote not in content:
                errors.append(f"{label}: evidence not verbatim in {doc}: {quote[:60]}")
                continue
            line_index = content[:content.index(quote)].count("\n") + 1
            headings = headings_by_line(content)
            if section != headings[line_index]:
                errors.append(f"{label}: section mismatch in {doc}: {section!r} != {headings[line_index]!r}")
        if sorted(set(docs)) != sorted(set(ev_docs)) or len(docs) != len(set(docs)):
            errors.append(f"{label}: gold_documents differs from evidence documents")
        if item["hop_type"] == "single" and len(evs) != 1:
            errors.append(f"{label}: single-hop requires one evidence")
        if item["hop_type"] == "multi" and len(evs) < 2:
            errors.append(f"{label}: multi-hop requires at least two evidence units")
        if item["question_type"] == "cross_document" and (len(set(docs)) < 2 or item["hop_type"] != "multi"):
            errors.append(f"{label}: cross_document must use two documents and multi-hop")
        counts[f"type:{item['question_type']}"] += 1
        counts[f"difficulty:{item['difficulty']}"] += 1
        counts[f"hop:{item['hop_type']}"] += 1
        for doc in docs:
            counts[f"document:{doc}"] += 1
        for doc in ev_docs:
            counts[f"evidence:{doc}"] += 1
    if not pilot:
        if counts["type:cross_document"] < 7:
            errors.append("fewer than seven cross_document questions")
        if counts["type:unanswerable"] < 5:
            errors.append("fewer than five unanswerable questions")
        for name in allowed:
            if counts[f"document:{name}"] == 0:
                errors.append(f"document absent from gold questions: {name}")
    return errors, counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pilot", action="store_true", help="require 10 instead of 50 questions")
    args = parser.parse_args()
    errors, counts = validate(pilot=args.pilot)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    digest = hashlib.sha256(BENCHMARK.read_bytes()).hexdigest()
    print(f"PASS: {10 if args.pilot else 50} questions; SHA256={digest}")
    print("types:", {key[5:]: value for key, value in counts.items() if key.startswith("type:")})
    print("difficulty:", {key[11:]: value for key, value in counts.items() if key.startswith("difficulty:")})
    print("hops:", {key[4:]: value for key, value in counts.items() if key.startswith("hop:")})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
