import React, { useState } from 'react';
import { Modal } from '../../components/ui/Modal';
import { Button } from '../../components/ui/Button';
import { api } from '../../lib/api-client';
import { Sparkles, CheckCircle2, AlertTriangle } from 'lucide-react';

interface JobDiscoveryModalProps {
  isOpen: boolean;
  onClose: () => void;
  onDiscoveryComplete: () => void;
}

export const JobDiscoveryModal: React.FC<JobDiscoveryModalProps> = ({
  isOpen,
  onClose,
  onDiscoveryComplete,
}) => {
  const [selectedSource, setSelectedSource] = useState<string>('synthetic');
  const [count, setCount] = useState<number>(10);
  const [isLoading, setIsLoading] = useState(false);
  const [resultMessage, setResultMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const availableSources = [
    { id: 'synthetic', label: 'Synthetic Portal (Local Test)', desc: 'Local synthetic jobs for end-to-end safe testing' },
    { id: 'remoteok', label: 'RemoteOK Adapter', desc: 'Remote developer job listings' },
    { id: 'arbeitnow', label: 'Arbeitnow Adapter', desc: 'European tech & remote job listings' },
  ];

  const handleDiscover = async () => {
    setIsLoading(true);
    setError(null);
    setResultMessage(null);

    try {
      const response = await api.jobs.discover(selectedSource, { count });

      setResultMessage(
        `Discovery completed for ${response.source_identifier}: Discovered ${response.total_discovered} jobs (${response.new_jobs_added} newly stored, ${response.duplicate_jobs_skipped} duplicates skipped).`
      );
      onDiscoveryComplete();
    } catch (err: any) {
      setError(err?.message || 'Failed to run job discovery');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Discover New Jobs"
      size="lg"
      footer={
        <div className="flex items-center justify-between w-full">
          <div className="text-xs text-slate-500">
            Local & public API discovery only. No web scraping.
          </div>
          <div className="flex items-center gap-2">
            <Button variant="ghost" onClick={onClose} disabled={isLoading}>
              Close
            </Button>
            <Button
              variant="primary"
              onClick={handleDiscover}
              isLoading={isLoading}
              icon={<Sparkles className="w-4 h-4" />}
            >
              Run Discovery
            </Button>
          </div>
        </div>
      }
    >
      <div className="space-y-4">
        {resultMessage && (
          <div className="p-3.5 rounded-lg bg-emerald-950/30 border border-emerald-900/50 flex items-start gap-2.5 text-xs text-emerald-300">
            <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
            <span>{resultMessage}</span>
          </div>
        )}

        {error && (
          <div className="p-3.5 rounded-lg bg-red-950/30 border border-red-900/50 flex items-start gap-2.5 text-xs text-red-300">
            <AlertTriangle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
            <span>{error}</span>
          </div>
        )}

        <div>
          <label className="block text-xs font-medium text-slate-300 mb-2">
            Discovery Source Adapter
          </label>
          <div className="space-y-2">
            {availableSources.map((src) => {
              const isSelected = selectedSource === src.id;
              return (
                <div
                  key={src.id}
                  onClick={() => setSelectedSource(src.id)}
                  className={`p-3 rounded-lg border cursor-pointer transition-all ${
                    isSelected
                      ? 'bg-blue-950/20 border-blue-600/50 text-slate-200'
                      : 'bg-slate-900/40 border-slate-800 text-slate-400 hover:border-slate-700'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium">{src.label}</span>
                    <input
                      type="radio"
                      name="source"
                      checked={isSelected}
                      onChange={() => setSelectedSource(src.id)}
                      className="text-blue-600 focus:ring-0"
                    />
                  </div>
                  <div className="text-xs text-slate-400 mt-0.5">{src.desc}</div>
                </div>
              );
            })}
          </div>
        </div>

        <div>
          <label className="block text-xs font-medium text-slate-300 mb-1">
            Batch Fetch Count ({count} items)
          </label>
          <input
            type="range"
            min="5"
            max="50"
            step="5"
            value={count}
            onChange={(e) => setCount(Number(e.target.value))}
            className="w-full accent-blue-500"
          />
        </div>
      </div>
    </Modal>
  );
};
