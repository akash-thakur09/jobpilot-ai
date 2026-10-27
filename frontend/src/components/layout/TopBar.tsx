import React, { useEffect, useState } from 'react';
import { Menu, Wifi, WifiOff, ShieldCheck } from 'lucide-react';
import { api } from '../../lib/api-client';

interface TopBarProps {
  title: string;
  onOpenMobileMenu: () => void;
}

export const TopBar: React.FC<TopBarProps> = ({ title, onOpenMobileMenu }) => {
  const [isBackendConnected, setIsBackendConnected] = useState<boolean | null>(null);

  useEffect(() => {
    let isMounted = true;
    const checkConnection = async () => {
      try {
        await api.health.check();
        if (isMounted) setIsBackendConnected(true);
      } catch {
        if (isMounted) setIsBackendConnected(false);
      }
    };

    checkConnection();
    const interval = setInterval(checkConnection, 15000);
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, []);

  return (
    <header className="h-16 bg-slate-900/60 backdrop-blur-md border-b border-slate-800 px-6 flex items-center justify-between shrink-0">
      <div className="flex items-center gap-4">
        <button
          type="button"
          onClick={onOpenMobileMenu}
          className="md:hidden p-2 text-slate-400 hover:text-slate-200 rounded-lg hover:bg-slate-800 focus:outline-none"
          aria-label="Open navigation menu"
        >
          <Menu className="w-5 h-5" />
        </button>
        <h1 className="text-lg font-semibold text-slate-100 tracking-tight">{title}</h1>
      </div>

      <div className="flex items-center gap-3">
        {/* Synthetic Mode Indicator */}
        <div className="hidden sm:flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-indigo-500/10 text-indigo-300 border border-indigo-500/20">
          <ShieldCheck className="w-3.5 h-3.5 text-indigo-400" />
          <span>Local Synthetic Mode</span>
        </div>

        {/* Backend Connectivity Status */}
        <div
          className={`flex items-center gap-2 px-3 py-1 rounded-full text-xs font-medium border ${
            isBackendConnected === true
              ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
              : isBackendConnected === false
              ? 'bg-rose-500/10 text-rose-400 border-rose-500/20'
              : 'bg-slate-800 text-slate-400 border-slate-700'
          }`}
          title={
            isBackendConnected === true
              ? 'FastAPI Backend Connected'
              : 'Backend Disconnected'
          }
        >
          {isBackendConnected === true ? (
            <>
              <Wifi className="w-3.5 h-3.5 text-emerald-400 animate-pulse" />
              <span>Backend Online</span>
            </>
          ) : isBackendConnected === false ? (
            <>
              <WifiOff className="w-3.5 h-3.5 text-rose-400" />
              <span>Backend Offline</span>
            </>
          ) : (
            <>
              <span className="w-2 h-2 rounded-full bg-slate-500 animate-ping" />
              <span>Connecting...</span>
            </>
          )}
        </div>
      </div>
    </header>
  );
};
