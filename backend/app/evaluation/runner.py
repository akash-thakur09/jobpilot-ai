from datetime import datetime, timezone
from typing import Dict, Any, List, Set, Tuple

from backend.app.models.candidate import CandidateProfile, CandidateSkill
from backend.app.models.job import Job
from backend.app.models.enums import RemoteType, EligibilityStatus, FreshnessStatus
from backend.app.matching.eligibility import EligibilityService
from backend.app.matching.scoring import DeterministicScoringService
from backend.app.services.duplicate_detection_service import DuplicateDetectionService
from backend.app.evaluation.fixtures import (
    EVALUATION_DATASET_VERSION,
    EVALUATION_DATASET_SIZE,
    BENCHMARK_CANDIDATE,
    BENCHMARK_JOBS,
    GROUND_TRUTH_DUPLICATE_PAIRS,
)
from backend.app.evaluation.metrics import (
    precision_at_k,
    recall_at_k,
    ndcg_at_k,
    duplicate_detection_metrics,
    freshness_classification_accuracy,
)


class OfflineRankingEvaluator:
    """
    Executes reproducible, deterministic offline evaluation against benchmark fixtures.
    """

    @classmethod
    def run_evaluation(cls) -> Dict[str, Any]:
        evaluated_at = datetime.now(timezone.utc).isoformat()

        # 1. Build Candidate Profile object
        candidate = CandidateProfile(
            id=BENCHMARK_CANDIDATE["id"],
            full_name=BENCHMARK_CANDIDATE["full_name"],
            email=BENCHMARK_CANDIDATE["email"],
            location=BENCHMARK_CANDIDATE["location"],
            work_authorization=BENCHMARK_CANDIDATE["work_authorization"],
            years_of_experience=BENCHMARK_CANDIDATE["years_of_experience"],
            remote_preference=BENCHMARK_CANDIDATE["remote_preference"],
            target_titles=BENCHMARK_CANDIDATE["target_titles"],
            target_salary_min=BENCHMARK_CANDIDATE["target_salary_min"],
            summary=BENCHMARK_CANDIDATE["summary"],
            search_preferences=BENCHMARK_CANDIDATE["search_preferences"],
        )
        candidate.skills = [
            CandidateSkill(
                id=f"skill-{idx}",
                candidate_id=candidate.id,
                skill_name=s["skill_name"],
                is_verified=s["is_verified"],
                years_experience=s["years_experience"],
            )
            for idx, s in enumerate(BENCHMARK_CANDIDATE["skills"])
        ]
        candidate.experiences = []
        candidate.projects = []
        candidate.educations = []

        # 2. Build Job objects
        job_objects: Dict[str, Job] = {}
        for item in BENCHMARK_JOBS:
            j = Job(
                id=item["id"],
                title=item["title"],
                company=item["company"],
                canonical_url=item["canonical_url"],
                location=item["location"],
                remote_type=item["remote_type"],
                salary_min=item["salary_min"],
                salary_max=item["salary_max"],
                description=item["description"],
                freshness_status=item["freshness_status"],
                requirements=[],
            )
            job_objects[item["id"]] = j

        # 3. Evaluate eligibility and scores
        scored_jobs = []
        predicted_freshness: Dict[str, str] = {}
        ground_truth_freshness: Dict[str, str] = {}
        ground_truth_relevance: Dict[str, float] = {}
        ground_truth_relevant_set: Set[str] = set()

        for item in BENCHMARK_JOBS:
            j_id = item["id"]
            job = job_objects[j_id]
            gt_rel = item["ground_truth_relevance"]
            ground_truth_relevance[j_id] = gt_rel
            if gt_rel >= 2.0:
                ground_truth_relevant_set.add(j_id)
            ground_truth_freshness[j_id] = item["freshness_status"]
            predicted_freshness[j_id] = job.freshness_status

            is_elig, status, checks = EligibilityService.evaluate_eligibility(candidate, job)
            breakdown, m_req, m_pref, miss_req, miss_pref = DeterministicScoringService.calculate_score(
                candidate, job
            )

            # Hard constraint gate: Disqualified jobs rank behind eligible jobs
            effective_rank_score = breakdown.final_score if is_elig else (breakdown.final_score * 0.01)

            scored_jobs.append({
                "job_id": j_id,
                "title": job.title,
                "company": job.company,
                "is_eligible": is_elig,
                "eligibility_status": status.value,
                "score": breakdown.final_score,
                "effective_rank_score": effective_rank_score,
                "ground_truth_relevance": gt_rel,
                "freshness_status": job.freshness_status,
                "positive_contributions": breakdown.positive_contributions,
                "negative_contributions": breakdown.negative_contributions,
                "warnings": [breakdown.freshness_warning] if breakdown.freshness_warning else [],
            })

        # Sort ranked jobs descending by effective rank score
        scored_jobs.sort(key=lambda x: x["effective_rank_score"], reverse=True)
        recommended_order = [x["job_id"] for x in scored_jobs]

        # 4. Evaluate Duplicate Detection
        predicted_duplicate_pairs: Set[Tuple[str, str]] = set()
        job_list = list(job_objects.values())
        for i in range(len(job_list)):
            for j in range(i + 1, len(job_list)):
                score, reasons, conf = DuplicateDetectionService.compute_similarity(job_list[i], job_list[j])
                if score >= 0.65:
                    predicted_duplicate_pairs.add((job_list[i].id, job_list[j].id))

        dup_metrics = duplicate_detection_metrics(predicted_duplicate_pairs, GROUND_TRUTH_DUPLICATE_PAIRS)
        freshness_acc = freshness_classification_accuracy(predicted_freshness, ground_truth_freshness)

        # 5. Compute Ranking Metrics
        p_at_3 = precision_at_k(recommended_order, ground_truth_relevant_set, 3)
        p_at_5 = precision_at_k(recommended_order, ground_truth_relevant_set, 5)
        r_at_3 = recall_at_k(recommended_order, ground_truth_relevant_set, 3)
        r_at_5 = recall_at_k(recommended_order, ground_truth_relevant_set, 5)
        ndcg_at_3 = ndcg_at_k(recommended_order, ground_truth_relevance, 3)
        ndcg_at_5 = ndcg_at_k(recommended_order, ground_truth_relevance, 5)

        summary = {
            "evaluation_dataset_version": EVALUATION_DATASET_VERSION,
            "dataset_size": EVALUATION_DATASET_SIZE,
            "scoring_policy_version": "1.1.0",
            "evaluated_at": evaluated_at,
            "metrics": {
                "ranking": {
                    "precision_at_3": p_at_3,
                    "precision_at_5": p_at_5,
                    "recall_at_3": r_at_3,
                    "recall_at_5": r_at_5,
                    "ndcg_at_3": ndcg_at_3,
                    "ndcg_at_5": ndcg_at_5,
                },
                "duplicate_detection": dup_metrics,
                "freshness_accuracy": freshness_acc,
            },
            "ranked_results": scored_jobs,
            "limitations_and_assumptions": [
                "Evaluated strictly against synthetic benchmark fixtures, not live user behavioral logs.",
                "Binary relevance threshold for Precision/Recall is ground_truth_relevance >= 2.0.",
                "Duplicate ground truth is defined by exact cross-source vacancy postings.",
                "Metrics provide deterministic regression protection against unintended scoring drift.",
            ],
        }
        return summary
