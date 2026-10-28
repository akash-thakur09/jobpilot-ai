import React, { useState, useEffect } from 'react';
import {
  NotificationPreferences,
  NotificationPreferencesUpdate,
  EmailConfigStatus,
  DeliveryMode,
  DigestStatus,
  DeliveryHistoryItem,
} from '../../types';
import { api, ApiError } from '../../lib/api-client';
import { Button } from '../../components/ui/Button';
import {
  Bell,
  Mail,
  CheckCircle2,
  AlertCircle,
  Send,
  Save,
  X,
  Sliders,
  Lock,
  Clock,
  RefreshCw,
  Globe,
  History,
  AlertTriangle,
} from 'lucide-react';
import { formatDate } from '../../lib/formatters';

interface NotificationSettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

const COMMON_TIMEZONES = [
  'UTC',
  'America/New_York',
  'America/Chicago',
  'America/Denver',
  'America/Los_Angeles',
  'Europe/London',
  'Europe/Berlin',
  'Asia/Kolkata',
  'Asia/Tokyo',
  'Australia/Sydney',
];

export const NotificationSettingsModal: React.FC<NotificationSettingsModalProps> = ({
  isOpen,
  onClose,
}) => {
  const [prefs, setPrefs] = useState<NotificationPreferences>({
    email_enabled: false,
    recipient_email: '',
    notify_new_matches: true,
    notify_partial_discovery: true,
    notify_discovery_failures: true,
    notify_workflow_blockers: true,
    delivery_mode: 'IMMEDIATE',
    min_match_score: 70,
    timezone: 'UTC',
  });

  const [emailStatus, setEmailStatus] = useState<EmailConfigStatus | null>(null);
  const [digestStatus, setDigestStatus] = useState<DigestStatus | null>(null);
  const [deliveryHistory, setDeliveryHistory] = useState<DeliveryHistoryItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Test email state
  const [testEmailRecipient, setTestEmailRecipient] = useState('');
  const [isSendingTest, setIsSendingTest] = useState(false);
  const [testResult, setTestResult] = useState<{
    success: boolean;
    message: string;
    delivery_status?: string;
  } | null>(null);

  // Manual digest trigger state
  const [isTriggeringDigest, setIsTriggeringDigest] = useState(false);
  const [forceDigest, setForceDigest] = useState(false);
  const [digestTriggerResult, setDigestTriggerResult] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      loadData();
    }
  }, [isOpen]);

  const loadData = async () => {
    setIsLoading(true);
    setError(null);
    setSuccessMsg(null);
    setTestResult(null);
    setDigestTriggerResult(null);

    try {
      const [prefsData, statusData] = await Promise.all([
        api.notifications.getPreferences(),
        api.notifications.getEmailStatus(),
      ]);

      setPrefs({
        ...prefsData,
        timezone: prefsData.timezone || statusData?.timezone || 'UTC',
      });
      setEmailStatus(statusData);
      if (prefsData.recipient_email) {
        setTestEmailRecipient(prefsData.recipient_email);
      }
      setIsLoading(false);

      // Asynchronously load digest telemetry and delivery history
      if (typeof api.notifications?.getDigestStatus === 'function') {
        api.notifications
          .getDigestStatus()
          .then((d) => setDigestStatus(d))
          .catch(() => {});
      }
      if (typeof api.notifications?.getDeliveryHistory === 'function') {
        api.notifications
          .getDeliveryHistory(8)
          .then((h) => setDeliveryHistory(h?.items || []))
          .catch(() => {});
      }
    } catch (err: any) {
      if (err instanceof ApiError) {
        setError(err.detail);
      } else {
        setError('Failed to load notification settings.');
      }
      setIsLoading(false);
    }
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSaving(true);
    setError(null);
    setSuccessMsg(null);

    if (prefs.email_enabled && prefs.recipient_email) {
      const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
      if (!emailRegex.test(prefs.recipient_email)) {
        setError('Please enter a valid recipient email address.');
        setIsSaving(false);
        return;
      }
    }

    const payload: NotificationPreferencesUpdate = {
      email_enabled: prefs.email_enabled,
      recipient_email: prefs.recipient_email || null,
      notify_new_matches: prefs.notify_new_matches,
      notify_partial_discovery: prefs.notify_partial_discovery,
      notify_discovery_failures: prefs.notify_discovery_failures,
      notify_workflow_blockers: prefs.notify_workflow_blockers,
      delivery_mode: prefs.delivery_mode,
      min_match_score: prefs.min_match_score,
      timezone: prefs.timezone || 'UTC',
    };

    try {
      const updated = await api.notifications.updatePreferences(payload);
      setPrefs({
        ...updated,
        timezone: updated.timezone || 'UTC',
      });
      setSuccessMsg('Notification preferences saved successfully.');
      // Refresh digest status
      const updatedDigest = await api.notifications.getDigestStatus().catch(() => null);
      setDigestStatus(updatedDigest);
    } catch (err: any) {
      if (err instanceof ApiError) {
        setError(err.detail);
      } else {
        setError('Failed to save notification preferences.');
      }
    } finally {
      setIsSaving(false);
    }
  };

  const handleSendTestEmail = async () => {
    if (!testEmailRecipient || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(testEmailRecipient)) {
      setTestResult({
        success: false,
        message: 'Please provide a valid recipient email address to test delivery.',
      });
      return;
    }

    setIsSendingTest(true);
    setTestResult(null);

    try {
      const res = await api.notifications.sendTestEmail(testEmailRecipient);
      if (res.success) {
        setTestResult({
          success: true,
          message: `${res.message} (Provider: ${res.provider})`,
          delivery_status: res.delivery_status,
        });
        // Refresh delivery history
        const hist = await api.notifications.getDeliveryHistory(8).catch(() => ({ items: [], total: 0 }));
        setDeliveryHistory(hist.items || []);
      } else {
        setTestResult({
          success: false,
          message: res.message || 'Delivery rejected by provider.',
          delivery_status: res.delivery_status,
        });
      }
    } catch (err: any) {
      const msg = err instanceof ApiError ? err.detail : 'Failed to send test email.';
      setTestResult({
        success: false,
        message: msg,
      });
    } finally {
      setIsSendingTest(false);
    }
  };

  const handleTriggerDigest = async () => {
    setIsTriggeringDigest(true);
    setDigestTriggerResult(null);

    try {
      const res = await api.notifications.triggerDigest(forceDigest);
      setDigestTriggerResult(res.message);
      // Refresh data
      const [updatedDigest, hist] = await Promise.all([
        api.notifications.getDigestStatus().catch(() => null),
        api.notifications.getDeliveryHistory(8).catch(() => ({ items: [], total: 0 })),
      ]);
      setDigestStatus(updatedDigest);
      setDeliveryHistory(hist.items || []);
    } catch (err: any) {
      setDigestTriggerResult(err instanceof ApiError ? err.detail : 'Failed to trigger digest.');
    } finally {
      setIsTriggeringDigest(false);
    }
  };

  const renderStatusBadge = (status: string, isSimulated: boolean) => {
    const norm = status.toUpperCase();
    if (isSimulated || norm === 'SIMULATED') {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold bg-amber-500/15 text-amber-300 border border-amber-500/30">
          Simulated
        </span>
      );
    }
    if (norm === 'SENT') {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold bg-indigo-500/15 text-indigo-300 border border-indigo-500/30">
          Relay Accepted
        </span>
      );
    }
    if (norm === 'DELIVERED') {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">
          Delivered
        </span>
      );
    }
    if (norm === 'FAILED') {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold bg-rose-500/15 text-rose-300 border border-rose-500/30">
          Failed
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold bg-slate-800 text-slate-400 border border-slate-700">
        {status}
      </span>
    );
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm overflow-y-auto">
      <div className="relative w-full max-w-3xl bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl overflow-hidden my-8">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800 bg-slate-900/90">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-indigo-500/15 text-indigo-400 flex items-center justify-center border border-indigo-500/30">
              <Bell className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-base font-bold text-slate-100">Smart Alerts & Notification Delivery</h2>
              <p className="text-xs text-slate-400">
                Phase 10: Reliable email delivery, digest scheduling, and delivery status tracking.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-6 max-h-[75vh] overflow-y-auto">
          {isLoading ? (
            <div className="py-12 text-center text-slate-400 text-sm">
              <div className="w-6 h-6 border-2 border-indigo-400 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
              <span>Loading notification preferences & delivery history...</span>
            </div>
          ) : (
            <>
              {/* Email Provider Security & Status Banner */}
              <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 text-xs">
                <div className="flex items-center justify-between pb-2 border-b border-slate-800/80 mb-2.5">
                  <div className="flex items-center gap-2 font-semibold text-slate-200">
                    <Mail className="w-4 h-4 text-indigo-400" />
                    <span>Email Provider Semantics & Configuration</span>
                  </div>
                  {(emailStatus as any)?.configured || (emailStatus?.is_available && !emailStatus?.is_simulated) ? (
                    <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
                      <CheckCircle2 className="w-3 h-3" />
                      Provider Ready ({emailStatus?.provider || 'None'})
                    </span>
                  ) : emailStatus?.is_simulated ? (
                    <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-amber-500/15 text-amber-300 border border-amber-500/30">
                      <AlertTriangle className="w-3 h-3" />
                      Simulated Mode ({emailStatus?.provider || 'Mock'})
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-slate-800 text-slate-400 border border-slate-700">
                      Provider Disabled / Mock
                    </span>
                  )}
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-slate-400">
                  <div>
                    <span className="text-slate-500 block text-[10px] uppercase tracking-wider">Provider</span>
                    <span className="text-slate-200 font-medium capitalize">{emailStatus?.provider || 'None'}</span>
                  </div>
                  <div>
                    <span className="text-slate-500 block text-[10px] uppercase tracking-wider">Sender Address</span>
                    <span className="text-slate-200 font-mono text-[11px] truncate block">
                      {emailStatus?.from_address || 'Unconfigured'}
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-500 block text-[10px] uppercase tracking-wider">System Timezone</span>
                    <span className="text-slate-200 font-medium">{emailStatus?.timezone || 'UTC'}</span>
                  </div>
                  <div>
                    <span className="text-slate-500 block text-[10px] uppercase tracking-wider">Delivery Guarantee</span>
                    <span className="text-slate-200 font-medium">
                      {emailStatus?.is_simulated
                        ? 'Simulated (No Network)'
                        : 'Relay Handoff (RFC 5321)'}
                    </span>
                  </div>
                </div>

                <div className="mt-3 pt-2.5 border-t border-slate-800/60 flex items-center gap-1.5 text-[11px] text-slate-500">
                  <Lock className="w-3.5 h-3.5 text-indigo-400 shrink-0" />
                  <span>
                    Zero credential exposure: Provider keys are strictly configured via server environment variables and never stored in the database. Mock acceptance is never reported as real delivered email.
                  </span>
                </div>
              </div>

              {error && (
                <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs flex items-center gap-2">
                  <AlertCircle className="w-4 h-4 shrink-0" />
                  <span>{error}</span>
                </div>
              )}

              {successMsg && (
                <div className="p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 shrink-0" />
                  <span>{successMsg}</span>
                </div>
              )}

              {/* Form */}
              <form onSubmit={handleSave} className="space-y-5">
                {/* Master Toggle */}
                <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800 flex items-center justify-between">
                  <div>
                    <span className="font-semibold text-sm text-slate-100 block">Enable Email Notifications</span>
                    <span className="text-xs text-slate-400">
                      Dispatches email alerts or batch digests for eligible job matches meeting your score criteria.
                    </span>
                  </div>
                  <label className="relative inline-flex items-center cursor-pointer">
                    <input
                      type="checkbox"
                      checked={prefs.email_enabled}
                      onChange={(e) => setPrefs({ ...prefs, email_enabled: e.target.checked })}
                      className="sr-only peer"
                    />
                    <div className="w-11 h-6 bg-slate-800 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-indigo-600"></div>
                  </label>
                </div>

                {/* Recipient, Delivery Mode, & Timezone */}
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                  <div>
                    <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                      Recipient Email Address
                    </label>
                    <input
                      type="email"
                      value={prefs.recipient_email || ''}
                      onChange={(e) => setPrefs({ ...prefs, recipient_email: e.target.value })}
                      placeholder="candidate@example.com"
                      disabled={!prefs.email_enabled}
                      className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500 disabled:opacity-50"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                      Delivery Mode
                    </label>
                    <select
                      value={prefs.delivery_mode}
                      onChange={(e) =>
                        setPrefs({ ...prefs, delivery_mode: e.target.value as DeliveryMode })
                      }
                      disabled={!prefs.email_enabled}
                      className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-slate-100 focus:outline-none focus:border-indigo-500 disabled:opacity-50"
                    >
                      <option value="IMMEDIATE">Immediate (Real-Time Alert)</option>
                      <option value="DAILY_DIGEST">Daily Digest (09:00 AM)</option>
                      <option value="WEEKLY_DIGEST">Weekly Digest (Monday 09:00 AM)</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-300 mb-1.5 flex items-center gap-1">
                      <Globe className="w-3.5 h-3.5 text-indigo-400" />
                      <span>Preferred Timezone</span>
                    </label>
                    <select
                      value={prefs.timezone || 'UTC'}
                      onChange={(e) => setPrefs({ ...prefs, timezone: e.target.value })}
                      disabled={!prefs.email_enabled}
                      className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-slate-100 focus:outline-none focus:border-indigo-500 disabled:opacity-50"
                    >
                      {COMMON_TIMEZONES.map((tz) => (
                        <option key={tz} value={tz}>
                          {tz}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                {/* Digest Status Card (when digest selected) */}
                {prefs.email_enabled && prefs.delivery_mode !== 'IMMEDIATE' && (
                  <div className="p-4 rounded-xl bg-indigo-950/20 border border-indigo-500/30 text-xs">
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex items-center gap-2 text-indigo-300 font-semibold">
                        <Clock className="w-4 h-4" />
                        <span>Scheduled Digest Telemetry</span>
                      </div>
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        disabled={isTriggeringDigest}
                        onClick={handleTriggerDigest}
                        className="text-[11px] h-7"
                      >
                        <RefreshCw className={`w-3 h-3 mr-1 ${isTriggeringDigest ? 'animate-spin' : ''}`} />
                        <span>Trigger Digest Now</span>
                      </Button>
                    </div>

                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-slate-300">
                      <div>
                        <span className="text-slate-500 block text-[10px] uppercase">Next Scheduled Run</span>
                        <span className="font-mono font-medium text-slate-200">
                          {digestStatus?.next_digest_at
                            ? formatDate(digestStatus.next_digest_at)
                            : 'Not scheduled'}
                        </span>
                      </div>
                      <div>
                        <span className="text-slate-500 block text-[10px] uppercase">Pending Matches</span>
                        <span className="font-bold text-indigo-400">
                          {digestStatus?.pending_matches_count ?? 0} waiting
                        </span>
                      </div>
                      <div>
                        <span className="text-slate-500 block text-[10px] uppercase">Last Digest Time</span>
                        <span className="text-slate-200">
                          {digestStatus?.last_digest_at ? formatDate(digestStatus.last_digest_at) : 'None'}
                        </span>
                      </div>
                      <div>
                        <span className="text-slate-500 block text-[10px] uppercase">Last Status</span>
                        <span>
                          {digestStatus?.last_digest_status
                            ? renderStatusBadge(digestStatus.last_digest_status, false)
                            : 'N/A'}
                        </span>
                      </div>
                    </div>

                    <div className="mt-3 flex items-center justify-between text-[11px] text-slate-400 border-t border-indigo-500/20 pt-2">
                      <label className="flex items-center gap-1.5 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={forceDigest}
                          onChange={(e) => setForceDigest(e.target.checked)}
                          className="rounded bg-slate-900 border-slate-700 text-indigo-600 focus:ring-0"
                        />
                        <span>Force send digest even if no new pending matches exist</span>
                      </label>
                      {digestTriggerResult && (
                        <span className="text-indigo-300 font-medium">{digestTriggerResult}</span>
                      )}
                    </div>
                  </div>
                )}

                {/* Match Score Threshold Slider */}
                <div>
                  <div className="flex items-center justify-between mb-1.5">
                    <label className="text-xs font-semibold text-slate-300 flex items-center gap-1.5">
                      <Sliders className="w-3.5 h-3.5 text-indigo-400" />
                      <span>Minimum Match Score Threshold</span>
                    </label>
                    <span className="text-xs font-bold font-mono text-indigo-400 bg-indigo-500/10 px-2 py-0.5 rounded border border-indigo-500/20">
                      {prefs.min_match_score}%
                    </span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="100"
                    step="5"
                    value={prefs.min_match_score}
                    onChange={(e) => setPrefs({ ...prefs, min_match_score: Number(e.target.value) })}
                    className="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-indigo-500"
                  />
                  <span className="text-[11px] text-slate-500 mt-1 block">
                    Only include job opportunities whose overall match score meets or exceeds {prefs.min_match_score}%.
                  </span>
                </div>

                {/* Event Trigger Toggles */}
                <div className="pt-3 border-t border-slate-800/80">
                  <span className="block text-xs font-semibold text-slate-300 mb-3">
                    Notification Trigger Channels
                  </span>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                    <label className="flex items-center gap-2.5 text-xs text-slate-300 bg-slate-950/40 p-2.5 rounded-lg border border-slate-800/60 cursor-pointer hover:bg-slate-950">
                      <input
                        type="checkbox"
                        checked={prefs.notify_new_matches}
                        onChange={(e) => setPrefs({ ...prefs, notify_new_matches: e.target.checked })}
                        className="rounded bg-slate-900 border-slate-700 text-indigo-600 focus:ring-0"
                      />
                      <span>New Eligible Matches</span>
                    </label>

                    <label className="flex items-center gap-2.5 text-xs text-slate-300 bg-slate-950/40 p-2.5 rounded-lg border border-slate-800/60 cursor-pointer hover:bg-slate-950">
                      <input
                        type="checkbox"
                        checked={prefs.notify_workflow_blockers}
                        onChange={(e) =>
                          setPrefs({ ...prefs, notify_workflow_blockers: e.target.checked })
                        }
                        className="rounded bg-slate-900 border-slate-700 text-indigo-600 focus:ring-0"
                      />
                      <span>Application Blockers / MFA</span>
                    </label>

                    <label className="flex items-center gap-2.5 text-xs text-slate-300 bg-slate-950/40 p-2.5 rounded-lg border border-slate-800/60 cursor-pointer hover:bg-slate-950">
                      <input
                        type="checkbox"
                        checked={prefs.notify_partial_discovery}
                        onChange={(e) =>
                          setPrefs({ ...prefs, notify_partial_discovery: e.target.checked })
                        }
                        className="rounded bg-slate-900 border-slate-700 text-indigo-600 focus:ring-0"
                      />
                      <span>Partial Discovery Runs</span>
                    </label>

                    <label className="flex items-center gap-2.5 text-xs text-slate-300 bg-slate-950/40 p-2.5 rounded-lg border border-slate-800/60 cursor-pointer hover:bg-slate-950">
                      <input
                        type="checkbox"
                        checked={prefs.notify_discovery_failures}
                        onChange={(e) =>
                          setPrefs({ ...prefs, notify_discovery_failures: e.target.checked })
                        }
                        className="rounded bg-slate-900 border-slate-700 text-indigo-600 focus:ring-0"
                      />
                      <span>Discovery Run Failures</span>
                    </label>
                  </div>
                </div>

                <div className="flex justify-end pt-2">
                  <Button type="submit" variant="primary" disabled={isSaving}>
                    <Save className="w-4 h-4 mr-1.5" />
                    <span>{isSaving ? 'Saving Preferences...' : 'Save Preferences'}</span>
                  </Button>
                </div>
              </form>

              {/* Safe Test Delivery Section */}
              <div className="pt-6 border-t border-slate-800">
                <div className="flex items-center gap-2 mb-1.5">
                  <Send className="w-4 h-4 text-emerald-400" />
                  <h3 className="text-xs font-semibold text-slate-200">Safe Test Delivery Workflow</h3>
                </div>
                <p className="text-[11px] text-slate-400 mb-3">
                  Dispatch a synthetic test alert to verify template rendering and delivery pipeline. External employers are never contacted.
                </p>

                <div className="flex gap-2">
                  <input
                    type="email"
                    value={testEmailRecipient}
                    onChange={(e) => setTestEmailRecipient(e.target.value)}
                    placeholder="test_candidate@example.com"
                    className="flex-1 bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
                  />
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    disabled={isSendingTest}
                    onClick={handleSendTestEmail}
                  >
                    <Send className="w-3.5 h-3.5 mr-1" />
                    <span>{isSendingTest ? 'Sending...' : 'Send Test Alert'}</span>
                  </Button>
                </div>

                {testResult && (
                  <div
                    className={`mt-3 p-3 rounded-lg border text-xs flex items-center justify-between ${
                      testResult.success
                        ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
                        : 'bg-rose-500/10 border-rose-500/30 text-rose-300'
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      {testResult.success ? (
                        <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-400" />
                      ) : (
                        <AlertCircle className="w-4 h-4 shrink-0 text-rose-400" />
                      )}
                      <span>{testResult.message}</span>
                    </div>
                    {testResult.delivery_status && (
                      <div>{renderStatusBadge(testResult.delivery_status, false)}</div>
                    )}
                  </div>
                )}
              </div>

              {/* Recent Delivery History Section */}
              <div className="pt-6 border-t border-slate-800">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <History className="w-4 h-4 text-slate-400" />
                    <h3 className="text-xs font-semibold text-slate-200">Recent Delivery History & Status</h3>
                  </div>
                  <span className="text-[11px] text-slate-500">
                    Accurate RFC 5321 / Simulated semantics
                  </span>
                </div>

                {deliveryHistory.length === 0 ? (
                  <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 text-center text-slate-500 text-xs">
                    No email delivery attempts recorded yet.
                  </div>
                ) : (
                  <div className="rounded-xl border border-slate-800 overflow-hidden bg-slate-950/60">
                    <table className="w-full text-left text-xs">
                      <thead className="bg-slate-950 border-b border-slate-800 text-[10px] text-slate-500 uppercase tracking-wider">
                        <tr>
                          <th className="px-3 py-2">Subject / Message</th>
                          <th className="px-3 py-2">Status</th>
                          <th className="px-3 py-2">Attempts</th>
                          <th className="px-3 py-2">Recipient</th>
                          <th className="px-3 py-2">Timestamp</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-800/60 text-slate-300">
                        {deliveryHistory.map((item) => (
                          <tr key={item.id} className="hover:bg-slate-900/60">
                            <td className="px-3 py-2">
                              <span className="font-medium text-slate-200 block truncate max-w-[200px]" title={item.title}>
                                {item.title}
                              </span>
                              {item.error && (
                                <span className="text-[10px] text-rose-400 block truncate max-w-[200px]" title={item.error}>
                                  {item.error}
                                </span>
                              )}
                            </td>
                            <td className="px-3 py-2 whitespace-nowrap">
                              {renderStatusBadge(item.status, item.is_simulated)}
                            </td>
                            <td className="px-3 py-2 whitespace-nowrap text-slate-400">
                              {item.attempt_count} attempt{item.attempt_count > 1 ? 's' : ''}
                            </td>
                            <td className="px-3 py-2 font-mono text-[11px] text-slate-400 truncate max-w-[120px]">
                              {item.recipient || 'N/A'}
                            </td>
                            <td className="px-3 py-2 text-slate-400 text-[11px] whitespace-nowrap">
                              {formatDate(item.created_at)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-3.5 bg-slate-950/60 border-t border-slate-800 flex justify-end">
          <Button variant="ghost" size="sm" onClick={onClose}>
            Close
          </Button>
        </div>
      </div>
    </div>
  );
};
