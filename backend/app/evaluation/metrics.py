import math
from typing import List, Dict, Set, Tuple, Any


def precision_at_k(recommended_ids: List[str], ground_truth_relevant: Set[str], k: int) -> float:
    """
    Precision@K = (# of relevant items in top K) / K.
    """
    if k <= 0 or not recommended_ids:
        return 0.0
    top_k = recommended_ids[:k]
    relevant_in_top_k = sum(1 for item in top_k if item in ground_truth_relevant)
    return round(relevant_in_top_k / k, 4)


def recall_at_k(recommended_ids: List[str], ground_truth_relevant: Set[str], k: int) -> float:
    """
    Recall@K = (# of relevant items in top K) / (total # of relevant items).
    """
    if not ground_truth_relevant or k <= 0 or not recommended_ids:
        return 0.0
    top_k = recommended_ids[:k]
    relevant_in_top_k = sum(1 for item in top_k if item in ground_truth_relevant)
    return round(relevant_in_top_k / len(ground_truth_relevant), 4)


def dcg_at_k(recommended_ids: List[str], relevance_grades: Dict[str, float], k: int) -> float:
    """
    Discounted Cumulative Gain at K.
    DCG@K = sum_{i=1}^K (2^{rel_i} - 1) / log_2(i + 1)
    """
    dcg = 0.0
    for idx, item in enumerate(recommended_ids[:k]):
        rel = relevance_grades.get(item, 0.0)
        # Using standard grading formulation
        dcg += (math.pow(2.0, rel) - 1.0) / math.log2(idx + 2.0)
    return dcg


def ndcg_at_k(recommended_ids: List[str], relevance_grades: Dict[str, float], k: int) -> float:
    """
    Normalized Discounted Cumulative Gain at K.
    NDCG@K = DCG@K / IDCG@K.
    """
    if k <= 0 or not recommended_ids or not relevance_grades:
        return 0.0

    actual_dcg = dcg_at_k(recommended_ids, relevance_grades, k)

    # Ideal DCG: sort all items by relevance descending
    sorted_ideal = sorted(relevance_grades.keys(), key=lambda x: relevance_grades[x], reverse=True)
    ideal_dcg = dcg_at_k(sorted_ideal, relevance_grades, k)

    if ideal_dcg <= 0.0:
        return 0.0

    return round(actual_dcg / ideal_dcg, 4)


def duplicate_detection_metrics(
    predicted_pairs: Set[Tuple[str, str]], ground_truth_pairs: Set[Tuple[str, str]]
) -> Dict[str, float]:
    """
    Precision, Recall, and F1 for duplicate pair identification.
    Pairs are treated as undirected (canonicalized).
    """
    norm_predicted = {tuple(sorted(p)) for p in predicted_pairs if p[0] != p[1]}
    norm_ground_truth = {tuple(sorted(p)) for p in ground_truth_pairs if p[0] != p[1]}

    if not norm_predicted and not norm_ground_truth:
        return {"precision": 1.0, "recall": 1.0, "f1": 1.0}

    true_positives = len(norm_predicted.intersection(norm_ground_truth))
    precision = (true_positives / len(norm_predicted)) if norm_predicted else 0.0
    recall = (true_positives / len(norm_ground_truth)) if norm_ground_truth else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "true_positives": true_positives,
        "predicted_count": len(norm_predicted),
        "ground_truth_count": len(norm_ground_truth),
    }


def freshness_classification_accuracy(
    predicted_statuses: Dict[str, str], ground_truth_statuses: Dict[str, str]
) -> float:
    """
    Classification accuracy for job freshness status.
    """
    if not ground_truth_statuses:
        return 0.0
    correct = sum(
        1
        for j_id, gt_stat in ground_truth_statuses.items()
        if predicted_statuses.get(j_id) == gt_stat
    )
    return round(correct / len(ground_truth_statuses), 4)
