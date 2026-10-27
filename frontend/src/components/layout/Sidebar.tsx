import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  Briefcase,
  FileCheck2,
  FileText,
  UserCheck,
  ShieldAlert,
  Compass,
  CalendarClock,
} from 'lucide-react';

interface SidebarProps {
  onCloseMobile?: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ onCloseMobile }) => {
  const navItems = [
    { to: '/', label: 'Overview', icon: LayoutDashboard },
    { to: '/jobs', label: 'Discovered Jobs', icon: Briefcase },
    { to: '/applications', label: 'Applications & Queue', icon: FileCheck2 },
    { to: '/resumes', label: 'Resume Workspace', icon: FileText },
    { to: '/profile', label: 'Candidate Profile', icon: UserCheck },
    { to: '/scheduler', label: 'Scheduler & Discovery', icon: CalendarClock },
  ];

  return (
    <aside className="w-64 h-full flex flex-col bg-slate-900 border-r border-slate-800 select-none">
      {/* Brand Header */}
      <div className="h-16 flex items-center px-6 gap-3 border-b border-slate-800">
        <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-indigo-600 to-indigo-400 flex items-center justify-center text-white shadow-md shadow-indigo-500/20">
          <Compass className="w-5 h-5" />
        </div>
        <div>
          <span className="font-bold text-slate-100 text-base tracking-tight">JobPilot</span>
          <span className="text-indigo-400 text-xs font-semibold ml-1.5 px-1.5 py-0.5 rounded bg-indigo-500/10 border border-indigo-500/20">AI</span>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
        <div className="px-3 pb-2 text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
          Workspace
        </div>
        {navItems.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.to}
              to={item.to}
              onClick={onCloseMobile}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-indigo-600/15 text-indigo-400 border border-indigo-500/30'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
                }`
              }
            >
              <Icon className="w-4 h-4 shrink-0" />
              <span>{item.label}</span>
            </NavLink>
          );
        })}
      </nav>

      {/* Safety Notice Footer */}
      <div className="p-4 m-3 rounded-xl bg-slate-950/60 border border-slate-800 text-xs space-y-1.5">
        <div className="flex items-center gap-2 text-emerald-400 font-semibold">
          <ShieldAlert className="w-4 h-4 text-emerald-400" />
          <span>Safety Gate Active</span>
        </div>
        <p className="text-slate-400 leading-relaxed text-[11px]">
          External submissions are disabled. Browser runs execute in isolated synthetic simulation.
        </p>
      </div>
    </aside>
  );
};
