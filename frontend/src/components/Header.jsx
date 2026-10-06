import React from 'react';
import { Briefcase, User, Sparkles } from 'lucide-react';

export default function Header({ portal, setPortal }) {
  return (
    <header className="glass-panel rounded-2xl p-6 border border-slate-800 space-y-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-gradient-to-tr from-sky-500 to-indigo-600 shadow-lg shadow-sky-500/20">
              <Sparkles className="w-6 h-6 text-white" />
            </div>
            <div>
              <h1 className="text-2xl font-black text-white tracking-tight bg-gradient-to-r from-white via-slate-100 to-slate-400 bg-clip-text text-transparent">
                AI Recruitment & Resume Intelligence Platform
              </h1>
              <p className="text-xs text-slate-400 font-medium mt-0.5">
                Dual-Sided Intelligence for HR Recruiters & Job Seekers
              </p>
            </div>
          </div>
        </div>

        {/* Portal Switcher */}
        <div className="flex bg-slate-900/90 p-1.5 rounded-xl border border-slate-800 self-start md:self-auto">
          <button
            onClick={() => setPortal('recruiter')}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-bold transition-all ${
              portal === 'recruiter'
                ? 'bg-gradient-to-r from-sky-500 to-blue-600 text-white shadow-md shadow-sky-500/20'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
            }`}
          >
            <Briefcase className="w-4 h-4" />
            <span>👔 Recruiter Portal</span>
          </button>
          <button
            onClick={() => setPortal('candidate')}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-bold transition-all ${
              portal === 'candidate'
                ? 'bg-gradient-to-r from-indigo-500 to-purple-600 text-white shadow-md shadow-purple-500/20'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
            }`}
          >
            <User className="w-4 h-4" />
            <span>🎯 Candidate Portal</span>
          </button>
        </div>
      </div>
    </header>
  );
}
