import React, { useState, useEffect } from 'react';
import { JobSource, JobSourceConfigUpdate } from '../../types';
import { api, ApiError } from '../../lib/api-client';
import { Card } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import {
  Globe,
  CheckCircle2,
  AlertCircle,
  AlertTriangle,
  RotateCw,
  Edit2,
  Save,
  X,
  ShieldCheck,
  Power,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';

export const DiscoverySourcesCard: React.FC = () => {
  const [sources, setSources] = useState<JobSource[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editingSourceId, setEditingSourceId] = useState<string | null>(null);
  const [editBoardToken, setEditBoardToken] = useState('');
  const [editIsEnabled, setEditIsEnabled] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [saveSuccessMsg, setSaveSuccessMsg] = useState<string | null>(null);
  const [expandedErrors, setExpandedErrors] = useState<Record<string, boolean>>({});

  const fetchSources = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await api.jobs.listSources();
      setSources(data);
    } catch (err: any) {
      if (err instanceof ApiError) {
        setError(err.detail);
      } else {
        setError('Failed to load discovery sources.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchSources();
  }, []);

  const handleStartEdit = (source: JobSource) => {
    setEditingSourceId(source.identifier);
    setEditBoardToken(source.board_identifier || '');
    setEditIsEnabled(source.is_enabled !== undefined ? source.is_enabled : source.is_active);
    setSaveSuccessMsg(null);
  };

  const handleCancelEdit = () => {
    setEditingSourceId(null);
    setEditBoardToken('');
    setError(null);
  };

  const handleSaveConfig = async (identifier: string) => {
    setIsSaving(true);
    setError(null);
    setSaveSuccessMsg(null);

    // Validation: board_token alphanumeric, dash, underscore
    if (editBoardToken.trim() && !/^[a-zA-Z0-9_\-]+$/.test(editBoardToken.trim())) {
      setError('Board identifier must contain only alphanumeric characters, underscores, and hyphens.');
      setIsSaving(false);
      return;
    }

    const payload: JobSourceConfigUpdate = {
      is_enabled: editIsEnabled,
      board_token: editBoardToken.trim() || undefined,
    };

    try {
      const updated = await api.jobs.updateSource(identifier, payload);
      setSources((prev) =>
        prev.map((s) => (s.identifier === identifier ? updated : s))
      );
      setSaveSuccessMsg(`Configuration saved for source "${identifier}".`);
      setEditingSourceId(null);
    } catch (err: any) {
      if (err instanceof ApiError) {
        setError(err.detail);
      } else {
        setError('Failed to update source configuration.');
      }
    } finally {
      setIsSaving(false);
    }
  };

  const handleToggleSourceEnabled = async (source: JobSource) => {
    const currentEnabled = source.is_enabled !== undefined ? source.is_enabled : source.is_active;
    const newEnabled = !currentEnabled;
    try {
      const updated = await api.jobs.updateSource(source.identifier, { is_enabled: newEnabled });
      setSources((prev) =>
        prev.map((s) => (s.identifier === source.identifier ? updated : s))
      );
    } catch (err: any) {
      setError(err instanceof ApiError ? err.detail : 'Failed to toggle source.');
    }
  };

  const toggleErrorExpand = (id: string) => {
    setExpandedErrors((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const getHealthBadge = (source: JobSource) => {
    const status = (source.last_status || 'IDLE').toUpperCase();
    switch (status) {
      case 'HEALTHY':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
            <CheckCircle2 className="w-3.5 h-3.5" />
            Healthy
          </span>
        );
      case 'PARTIAL':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-500/15 text-amber-400 border border-amber-500/30">
            <AlertTriangle className="w-3.5 h-3.5" />
            Partial Health
          </span>
        );
      case 'FAILED':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-rose-500/15 text-rose-400 border border-rose-500/30">
            <AlertCircle className="w-3.5 h-3.5" />
            Failed Run
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-slate-800 text-slate-400 border border-slate-700">
            Idle / Configured
          </span>
        );
    }
  };

  const formatDate = (isoString?: string | null) => {
    if (!isoString) return 'Never executed';
    try {
      return new Date(isoString).toLocaleString('en-US', {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return isoString;
    }
  };

  return (
    <Card className="p-6 border-slate-800 bg-slate-900/60 backdrop-blur-md">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-slate-800 gap-3">
        <div>
          <div className="flex items-center gap-2">
            <Globe className="w-5 h-5 text-indigo-400" />
            <h3 className="text-base font-semibold text-slate-100">Job Discovery Sources & Board Health</h3>
          </div>
          <p className="text-xs text-slate-400 mt-0.5">
            Manage public job board adapters (Greenhouse, Lever) with validated identifiers, health diagnostics, and error reporting.
          </p>
        </div>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={fetchSources}
          disabled={isLoading || isSaving}
        >
          <RotateCw className={`w-3.5 h-3.5 mr-1 ${isLoading ? 'animate-spin' : ''}`} />
          <span>Refresh</span>
        </Button>
      </div>

      {/* Safety Notice */}
      <div className="mt-4 p-3 rounded-xl bg-slate-800/40 border border-slate-800 text-xs text-slate-400 flex items-center gap-2">
        <ShieldCheck className="w-4 h-4 text-indigo-400 shrink-0" />
        <span>
          Strict Adapter Boundaries: Only verified Greenhouse/Lever board identifiers are permitted. Arbitrary URLs and network crawling are blocked by design.
        </span>
      </div>

      {error && (
        <div className="mt-4 p-3 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs flex items-center gap-2">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {saveSuccessMsg && (
        <div className="mt-4 p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 shrink-0" />
          <span>{saveSuccessMsg}</span>
        </div>
      )}

      {/* Sources Grid */}
      <div className="mt-6 space-y-4">
        {sources.map((source) => {
          const isEditing = editingSourceId === source.identifier;
          const isEnabled = source.is_enabled !== undefined ? source.is_enabled : source.is_active;
          const hasError = Boolean(source.last_error_summary);
          const isExpanded = Boolean(expandedErrors[source.identifier]);

          return (
            <div
              key={source.id || source.identifier}
              className={`p-4 rounded-xl border transition-all ${
                isEnabled
                  ? 'bg-slate-900/90 border-slate-800'
                  : 'bg-slate-950/60 border-slate-900 opacity-70'
              }`}
            >
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div className="flex items-center gap-3">
                  <div
                    className={`w-9 h-9 rounded-lg flex items-center justify-center font-bold text-xs uppercase ${
                      source.identifier === 'greenhouse'
                        ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30'
                        : source.identifier === 'lever'
                        ? 'bg-blue-500/15 text-blue-400 border border-blue-500/30'
                        : 'bg-purple-500/15 text-purple-400 border border-purple-500/30'
                    }`}
                  >
                    {source.identifier.slice(0, 2)}
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-sm text-slate-100">{source.name}</span>
                      <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-400">
                        {source.identifier}
                      </span>
                    </div>
                    <div className="text-xs text-slate-400 mt-0.5">
                      Type: <span className="text-slate-300 font-medium capitalize">{source.source_type || source.identifier}</span>
                      {source.board_identifier && (
                        <> &middot; Board: <span className="text-indigo-300 font-mono font-medium">{source.board_identifier}</span></>
                      )}
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-3 self-end sm:self-center">
                  {getHealthBadge(source)}

                  {/* Toggle button */}
                  <button
                    type="button"
                    onClick={() => handleToggleSourceEnabled(source)}
                    className={`p-1.5 rounded-lg border text-xs font-medium flex items-center gap-1.5 transition-colors ${
                      isEnabled
                        ? 'bg-emerald-500/10 text-emerald-300 border-emerald-500/30 hover:bg-emerald-500/20'
                        : 'bg-slate-800 text-slate-400 border-slate-700 hover:text-slate-200'
                    }`}
                    title={isEnabled ? 'Click to disable source' : 'Click to enable source'}
                  >
                    <Power className="w-3.5 h-3.5" />
                    <span>{isEnabled ? 'Enabled' : 'Disabled'}</span>
                  </button>

                  {!isEditing && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleStartEdit(source)}
                      className="text-slate-400 hover:text-slate-200"
                    >
                      <Edit2 className="w-3.5 h-3.5 mr-1" />
                      <span>Configure</span>
                    </Button>
                  )}
                </div>
              </div>

              {/* Edit form */}
              {isEditing && (
                <div className="mt-4 pt-4 border-t border-slate-800/80 bg-slate-950/50 p-3.5 rounded-lg">
                  <div className="flex flex-col sm:flex-row items-start sm:items-end gap-3">
                    <div className="flex-1 w-full">
                      <label className="block text-xs font-semibold text-slate-300 mb-1">
                        Configured Board Identifier / Token
                      </label>
                      <input
                        type="text"
                        value={editBoardToken}
                        onChange={(e) => setEditBoardToken(e.target.value)}
                        placeholder="e.g. airbnb, stripe, gitlab"
                        className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-slate-100 font-mono placeholder-slate-500 focus:outline-none focus:border-indigo-500"
                      />
                      <span className="text-[10px] text-slate-500 mt-1 block">
                        Must match exact board slug on {source.name} (letters, numbers, underscores, hyphens only).
                      </span>
                    </div>

                    <div className="flex items-center gap-2">
                      <Button
                        type="button"
                        variant="primary"
                        size="sm"
                        disabled={isSaving}
                        onClick={() => handleSaveConfig(source.identifier)}
                      >
                        <Save className="w-3.5 h-3.5 mr-1" />
                        <span>{isSaving ? 'Saving...' : 'Save'}</span>
                      </Button>
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={handleCancelEdit}
                      >
                        <X className="w-3.5 h-3.5 mr-1" />
                        <span>Cancel</span>
                      </Button>
                    </div>
                  </div>
                </div>
              )}

              {/* Health Diagnostics & Stats Bar */}
              <div className="mt-3 pt-3 border-t border-slate-800/60 flex flex-wrap items-center justify-between gap-2 text-xs text-slate-400">
                <div className="flex items-center gap-4">
                  <span>
                    Last Executed: <strong className="text-slate-300 font-medium">{formatDate(source.last_run_at || source.last_discovered_at)}</strong>
                  </span>
                  <span>
                    Jobs Discovered: <strong className="text-indigo-300 font-medium">{source.jobs_discovered_count ?? 0}</strong>
                  </span>
                </div>

                {hasError && (
                  <button
                    type="button"
                    onClick={() => toggleErrorExpand(source.identifier)}
                    className="text-rose-400 hover:text-rose-300 font-medium inline-flex items-center gap-1"
                  >
                    <span>View Error Summary</span>
                    {isExpanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                  </button>
                )}
              </div>

              {/* Expandable Error Summary */}
              {hasError && isExpanded && (
                <div className="mt-2.5 p-3 rounded-lg bg-rose-950/30 border border-rose-900/50 text-xs text-rose-300">
                  <div className="font-semibold text-rose-200 mb-1 flex items-center gap-1.5">
                    <AlertCircle className="w-3.5 h-3.5" />
                    Last Run Error Diagnostics:
                  </div>
                  <pre className="text-[11px] whitespace-pre-wrap font-mono text-rose-400/90 overflow-x-auto">
                    {source.last_error_summary}
                  </pre>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </Card>
  );
};
