import React, { useEffect, useState } from 'react';
import {
  CalendarClock,
  Play,
  RotateCw,
  CheckCircle2,
  AlertTriangle,
  AlertCircle,
  ChevronRight,
  Info,
  Layers,
} from 'lucide-react';
import { api, ApiError } from '../../lib/api-client';
import { SchedulerStatus, AutomationRunItem } from '../../types';
import { Card } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { LoadingSkeleton } from '../../components/ui/LoadingSkeleton';
import { formatDate } from '../../lib/formatters';
import { DiscoverySourcesCard } from './DiscoverySourcesCard';

export const SchedulerManager: React.FC = () => {
  const [status, setStatus] = useState<SchedulerStatus | null>(null);
  const [runs, setRuns] = useState<AutomationRunItem[]>([]);
  const [totalRuns, setTotalRuns] = useState<number>(0);
  const [intervalInput, setIntervalInput] = useState<number>(240);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isSavingConfig, setIsSavingConfig] = useState<boolean>(false);
  const [isRunningDiscovery, setIsRunningDiscovery] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [selectedRun, setSelectedRun] = useState<AutomationRunItem | null>(null);

  const fetchSchedulerData = async () => {
    try {
      const [statusRes, runsRes] = await Promise.all([
        api.scheduler.getStatus(),
        api.scheduler.listRuns({ limit: 10, offset: 0 }),
      ]);
      setStatus(statusRes);
      setIntervalInput(statusRes.interval_minutes);
      setRuns(runsRes.items);
      setTotalRuns(runsRes.total);
      setError(null);
    } catch (err: any) {
      if (err instanceof ApiError) {
        setError(err.detail);
      } else {
        setError('Failed to connect to scheduler service.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchSchedulerData();
    const interval = setInterval(fetchSchedulerData, 10000);
    return () => clearInterval(interval);
  }, []);

  const handleToggleEnable = async () => {
    if (!status) return;
    setIsSavingConfig(true);
    setError(null);
    setSuccessMsg(null);
    try {
      const updated = await api.scheduler.updateConfig({ enabled: !status.is_enabled });
      setStatus(updated);
      setSuccessMsg(updated.is_enabled ? 'Scheduler enabled successfully.' : 'Scheduler paused.');
    } catch (err: any) {
      setError(err instanceof ApiError ? err.detail : 'Failed to update scheduler status.');
    } finally {
      setIsSavingConfig(false);
    }
  };

  const handleSaveInterval = async (e: React.FormEvent) => {
    e.preventDefault();
    if (intervalInput < 5 || intervalInput > 10080) {
      setError('Interval must be between 5 minutes and 10080 minutes (7 days).');
      return;
    }
    setIsSavingConfig(true);
    setError(null);
    setSuccessMsg(null);
    try {
      const updated = await api.scheduler.updateConfig({ interval_minutes: intervalInput });
      setStatus(updated);
      setSuccessMsg(`Interval updated to ${intervalInput} minutes.`);
    } catch (err: any) {
      setError(err instanceof ApiError ? err.detail : 'Failed to save interval.');
    } finally {
      setIsSavingConfig(false);
    }
  };

  const handleTriggerDiscovery = async () => {
    setIsRunningDiscovery(true);
    setError(null);
    setSuccessMsg(null);
    try {
      const res = await api.scheduler.run({ use_ai_matching: false });
      setSuccessMsg(`Discovery run completed: ${res.inserted} new jobs discovered, ${res.jobs_eligible} eligible matches.`);
      await fetchSchedulerData();
    } catch (err: any) {
      if (err instanceof ApiError) {
        setError(err.detail);
      } else {
        setError('Discovery run failed. Check backend logs.');
      }
    } finally {
      setIsRunningDiscovery(false);
    }
  };

  const getStatusBadge = (runStatus: string) => {
    switch (runStatus) {
      case 'COMPLETED':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            <CheckCircle2 className="w-3.5 h-3.5" />
            <span>Success</span>
          </span>
        );
      case 'PARTIAL_SUCCESS':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-amber-500/10 text-amber-400 border border-amber-500/20">
            <AlertTriangle className="w-3.5 h-3.5" />
            <span>Partial Success</span>
          </span>
        );
      case 'FAILED':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-rose-500/10 text-rose-400 border border-rose-500/20">
            <AlertCircle className="w-3.5 h-3.5" />
            <span>Failed</span>
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
            <RotateCw className="w-3.5 h-3.5 animate-spin" />
            <span>{runStatus}</span>
          </span>
        );
    }
  };

  if (isLoading) {
    return (
      <div className="space-y-4">
        <LoadingSkeleton count={2} className="h-32" />
        <LoadingSkeleton count={1} className="h-64" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Safety Notice Banner */}
      <div className="rounded-2xl border border-indigo-500/30 bg-gradient-to-r from-indigo-950/40 to-slate-900/60 p-4 flex items-start gap-3 backdrop-blur-md">
        <Info className="w-5 h-5 text-indigo-400 shrink-0 mt-0.5" />
        <div className="text-xs text-slate-300 leading-relaxed">
          <span className="font-semibold text-slate-100">Scheduled Discovery Safety Boundary:</span> Scheduled discovery only queries supported job sources, evaluates deterministic eligibility, and delivers match notifications. It <strong className="text-indigo-300">never automatically prepares, approves, or submits applications</strong>.
        </div>
      </div>

      {error && (
        <div className="rounded-xl border border-rose-500/20 bg-rose-500/10 p-3 text-xs text-rose-300 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
          <button onClick={() => setError(null)} className="text-rose-400 hover:text-rose-200">
            &times;
          </button>
        </div>
      )}

      {successMsg && (
        <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/10 p-3 text-xs text-emerald-300 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 shrink-0" />
            <span>{successMsg}</span>
          </div>
          <button onClick={() => setSuccessMsg(null)} className="text-emerald-400 hover:text-emerald-200">
            &times;
          </button>
        </div>
      )}

      {/* Control Bar & State Cards */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Scheduler Control Panel */}
        <Card className="lg:col-span-2">
          <div className="flex items-center justify-between pb-4 border-b border-slate-800">
            <div className="flex items-center gap-2.5">
              <CalendarClock className="w-5 h-5 text-indigo-400" />
              <h3 className="text-base font-semibold text-slate-100">Discovery Scheduler</h3>
            </div>
            <div className="flex items-center gap-3">
              <span
                className={`text-xs font-semibold px-2.5 py-1 rounded-full border ${
                  status?.is_enabled
                    ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                    : 'bg-slate-800 text-slate-400 border-slate-700'
                }`}
              >
                {status?.is_enabled ? 'Active / Enabled' : 'Paused / Disabled'}
              </span>
              <Button
                variant={status?.is_enabled ? 'danger' : 'primary'}
                size="sm"
                onClick={handleToggleEnable}
                disabled={isSavingConfig}
              >
                {status?.is_enabled ? 'Disable Scheduler' : 'Enable Scheduler'}
              </Button>
            </div>
          </div>

          <div className="mt-5 grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Interval Configuration Form */}
            <form onSubmit={handleSaveInterval} className="space-y-3">
              <label className="block text-xs font-semibold text-slate-300">
                Discovery Interval (Minutes)
              </label>
              <div className="flex items-center gap-2">
                <input
                  type="number"
                  min={5}
                  max={10080}
                  value={intervalInput}
                  onChange={(e) => setIntervalInput(parseInt(e.target.value) || 0)}
                  className="w-32 bg-slate-800/80 border border-slate-700 text-slate-100 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/50"
                  placeholder="240"
                />
                <Button type="submit" variant="secondary" size="sm" disabled={isSavingConfig}>
                  Save Interval
                </Button>
              </div>
              <p className="text-[11px] text-slate-500">
                Accepted range: 5 to 10,080 minutes (Default: 240m / 4h).
              </p>
            </form>

            {/* Manual Run Action */}
            <div className="bg-slate-800/40 rounded-xl p-4 border border-slate-800 flex flex-col justify-between">
              <div>
                <span className="text-xs font-semibold text-slate-200">Manual Discovery Trigger</span>
                <p className="text-[11px] text-slate-400 mt-1 leading-normal">
                  Execute the exact same 12-stage discovery and matching pipeline immediately without waiting for the next scheduled tick.
                </p>
              </div>
              <div className="mt-3">
                <Button
                  onClick={handleTriggerDiscovery}
                  disabled={isRunningDiscovery || status?.is_active_run}
                  size="sm"
                  className="w-full"
                >
                  {isRunningDiscovery || status?.is_active_run ? (
                    <>
                      <RotateCw className="w-4 h-4 animate-spin mr-1.5" />
                      <span>Running Discovery...</span>
                    </>
                  ) : (
                    <>
                      <Play className="w-4 h-4 mr-1.5 fill-current" />
                      <span>Run Discovery Now</span>
                    </>
                  )}
                </Button>
              </div>
            </div>
          </div>
        </Card>

        {/* Latest Run Summary Card */}
        <Card>
          <div className="flex items-center justify-between pb-3 border-b border-slate-800">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Latest Run</span>
            {status?.last_run && getStatusBadge(status.last_run.status)}
          </div>
          {status?.last_run ? (
            <div className="mt-4 space-y-3">
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div className="bg-slate-800/50 p-2.5 rounded-xl border border-slate-800">
                  <span className="text-slate-400 block text-[10px]">Discovered</span>
                  <span className="text-base font-bold text-slate-100">{status.last_run.items_processed}</span>
                </div>
                <div className="bg-slate-800/50 p-2.5 rounded-xl border border-slate-800">
                  <span className="text-slate-400 block text-[10px]">Eligible Matches</span>
                  <span className="text-base font-bold text-emerald-400">{status.last_run.metadata?.jobs_eligible ?? 0}</span>
                </div>
              </div>
              <div className="text-[11px] space-y-1 text-slate-400 pt-1">
                <div className="flex justify-between">
                  <span>Trigger:</span>
                  <span className="text-slate-200 font-medium capitalize">{status.last_run.metadata?.trigger || 'manual'}</span>
                </div>
                <div className="flex justify-between">
                  <span>Started:</span>
                  <span className="text-slate-200">{formatDate(status.last_run.started_at)}</span>
                </div>
                {status.next_run_time && (
                  <div className="flex justify-between pt-1 border-t border-slate-800/60">
                    <span className="text-indigo-300">Next Scheduled:</span>
                    <span className="text-indigo-200 font-medium">{formatDate(status.next_run_time)}</span>
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="mt-8 text-center text-slate-500 text-xs">
              No previous runs recorded.
            </div>
          )}
        </Card>
      </div>

      {/* Discovery Sources & Health Diagnostics */}
      <DiscoverySourcesCard />

      {/* Discovery Run History Table */}
      <Card>
        <div className="flex items-center justify-between pb-4 border-b border-slate-800">
          <div className="flex items-center gap-2">
            <Layers className="w-5 h-5 text-indigo-400" />
            <h3 className="text-base font-semibold text-slate-100">Run History</h3>
            <span className="text-xs text-slate-400">({totalRuns} total)</span>
          </div>
          <Button variant="ghost" size="sm" onClick={fetchSchedulerData}>
            <RotateCw className="w-3.5 h-3.5 mr-1" />
            <span>Refresh</span>
          </Button>
        </div>

        <div className="overflow-x-auto mt-4">
          <table className="w-full text-left text-xs text-slate-300">
            <thead className="text-[11px] uppercase tracking-wider text-slate-400 bg-slate-800/40 border-b border-slate-800">
              <tr>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4">Trigger</th>
                <th className="py-3 px-4">Discovered</th>
                <th className="py-3 px-4">Saved / Evaluated</th>
                <th className="py-3 px-4">Started At</th>
                <th className="py-3 px-4">Completed</th>
                <th className="py-3 px-4 text-right">Details</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {runs.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-8 text-center text-slate-500">
                    No run history available.
                  </td>
                </tr>
              ) : (
                runs.map((r) => (
                  <tr key={r.id} className="hover:bg-slate-800/30 transition-colors">
                    <td className="py-3 px-4">{getStatusBadge(r.status)}</td>
                    <td className="py-3 px-4 font-medium capitalize text-slate-200">
                      {r.metadata?.trigger || (r.run_type.includes('scheduled') ? 'scheduled' : 'manual')}
                    </td>
                    <td className="py-3 px-4">{r.items_processed} jobs</td>
                    <td className="py-3 px-4">
                      {r.metadata?.jobs_inserted ?? r.items_succeeded} inserted &middot; {r.metadata?.jobs_eligible ?? 0} eligible
                    </td>
                    <td className="py-3 px-4 text-slate-400">{formatDate(r.started_at)}</td>
                    <td className="py-3 px-4 text-slate-400">
                      {r.completed_at ? formatDate(r.completed_at) : 'In Progress'}
                    </td>
                    <td className="py-3 px-4 text-right">
                      <button
                        type="button"
                        onClick={() => setSelectedRun(r)}
                        className="text-xs text-indigo-400 hover:text-indigo-300 font-medium inline-flex items-center gap-1"
                      >
                        <span>Diagnostics</span>
                        <ChevronRight className="w-3.5 h-3.5" />
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Diagnostics Modal */}
      {selectedRun && (
        <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-700/80 rounded-2xl max-w-lg w-full p-6 shadow-2xl animate-in fade-in zoom-in-95">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <div className="flex items-center gap-2">
                <span className="font-semibold text-slate-100 text-sm">Run Diagnostics</span>
                {getStatusBadge(selectedRun.status)}
              </div>
              <button
                type="button"
                onClick={() => setSelectedRun(null)}
                className="text-slate-400 hover:text-slate-200 text-lg leading-none"
              >
                &times;
              </button>
            </div>

            <div className="mt-4 space-y-3 text-xs">
              <div className="flex justify-between py-1 border-b border-slate-800/60">
                <span className="text-slate-400">Run ID:</span>
                <span className="text-slate-200 font-mono text-[11px]">{selectedRun.id}</span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-800/60">
                <span className="text-slate-400">Trigger Mode:</span>
                <span className="text-slate-200 capitalize">{selectedRun.metadata?.trigger || 'manual'}</span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-800/60">
                <span className="text-slate-400">Sources Attempted:</span>
                <span className="text-slate-200">
                  {selectedRun.metadata?.sources_attempted?.join(', ') || 'synthetic'}
                </span>
              </div>
              {selectedRun.error_summary && (
                <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-300">
                  <span className="font-semibold block mb-1">Error Summary:</span>
                  <p className="font-mono text-[11px] leading-relaxed break-words">{selectedRun.error_summary}</p>
                </div>
              )}
              {selectedRun.metadata?.source_diagnostics && (
                <div className="space-y-2 pt-2">
                  <span className="font-semibold text-slate-300">Source Diagnostics:</span>
                  {Object.entries(selectedRun.metadata.source_diagnostics).map(([src, diag]: any) => (
                    <div key={src} className="p-2.5 rounded-lg bg-slate-800/60 border border-slate-800 text-[11px]">
                      <div className="flex justify-between font-semibold text-slate-200">
                        <span className="capitalize">{src}</span>
                        <span className={diag.status === 'SUCCESS' ? 'text-emerald-400' : 'text-rose-400'}>
                          {diag.status}
                        </span>
                      </div>
                      {diag.error ? (
                        <p className="text-rose-300 mt-1 font-mono text-[10px] break-words">{diag.error}</p>
                      ) : (
                        <div className="text-slate-400 mt-1 flex gap-3 text-[10px]">
                          <span>Discovered: {diag.discovered}</span>
                          <span>Inserted: {diag.inserted}</span>
                          <span>Unchanged: {diag.unchanged}</span>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="mt-6 flex justify-end">
              <Button size="sm" variant="secondary" onClick={() => setSelectedRun(null)}>
                Close
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
