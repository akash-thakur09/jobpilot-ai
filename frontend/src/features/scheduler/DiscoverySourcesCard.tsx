import React, { useState, useEffect } from 'react';
import { JobSource, JobSourceConfigUpdate, JobImportResponse } from '../../types';
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
  UploadCloud,
  Lock,
  Layers,
  Sparkles,
} from 'lucide-react';

export const DiscoverySourcesCard: React.FC = () => {
  const [sources, setSources] = useState<JobSource[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editingSourceId, setEditingSourceId] = useState<string | null>(null);
  const [editBoardToken, setEditBoardToken] = useState('');
  const [editFeedUrl, setEditFeedUrl] = useState('');
  const [editIsEnabled, setEditIsEnabled] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [saveSuccessMsg, setSaveSuccessMsg] = useState<string | null>(null);
  const [expandedErrors, setExpandedErrors] = useState<Record<string, boolean>>({});

  // Manual import state
  const [importingSourceId, setImportingSourceId] = useState<string | null>(null);
  const [importPayload, setImportPayload] = useState('');
  const [importFormat, setImportFormat] = useState<'json' | 'email_text'>('email_text');
  const [isImporting, setIsImporting] = useState(false);
  const [importResult, setImportResult] = useState<JobImportResponse | null>(null);

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
    const cfg = source.config_json || {};
    if (cfg.board_tokens && Array.isArray(cfg.board_tokens)) {
      setEditBoardToken(cfg.board_tokens.join(', '));
    } else if (cfg.site_tokens && Array.isArray(cfg.site_tokens)) {
      setEditBoardToken(cfg.site_tokens.join(', '));
    } else if (cfg.board_token) {
      setEditBoardToken(cfg.board_token);
    } else if (cfg.site_token) {
      setEditBoardToken(cfg.site_token);
    } else {
      setEditBoardToken(source.board_identifier || '');
    }
    setEditFeedUrl(cfg.rss_url || cfg.feed_url || '');
    setEditIsEnabled(source.is_enabled !== undefined ? source.is_enabled : source.is_active);
    setSaveSuccessMsg(null);
  };

  const handleCancelEdit = () => {
    setEditingSourceId(null);
    setEditBoardToken('');
    setEditFeedUrl('');
    setError(null);
  };

  const handleSaveConfig = async (identifier: string) => {
    setIsSaving(true);
    setError(null);
    setSaveSuccessMsg(null);

    // Validation: board_token alphanumeric, dash, underscore, comma, space
    if (editBoardToken.trim() && !/^[a-zA-Z0-9_\-,\s]+$/.test(editBoardToken.trim())) {
      setError('Board identifier must contain only alphanumeric characters, underscores, hyphens, and commas.');
      setIsSaving(false);
      return;
    }

    const tokens = editBoardToken
      .split(',')
      .map((t) => t.trim())
      .filter(Boolean);

    const payload: JobSourceConfigUpdate = {
      is_enabled: editIsEnabled,
      board_tokens: identifier === 'greenhouse' ? tokens : undefined,
      board_token: identifier === 'greenhouse' && tokens.length > 0 ? tokens[0] : undefined,
      site_tokens: identifier === 'lever' ? tokens : undefined,
      site_token: identifier === 'lever' && tokens.length > 0 ? tokens[0] : undefined,
      rss_url: identifier === 'hirist' ? editFeedUrl.trim() : undefined,
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

  const handleStartImport = (source: JobSource) => {
    setImportingSourceId(source.identifier);
    setImportPayload('');
    setImportResult(null);
    setError(null);
  };

  const handleCancelImport = () => {
    setImportingSourceId(null);
    setImportPayload('');
    setImportResult(null);
  };

  const handleSubmitImport = async (sourceIdentifier: string) => {
    if (!importPayload.trim()) {
      setError('Please provide a payload to import.');
      return;
    }
    setIsImporting(true);
    setError(null);
    setImportResult(null);

    let parsedData: any = importPayload;
    if (importFormat === 'json') {
      try {
        parsedData = JSON.parse(importPayload);
      } catch (jsonErr: any) {
        setError('Invalid JSON format. Please check your syntax or switch to Email/Alert format.');
        setIsImporting(false);
        return;
      }
    }

    try {
      const res = await api.jobs.importJobs(sourceIdentifier, {
        source_identifier: sourceIdentifier,
        format: importFormat,
        payload: parsedData,
      });
      setImportResult(res);
      setSaveSuccessMsg(`Successfully imported ${res.items_saved} jobs from ${sourceIdentifier}.`);
      await fetchSources();
    } catch (err: any) {
      setError(err instanceof ApiError ? err.detail : 'Failed to import jobs.');
    } finally {
      setIsImporting(false);
    }
  };

  const toggleErrorExpand = (id: string) => {
    setExpandedErrors((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const getIntegrationBadge = (status?: string) => {
    const s = (status || 'AVAILABLE').toUpperCase();
    switch (s) {
      case 'AVAILABLE':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
            <CheckCircle2 className="w-3.5 h-3.5" />
            Available
          </span>
        );
      case 'CONFIGURATION_REQUIRED':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-sky-500/15 text-sky-400 border border-sky-500/30">
            <Layers className="w-3.5 h-3.5" />
            Config Required
          </span>
        );
      case 'AUTHORIZATION_REQUIRED':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-500/15 text-amber-400 border border-amber-500/30">
            <Lock className="w-3.5 h-3.5" />
            Auth Required
          </span>
        );
      case 'MANUAL_IMPORT_ONLY':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-purple-500/15 text-purple-400 border border-purple-500/30">
            <UploadCloud className="w-3.5 h-3.5" />
            Manual Import / Alert
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-slate-800 text-slate-400 border border-slate-700">
            {s}
          </span>
        );
    }
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
      case 'ERROR':
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
            <h3 className="text-base font-semibold text-slate-100">Job Discovery Sources & Indian Platforms</h3>
          </div>
          <p className="text-xs text-slate-400 mt-0.5">
            Manage ATS adapters (Greenhouse, Lever) and Indian tech job platforms (Naukri, Instahyre, Cutshort, Hirist, Foundit, LinkedIn, Indeed) with compliance boundaries and alert ingestion.
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
          Compliance & Ethics Bound: Direct scraping against anti-bot challenges is avoided. Platforms utilize official public APIs, validated employer tokens, RSS category feeds, or inbound email alert and structured JSON ingestion.
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
          const isImportingThis = importingSourceId === source.identifier;
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
                      ['greenhouse', 'lever'].includes(source.identifier)
                        ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30'
                        : ['naukri', 'instahyre', 'cutshort', 'indeed', 'foundit', 'linkedin'].includes(source.identifier)
                        ? 'bg-purple-500/15 text-purple-400 border border-purple-500/30'
                        : source.identifier === 'hirist'
                        ? 'bg-sky-500/15 text-sky-400 border border-sky-500/30'
                        : 'bg-indigo-500/15 text-indigo-400 border border-indigo-500/30'
                    }`}
                  >
                    {source.identifier.slice(0, 2)}
                  </div>
                  <div>
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-semibold text-sm text-slate-100">{source.name}</span>
                      <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-400">
                        {source.identifier}
                      </span>
                      {getIntegrationBadge(source.integration_status)}
                    </div>
                    <div className="text-xs text-slate-400 mt-0.5">
                      Type: <span className="text-slate-300 font-medium capitalize">{source.source_type || 'job_board'}</span>
                      {source.config_json?.board_tokens && source.config_json.board_tokens.length > 0 ? (
                        <> &middot; Boards: <span className="text-indigo-300 font-mono font-medium">{source.config_json.board_tokens.join(', ')}</span></>
                      ) : source.config_json?.site_tokens && source.config_json.site_tokens.length > 0 ? (
                        <> &middot; Sites: <span className="text-indigo-300 font-mono font-medium">{source.config_json.site_tokens.join(', ')}</span></>
                      ) : source.config_json?.rss_url ? (
                        <> &middot; Feed: <span className="text-sky-300 font-mono font-medium truncate max-w-xs inline-block align-bottom">{source.config_json.rss_url}</span></>
                      ) : null}
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-2 self-end sm:self-center flex-wrap">
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

                  {/* Import Button */}
                  {!isImportingThis && (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleStartImport(source)}
                      className="text-purple-300 border-purple-500/30 hover:bg-purple-500/10"
                    >
                      <UploadCloud className="w-3.5 h-3.5 mr-1" />
                      <span>Import</span>
                    </Button>
                  )}

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
                    <div className="flex-1 w-full space-y-2">
                      {['greenhouse', 'lever'].includes(source.identifier) ? (
                        <>
                          <label className="block text-xs font-semibold text-slate-300">
                            Configured Employer Board Tokens (Comma-separated for multi-board)
                          </label>
                          <input
                            type="text"
                            value={editBoardToken}
                            onChange={(e) => setEditBoardToken(e.target.value)}
                            placeholder="e.g. canonical, stripe, github"
                            className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-slate-100 font-mono placeholder-slate-500 focus:outline-none focus:border-indigo-500"
                          />
                        </>
                      ) : (
                        <>
                          <label className="block text-xs font-semibold text-slate-300">
                            Custom RSS Feed URL / Publisher ID
                          </label>
                          <input
                            type="text"
                            value={editFeedUrl}
                            onChange={(e) => setEditFeedUrl(e.target.value)}
                            placeholder="e.g. https://www.hirist.tech/rss/python or Indeed Publisher ID"
                            className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-slate-100 font-mono placeholder-slate-500 focus:outline-none focus:border-indigo-500"
                          />
                        </>
                      )}
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

              {/* Manual / Alert Import Panel */}
              {isImportingThis && (
                <div className="mt-4 pt-4 border-t border-slate-800/80 bg-purple-950/20 p-4 rounded-lg border border-purple-900/30">
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2">
                      <UploadCloud className="w-4 h-4 text-purple-400" />
                      <span className="text-xs font-semibold text-purple-200">
                        Import Jobs & Email Alerts for {source.name}
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <label className="text-[11px] text-slate-400 flex items-center gap-1 cursor-pointer">
                        <input
                          type="radio"
                          name={`format_${source.identifier}`}
                          checked={importFormat === 'email_text'}
                          onChange={() => setImportFormat('email_text')}
                        />
                        <span>Email / Alert Text</span>
                      </label>
                      <label className="text-[11px] text-slate-400 flex items-center gap-1 cursor-pointer">
                        <input
                          type="radio"
                          name={`format_${source.identifier}`}
                          checked={importFormat === 'json'}
                          onChange={() => setImportFormat('json')}
                        />
                        <span>JSON Array</span>
                      </label>
                    </div>
                  </div>

                  <textarea
                    rows={4}
                    value={importPayload}
                    onChange={(e) => setImportPayload(e.target.value)}
                    placeholder={
                      importFormat === 'email_text'
                        ? "Paste alert text or email snippet. E.g.:\nRole: Full Stack Python Developer\nCompany: Flipkart\nExperience: 3-6 Yrs\nSalary: 20-30 LPA\nLocation: Bengaluru\nURL: https://..."
                        : '[{"title": "AI Engineer", "company": "Swiggy", "salary": "25-35 LPA", "location": "Remote", "url": "https://..."}]'
                    }
                    className="w-full bg-slate-900 border border-slate-700 rounded-lg p-2.5 text-xs text-slate-100 font-mono placeholder-slate-500 focus:outline-none focus:border-purple-500"
                  />

                  {importResult && (
                    <div className="mt-2.5 p-2.5 rounded bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-xs flex items-center justify-between">
                      <span>
                        Parsed: <strong>{importResult.items_parsed}</strong> &middot; Saved: <strong>{importResult.items_saved}</strong> &middot; Relevant: <strong>{importResult.items_relevant}</strong> &middot; Duplicates: <strong>{importResult.duplicates_detected}</strong>
                      </span>
                    </div>
                  )}

                  <div className="mt-3 flex items-center justify-end gap-2">
                    <Button
                      type="button"
                      variant="primary"
                      size="sm"
                      disabled={isImporting || !importPayload.trim()}
                      onClick={() => handleSubmitImport(source.identifier)}
                      className="bg-purple-600 hover:bg-purple-500 text-white"
                    >
                      <Sparkles className="w-3.5 h-3.5 mr-1" />
                      <span>{isImporting ? 'Ingesting...' : 'Ingest & Evaluate'}</span>
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={handleCancelImport}
                    >
                      <X className="w-3.5 h-3.5 mr-1" />
                      <span>Close</span>
                    </Button>
                  </div>
                </div>
              )}

              {/* Health Diagnostics & Stats Bar */}
              <div className="mt-3 pt-3 border-t border-slate-800/60 flex flex-wrap items-center justify-between gap-2 text-xs text-slate-400">
                <div className="flex items-center gap-4 flex-wrap">
                  <span>
                    Last Executed: <strong className="text-slate-300 font-medium">{formatDate(source.last_run_at || source.last_discovered_at)}</strong>
                  </span>
                  <span>
                    Jobs Discovered: <strong className="text-indigo-300 font-medium">{source.jobs_discovered_count ?? 0}</strong>
                  </span>
                  <span>
                    Relevant Jobs: <strong className="text-emerald-400 font-medium">{source.jobs_relevant_count ?? 0}</strong>
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
