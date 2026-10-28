#!/usr/bin/env python3
"""
CLI runner for JobPilot AI offline ranking evaluation.
Usage:
    python backend/evaluation/run_ranking_eval.py
"""

import sys
import os
import json

# Ensure backend package is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from backend.app.evaluation.runner import OfflineRankingEvaluator


def main():
    print("=" * 60)
    print(" JobPilot AI - Offline Ranking & Intelligence Evaluation")
    print("=" * 60)
    
    summary = OfflineRankingEvaluator.run_evaluation()
    
    metrics = summary["metrics"]
    ranking = metrics["ranking"]
    dup = metrics["duplicate_detection"]
    
    print(f"Dataset Version       : {summary['evaluation_dataset_version']}")
    print(f"Scoring Policy Version: {summary['scoring_policy_version']}")
    print(f"Dataset Size          : {summary['dataset_size']} items")
    print(f"Evaluated At          : {summary['evaluated_at']}")
    print("-" * 60)
    print("Ranking Metrics:")
    print(f"  Precision@3 : {ranking['precision_at_3']:.4f}")
    print(f"  Precision@5 : {ranking['precision_at_5']:.4f}")
    print(f"  Recall@3    : {ranking['recall_at_3']:.4f}")
    print(f"  Recall@5    : {ranking['recall_at_5']:.4f}")
    print(f"  NDCG@3      : {ranking['ndcg_at_3']:.4f}")
    print(f"  NDCG@5      : {ranking['ndcg_at_5']:.4f}")
    print("-" * 60)
    print("Duplicate Detection Metrics:")
    print(f"  Precision   : {dup['precision']:.4f}")
    print(f"  Recall      : {dup['recall']:.4f}")
    print(f"  F1 Score    : {dup['f1']:.4f}")
    print(f"  TP Count    : {dup['true_positives']} / {dup['ground_truth_count']}")
    print("-" * 60)
    print(f"Freshness Accuracy: {metrics['freshness_accuracy']:.4f}")
    print("=" * 60)
    
    # Save machine-readable output to storage/evaluation_results.json
    out_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "storage"))
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "evaluation_results.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"Results written to: {out_path}")


if __name__ == "__main__":
    main()
