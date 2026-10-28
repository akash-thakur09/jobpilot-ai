import React, { useEffect, useState } from 'react';
import { JobDuplicateCluster } from '../../types';
import { api } from '../../lib/api-client';
import { Modal } from '../../components/ui/Modal';
import { Badge } from '../../components/ui/Badge';
import { Button } from '../../components/ui/Button';
import { CheckCircle2, XCircle, ExternalLink, RefreshCw } from 'lucide-react';

interface DuplicateClustersModalProps {
  isOpen: boolean;
  onClose: () => void;
  onRefreshJobs?: () => void;
}

export const DuplicateClustersModal: React.FC<DuplicateClustersModalProps> = ({
  isOpen,
  onClose,
  onRefreshJobs,
}) => {
  const [clusters, setClusters] = useState<JobDuplicateCluster[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [actionInProgress, setActionInProgress] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fetchClusters = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await api.jobs.listDuplicates();
      setClusters(data || []);
    } catch (err: any) {
      setError(err?.message || 'Failed to load duplicate clusters');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      fetchClusters();
    }
  }, [isOpen]);

  const handleReview = async (clusterId: string, action: 'CONFIRM' | 'DISMISS') => {
    setActionInProgress(clusterId);
    try {
      await api.jobs.reviewDuplicate(clusterId, action);
      await fetchClusters();
      if (onRefreshJobs) onRefreshJobs();
    } catch (err: any) {
      setError(err?.message || `Failed to ${action.toLowerCase()} cluster`);
    } finally {
      setActionInProgress(null);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Cross-Source Duplicate Clusters"
      size="xl"
      footer={
        <div className="flex justify-between items-center w-full">
          <Button variant="ghost" size="sm" onClick={fetchClusters} icon={<RefreshCw className="w-3.5 h-3.5" />}>
            Refresh Clusters
          </Button>
          <Button variant="outline" size="sm" onClick={onClose}>
            Close
          </Button>
        </div>
      }
    >
      <div className="space-y-4">
        <p className="text-xs text-slate-400">
          Identifies identical or likely identical job vacancies across different supported job boards.
          Reviewing or dismissing duplicate relationships retains all individual listings and will never mutate applications or resume approvals.
        </p>

        {error && (
          <div className="p-3 bg-red-950/40 border border-red-800 rounded-lg text-xs text-red-200">
            {error}
          </div>
        )}

        {isLoading ? (
          <div className="p-8 text-center text-xs text-slate-500">Loading duplicate clusters...</div>
        ) : clusters.length === 0 ? (
          <div className="p-8 text-center text-xs text-slate-500 bg-slate-900/40 rounded-xl border border-slate-800">
            No cross-source duplicate clusters detected yet.
          </div>
        ) : (
          <div className="space-y-3 max-h-[60vh] overflow-y-auto">
            {clusters.map((cluster) => {
              const isWorking = actionInProgress === cluster.id;
              const isConfirmed = cluster.cluster_status === 'CONFIRMED';
              const isDismissed = cluster.cluster_status === 'DISMISSED';

              return (
                <div
                  key={cluster.id}
                  className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 space-y-3"
                >
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-semibold text-slate-200">
                          Cluster ({cluster.confidence.replace('_', ' ')})
                        </span>
                        <Badge
                          variant={
                            isConfirmed
                              ? 'success'
                              : isDismissed
                              ? 'default'
                              : cluster.confidence === 'HIGH_CONFIDENCE'
                              ? 'purple'
                              : 'warning'
                          }
                          size="sm"
                        >
                          {cluster.cluster_status}
                        </Badge>
                        <span className="text-[11px] font-mono text-slate-400">
                          Score: {Math.round(cluster.confidence_score * 100)}%
                        </span>
                      </div>
                      <div className="text-[11px] text-slate-400 mt-1">
                        Reasons: {cluster.match_reasons.join(' • ')}
                      </div>
                    </div>

                    <div className="flex items-center gap-2 shrink-0">
                      {!isConfirmed && (
                        <Button
                          variant="secondary"
                          size="sm"
                          isLoading={isWorking}
                          onClick={() => handleReview(cluster.id, 'CONFIRM')}
                          icon={<CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />}
                        >
                          Confirm
                        </Button>
                      )}
                      {!isDismissed && (
                        <Button
                          variant="ghost"
                          size="sm"
                          isLoading={isWorking}
                          onClick={() => handleReview(cluster.id, 'DISMISS')}
                          icon={<XCircle className="w-3.5 h-3.5 text-slate-400" />}
                        >
                          Dismiss
                        </Button>
                      )}
                    </div>
                  </div>

                  {/* Listings inside cluster */}
                  <div className="space-y-2 pt-2 border-t border-slate-800/80">
                    <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                      Associated Listings ({cluster.jobs?.length || 0})
                    </div>
                    {(cluster.jobs || []).map((j) => (
                      <div
                        key={j.id}
                        className="p-2.5 rounded-lg bg-slate-950/60 border border-slate-800/70 flex items-center justify-between text-xs"
                      >
                        <div className="space-y-0.5">
                          <div className="font-medium text-slate-200 flex items-center gap-2">
                            <span>{j.title}</span>
                            {cluster.canonical_job_id === j.id && (
                              <span className="text-[10px] px-1.5 py-0.2 rounded bg-blue-950 text-blue-300 border border-blue-800">
                                Canonical
                              </span>
                            )}
                          </div>
                          <div className="text-slate-400 text-[11px]">
                            {j.company} • {j.location || 'Remote'} • Source: <span className="font-mono text-slate-300">{j.source_id}</span>
                          </div>
                        </div>
                        {j.canonical_url && (
                          <a
                            href={j.canonical_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-blue-400 hover:text-blue-300 inline-flex items-center gap-1 text-[11px]"
                          >
                            <ExternalLink className="w-3 h-3" />
                            Open
                          </a>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </Modal>
  );
};
