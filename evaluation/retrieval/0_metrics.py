# evaluation/metrics.py
# 评估检索结果的指标，包括hit@k, recall@k, rr@k

def hit_at_k(matched_ids_by_rank, k):
    """
    Top-K 中，只要命中过至少一条 Gold Evidence，就记为 1。
    否则为 0。
    """

    top_k = matched_ids_by_rank[:k]

    for matched_ids in top_k:
        if matched_ids:
            return 1

    return 0


def recall_at_k(matched_ids_by_rank, gold_evidence_ids, k):
    """
    Top-K 一共找回了多少条 Gold Evidence。

    Recall@K =
        找回的 Gold Evidence 数量
        /
        Gold Evidence 总数量
    """

    found = set()

    for matched_ids in matched_ids_by_rank[:k]:
        for evidence_id in matched_ids:
            found.add(evidence_id)

    gold_ids = set(gold_evidence_ids)

    if not gold_ids:
        return 0.0

    return len(found & gold_ids) / len(gold_ids)


def reciprocal_rank(matched_ids_by_rank, k=5):
    """
    看第一条正确证据排在第几名。

    Rank 1 -> 1
    Rank 2 -> 1/2
    Rank 3 -> 1/3

    Top-K 都没有命中 -> 0
    """

    for rank, matched_ids in enumerate(
        matched_ids_by_rank[:k],
        start=1,
    ):
        if matched_ids:
            return 1 / rank

    return 0.0


def evaluate_question(
    matched_ids_by_rank,
    gold_evidence_ids,
):
    """
    汇总一道题的全部 Retrieval Metrics。
    """

    return {
        "hit_at_1": hit_at_k(matched_ids_by_rank, 1),
        "hit_at_3": hit_at_k(matched_ids_by_rank, 3),
        "hit_at_5": hit_at_k(matched_ids_by_rank, 5),

        "recall_at_1": recall_at_k(
            matched_ids_by_rank,
            gold_evidence_ids,
            1,
        ),
        "recall_at_3": recall_at_k(
            matched_ids_by_rank,
            gold_evidence_ids,
            3,
        ),
        "recall_at_5": recall_at_k(
            matched_ids_by_rank,
            gold_evidence_ids,
            5,
        ),

        "rr_at_5": reciprocal_rank(
            matched_ids_by_rank,
            5,
        ),
    }

# 示例：
if __name__ == "__main__":
    # 假设一道题有两条 Gold Evidence
    gold_evidence_ids = [
        "q005_e01",
        "q005_e02",
    ]

    # BM25 Top5：
    #
    # Top1 什么都没找到
    # Top2 找到 e01
    # Top3 没找到
    # Top4 找到 e02
    # Top5 没找到
    matched_ids_by_rank = [
        [],
        ["q005_e01"],
        [],
        ["q005_e02"],
        [],
    ]

    result = evaluate_question(
        matched_ids_by_rank,
        gold_evidence_ids,
    )

    for name, value in result.items():
        print(f"{name}: {value}")