import React, { useState, useEffect } from 'react';
import axios from 'axios';
import Header from './components/Header';
import StatusBadge from './components/StatusBadge';
import SingleResumeView from './components/SingleResumeView';
import BatchProcessingView from './components/BatchProcessingView';
import CandidatePortalView from './components/CandidatePortalView';
import { Cpu, ShieldCheck, Database, FileSpreadsheet, Briefcase, User, Sparkles } from 'lucide-react';

export default function App() {
  const [portal, setPortal] = useState('recruiter'); // 'recruiter' or 'candidate'
  const [mode, setMode] = useState('batch'); // 'batch' or 'single'
  const [systemStatus, setSystemStatus] = useState(null);
  const [loadingStatus, setLoadingStatus] = useState(false);

  const fetchStatus = async () => {
    setLoadingStatus(true);
    try {
      const res = await axios.get('/api/status');
      setSystemStatus(res.data);
    } catch (err) {
      setSystemStatus({
        is_online: false,
        status_msg: 'Groq Cloud LLM API unreachable',
        target_model: 'groq/compound-mini',
        llm_provider: 'Groq Cloud API'
      });
    } finally {
      setLoadingStatus(false);
    }
  };

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 30000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="min-h-screen text-slate-100 flex flex-col bg-slate-950">
      {/* Top Navbar & Header */}
      <div className="max-w-7xl w-full mx-auto p-4 md:p-6 space-y-6">
        <Header portal={portal} setPortal={setPortal} />

        {/* Main Content Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6 items-start">
          {/* Sidebar Status & Navigation */}
          <div className="space-y-6 lg:col-span-1">
            <StatusBadge
              status={systemStatus}
              loading={loadingStatus}
              onRefresh={fetchStatus}
            />

            {/* Platform Quick Switch */}
            <div className="glass-card rounded-2xl p-5 border border-slate-800 space-y-4">
              <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-sky-400" /> Platform Mode
              </h3>
              <div className="space-y-2">
                <button
                  onClick={() => setPortal('recruiter')}
                  className={`w-full text-left p-3 rounded-xl border transition-all text-xs font-medium flex items-center gap-3 ${
                    portal === 'recruiter'
                      ? 'bg-sky-950/40 border-sky-500 text-sky-200'
                      : 'bg-slate-900/60 border-slate-800 text-slate-400 hover:text-slate-200'
                  }`}
                >
                  <Briefcase className="w-4 h-4 text-sky-400 shrink-0" />
                  <div>
                    <div className="font-bold">Recruiter Portal</div>
                    <div className="text-[10px] text-slate-400">Screening, Ranking & Pipeline</div>
                  </div>
                </button>

                <button
                  onClick={() => setPortal('candidate')}
                  className={`w-full text-left p-3 rounded-xl border transition-all text-xs font-medium flex items-center gap-3 ${
                    portal === 'candidate'
                      ? 'bg-purple-950/40 border-purple-500 text-purple-200'
                      : 'bg-slate-900/60 border-slate-800 text-slate-400 hover:text-slate-200'
                  }`}
                >
                  <User className="w-4 h-4 text-purple-400 shrink-0" />
                  <div>
                    <div className="font-bold">Candidate Portal</div>
                    <div className="text-[10px] text-slate-400">Match Score, ATS & Rewording</div>
                  </div>
                </button>
              </div>
            </div>

            {/* Recruiter Options Mode (Only if in Recruiter Portal) */}
            {portal === 'recruiter' && (
              <div className="glass-card rounded-2xl p-5 border border-slate-800 space-y-3">
                <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider">Screening Modes</h3>
                <div className="space-y-2">
                  <button
                    onClick={() => setMode('batch')}
                    className={`w-full py-2 px-3 rounded-lg text-xs font-bold transition-all text-left ${
                      mode === 'batch' ? 'bg-sky-600 text-white' : 'bg-slate-900 text-slate-400'
                    }`}
                  >
                    ⚡ Bulk Batch Screening (30+)
                  </button>
                  <button
                    onClick={() => setMode('single')}
                    className={`w-full py-2 px-3 rounded-lg text-xs font-bold transition-all text-left ${
                      mode === 'single' ? 'bg-sky-600 text-white' : 'bg-slate-900 text-slate-400'
                    }`}
                  >
                    🚀 Single Resume Screening
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Main Operating View */}
          <div className="lg:col-span-3">
            {portal === 'candidate' ? (
              <CandidatePortalView />
            ) : mode === 'single' ? (
              <SingleResumeView systemStatus={systemStatus} />
            ) : (
              <BatchProcessingView systemStatus={systemStatus} />
            )}
          </div>
        </div>
      </div>

      {/* Footer */}
      <footer className="mt-auto py-6 border-t border-slate-900 bg-slate-950 text-center text-xs text-slate-500">
        <div className="max-w-7xl mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-2">
          <span>AI Recruitment & Resume Intelligence Platform • React + FastAPI + Streamlit + Groq Cloud</span>
          <span className="font-mono text-[11px] text-slate-600">SQLite Candidate Storage</span>
        </div>
      </footer>
    </div>
  );
}
