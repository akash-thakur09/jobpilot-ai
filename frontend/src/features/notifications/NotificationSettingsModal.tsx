import React, { useState, useEffect } from 'react';
import {
  NotificationPreferences,
  NotificationPreferencesUpdate,
  EmailConfigStatus,
  DeliveryMode,
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
} from 'lucide-react';

interface NotificationSettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

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
  });

  const [emailStatus, setEmailStatus] = useState<EmailConfigStatus | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Test email state
  const [testEmailRecipient, setTestEmailRecipient] = useState('');
  const [isSendingTest, setIsSendingTest] = useState(false);
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);

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

    try {
      const [prefsData, statusData] = await Promise.all([
        api.notifications.getPreferences(),
        api.notifications.getEmailStatus(),
      ]);

      setPrefs(prefsData);
      setEmailStatus(statusData);
      if (prefsData.recipient_email) {
        setTestEmailRecipient(prefsData.recipient_email);
      }
    } catch (err: any) {
      if (err instanceof ApiError) {
        setError(err.detail);
      } else {
        setError('Failed to load notification settings.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSaving(true);
    setError(null);
    setSuccessMsg(null);

    // Validate email format if email enabled
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
    };

    try {
      const updated = await api.notifications.updatePreferences(payload);
      setPrefs(updated);
      setSuccessMsg('Notification preferences saved successfully.');
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
        });
      } else {
        setTestResult({
          success: false,
          message: res.message || 'Delivery rejected by provider.',
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

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm overflow-y-auto">
      <div className="relative w-full max-w-2xl bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl overflow-hidden my-8">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800 bg-slate-900/90">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-indigo-500/15 text-indigo-400 flex items-center justify-center border border-indigo-500/30">
              <Bell className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-base font-bold text-slate-100">Smart Alerts & Notification Delivery</h2>
              <p className="text-xs text-slate-400">
                Configure in-app notifications and optional email alerts for qualifying opportunities.
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
              <span>Loading notification preferences...</span>
            </div>
          ) : (
            <>
              {/* Email Provider Security & Status Banner */}
              <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 text-xs">
            <div className="flex items-center justify-between pb-2 border-b border-slate-800/80 mb-2.5">
              <div className="flex items-center gap-2 font-semibold text-slate-200">
                <Mail className="w-4 h-4 text-indigo-400" />
                <span>Email Provider Configuration Status</span>
              </div>
              {emailStatus?.configured ? (
                <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
                  <CheckCircle2 className="w-3 h-3" />
                  Provider Ready ({emailStatus.provider})
                </span>
              ) : (
                <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-slate-800 text-slate-400 border border-slate-700">
                  Provider Disabled / Mock
                </span>
              )}
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 text-slate-400">
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
                <span className="text-slate-500 block text-[10px] uppercase tracking-wider">Transport Security</span>
                <span className="text-slate-200 font-medium">{emailStatus?.use_tls ? 'TLS Enabled' : 'Standard'}</span>
              </div>
            </div>

            <div className="mt-3 pt-2.5 border-t border-slate-800/60 flex items-center gap-1.5 text-[11px] text-slate-500">
              <Lock className="w-3.5 h-3.5 text-indigo-400 shrink-0" />
              <span>
                Zero credential exposure: Provider keys are strictly configured via server environment variables and never stored in the database.
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
                  Receive email alerts for new eligible job matches meeting your score criteria.
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

            {/* Recipient Email & Delivery Mode */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
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
                  <option value="DAILY_DIGEST">Daily Digest (Batch Roll-up)</option>
                  <option value="WEEKLY_DIGEST">Weekly Digest (Weekly Summary)</option>
                </select>
              </div>
            </div>

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
                Only send email alerts for jobs whose overall match score meets or exceeds {prefs.min_match_score}%. In-app notifications will always record eligible jobs.
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
                className={`mt-3 p-3 rounded-lg border text-xs flex items-center gap-2 ${
                  testResult.success
                    ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
                    : 'bg-rose-500/10 border-rose-500/30 text-rose-300'
                }`}
              >
                {testResult.success ? (
                  <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-400" />
                ) : (
                  <AlertCircle className="w-4 h-4 shrink-0 text-rose-400" />
                )}
                <span>{testResult.message}</span>
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
