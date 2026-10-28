import React, { useState } from 'react';
import { RankingEvaluationSummary } from '../../types';
import { api } from '../../lib/api-client';
import { Modal } from '../../components/ui/Modal';
import { Badge } from '../../components/ui/Badge';
import { Button } from '../../components/ui/Button';
import { Play, Activity } from 'lucide-react';

interface RankingEvaluationModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const RankingEvaluationModal: React.FC<RankingEvaluationModalProps> = ({
  isOpen,
  onClose,
}) => {
  const [summary, setSummary] = useState<RankingEvaluationSummary | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleRunEvaluation = async () => {
    setIsRunning(true);
    setError(null);
    try {
      const data = await api.matching.evaluateRanking();
      setSummary(data);
    } catch (err: any) {
      setError(err?.message || 'Failed to execute offline evaluation framework');
    } finally {
      setIsRunning(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Offline Ranking Evaluation & Quality Metrics"
      size="xl"
      footer={
        <div className="flex justify-between items-center w-full">
          <Button
            variant="primary"
            size="sm"
            onClick={handleRunEvaluation}
            isLoading={isRunning}
            icon={<Play className="w-3.5 h-3.5" />}
          >
            Run Evaluation Suite
          </Button>
          <Button variant="outline" size="sm" onClick={onClose}>
            Close
          </Button>
        </div>
      }
    >
      <div className="space-y-5">
        <div className="p-3 bg-blue-950/30 border border-blue-900/40 rounded-xl text-xs text-blue-200">
          <div className="font-semibold text-blue-100 flex items-center gap-1.5 mb-1">
            <Activity className="w-4 h-4 text-blue-400" />
            Deterministic Benchmark Suite
          </div>
          Evaluates ranking performance, duplicate detection, and freshness categorization against controlled labeled test fixtures.
          Metrics serve as offline regression baselines and should not be confused with live production clickthrough data.
        </div>

        {error && (
          <div className="p-3 bg-red-950/40 border border-red-800 rounded-lg text-xs text-red-200">
            {error}
          </div>
        )}

        {!summary && !isRunning && (
          <div className="p-10 text-center text-xs text-slate-500 bg-slate-900/40 rounded-xl border border-slate-800">
            Click "Run Evaluation Suite" to run the deterministic evaluation framework.
          </div>
        )}

        {isRunning && (
          <div className="p-10 text-center text-xs text-slate-400">
            Executing deterministic scoring, duplicate clustering, and freshness accuracy checks...
          </div>
        )}

        {summary && (
          <div className="space-y-4">
            <div className="flex flex-wrap items-center gap-2 text-xs text-slate-400">
              <span className="font-semibold text-slate-200">Dataset Version:</span>
              <Badge variant="info" size="sm">{summary.evaluation_dataset_version}</Badge>
              <span className="font-semibold text-slate-200 ml-2">Policy:</span>
              <Badge variant="purple" size="sm">v{summary.scoring_policy_version}</Badge>
              <span className="font-semibold text-slate-200 ml-2">Dataset Size:</span>
              <span className="font-mono text-slate-300">{summary.dataset_size} items</span>
            </div>

            {/* Metrics Grid */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <div className="p-3 rounded-xl bg-slate-900/70 border border-slate-800">
                <div className="text-[11px] text-slate-400">Precision@3</div>
                <div className="text-lg font-bold text-emerald-400">
                  {Math.round(summary.metrics.ranking.precision_at_3 * 100)}%
                </div>
              </div>
              <div className="p-3 rounded-xl bg-slate-900/70 border border-slate-800">
                <div className="text-[11px] text-slate-400">NDCG@3</div>
                <div className="text-lg font-bold text-emerald-400">
                  {summary.metrics.ranking.ndcg_at_3.toFixed(3)}
                </div>
              </div>
              <div className="p-3 rounded-xl bg-slate-900/70 border border-slate-800">
                <div className="text-[11px] text-slate-400">Precision@5</div>
                <div className="text-lg font-bold text-blue-400">
                  {Math.round(summary.metrics.ranking.precision_at_5 * 100)}%
                </div>
              </div>
              <div className="p-3 rounded-xl bg-slate-900/70 border border-slate-800">
                <div className="text-[11px] text-slate-400">NDCG@5</div>
                <div className="text-lg font-bold text-blue-400">
                  {summary.metrics.ranking.ndcg_at_5.toFixed(3)}
                </div>
              </div>
              <div className="p-3 rounded-xl bg-slate-900/70 border border-slate-800">
                <div className="text-[11px] text-slate-400">Duplicate Recall</div>
                <div className="text-lg font-bold text-purple-400">
                  {Math.round(summary.metrics.duplicate_detection.recall * 100)}%
                </div>
              </div>
              <div className="p-3 rounded-xl bg-slate-900/70 border border-slate-800">
                <div className="text-[11px] text-slate-400">Duplicate Precision</div>
                <div className="text-lg font-bold text-purple-400">
                  {Math.round(summary.metrics.duplicate_detection.precision * 100)}%
                </div>
              </div>
              <div className="p-3 rounded-xl bg-slate-900/70 border border-slate-800">
                <div className="text-[11px] text-slate-400">Duplicate F1</div>
                <div className="text-lg font-bold text-purple-400">
                  {summary.metrics.duplicate_detection.f1.toFixed(3)}
                </div>
              </div>
              <div className="p-3 rounded-xl bg-slate-900/70 border border-slate-800">
                <div className="text-[11px] text-slate-400">Freshness Accuracy</div>
                <div className="text-lg font-bold text-emerald-400">
                  {Math.round(summary.metrics.freshness_accuracy * 100)}%
                </div>
              </div>
            </div>

            {/* Ranked Fixtures */}
            <div className="space-y-2 pt-2 border-t border-slate-800">
              <div className="text-xs font-semibold text-slate-300">
                Top Ranked Benchmark Fixtures
              </div>
              <div className="space-y-1.5 max-h-56 overflow-y-auto">
                {summary.ranked_results.slice(0, 8).map((res, i) => (
                  <div
                    key={res.job_id}
                    className="p-2.5 rounded-lg bg-slate-900/50 border border-slate-800 flex items-center justify-between text-xs"
                  >
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-slate-500 w-4 text-center">#{i + 1}</span>
                      <span className="text-slate-200 font-medium">{res.title}</span>
                      <span className="text-slate-400">({res.company})</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge variant={res.is_eligible ? 'success' : 'danger'} size="sm">
                        {res.eligibility_status}
                      </Badge>
                      <span className="font-mono text-blue-400 font-semibold">{res.score} pts</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Limitations Notice */}
            <div className="text-[11px] text-slate-500 space-y-1 pt-2 border-t border-slate-800">
              <div className="font-medium text-slate-400">Assumptions & Limitations:</div>
              {summary.limitations_and_assumptions.map((item, idx) => (
                <div key={idx}>• {item}</div>
              ))}
            </div>
          </div>
        )}
      </div>
    </Modal>
  );
};
