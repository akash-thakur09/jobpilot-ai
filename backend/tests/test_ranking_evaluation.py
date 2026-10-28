import pytest
from httpx import AsyncClient, ASGITransport

from backend.app.main import create_app
from backend.app.evaluation.runner import OfflineRankingEvaluator
from backend.app.evaluation.fixtures import EVALUATION_DATASET_VERSION, EVALUATION_DATASET_SIZE


def test_offline_evaluator_runner_direct():
    summary = OfflineRankingEvaluator.run_evaluation()

    assert summary["evaluation_dataset_version"] == EVALUATION_DATASET_VERSION
    assert summary["dataset_size"] == EVALUATION_DATASET_SIZE
    assert summary["scoring_policy_version"] == "1.1.0"

    metrics = summary["metrics"]
    ranking = metrics["ranking"]
    assert 0.0 <= ranking["precision_at_3"] <= 1.0
    assert 0.0 <= ranking["ndcg_at_3"] <= 1.0
    assert 0.0 <= ranking["precision_at_5"] <= 1.0
    assert 0.0 <= ranking["ndcg_at_5"] <= 1.0

    dup = metrics["duplicate_detection"]
    assert dup["precision"] >= 0.80
    assert dup["recall"] >= 0.80
    assert dup["f1"] >= 0.80

    assert metrics["freshness_accuracy"] == 1.0

    # Ensure disqualified jobs are ranked at the bottom
    ranked = summary["ranked_results"]
    disqualified_positions = [i for i, r in enumerate(ranked) if not r["is_eligible"]]
    assert all(pos >= 3 for pos in disqualified_positions), "Disqualified jobs must not appear in top 3"


@pytest.mark.asyncio
async def test_ranking_evaluation_api_endpoint():
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/v1/matching/evaluate-ranking")
        assert response.status_code == 200
        data = response.json()
        assert data["evaluation_dataset_version"] == "1.1.0"
        assert "metrics" in data
        assert "ranking" in data["metrics"]
        assert "duplicate_detection" in data["metrics"]
        assert len(data["ranked_results"]) == EVALUATION_DATASET_SIZE
