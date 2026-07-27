import React, { useState, useEffect, useMemo } from 'react';
import {
  ShieldAlert,
  AlertTriangle,
  Info,
  Wrench,
  RefreshCw,
  Sparkles,
  FileCode,
  Download,
  Check
} from 'lucide-react';


import { useEditor } from '../../core/editor/EditorContext';
import { useAI } from '../../core/ai/AIContext';

interface ReviewFinding {
  id: string;
  file: string;
  category: string;
  severity: 'critical' | 'warning' | 'info';
  title: string;
  description: string;
  suggestion: string;
  auto_fixable: boolean;
  line?: number;
}

interface ReviewReport {
  score: number;
  files_scanned: number;
  summary: {
    critical: number;
    warning: number;
    info: number;
    total_issues: number;
  };
  findings: ReviewFinding[];
}

export const WorkspaceReviewPanel: React.FC = () => {
  const [report, setReport] = useState<ReviewReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [fixingId, setFixingId] = useState<string | null>(null);
  const [filterSeverity, setFilterSeverity] = useState<'all' | 'critical' | 'warning' | 'info'>('all');
  const [filterCategory, setFilterCategory] = useState<string>('all');
  const [copiedReport, setCopiedReport] = useState(false);

  const { handleSelectFile } = useEditor();
  const { handleSendMessage } = useAI();

  const runScan = async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/review/scan', {
        method: 'POST',
        headers: { Authorization: `Bearer ${localStorage.getItem('session_token') || ''}` }
      });
      if (res.ok) {
        const json = await res.json();
        setReport(json);
      }
    } catch (e) {
      console.error('Failed to run code review scan:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    runScan();
  }, []);

  const handleFix = async (finding: ReviewFinding) => {
    setFixingId(finding.id);
    try {
      const res = await fetch('/api/review/fix', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${localStorage.getItem('session_token') || ''}`
        },
        body: JSON.stringify({ finding_id: finding.id, file_path: finding.file })
      });
      if (res.ok) {
        await runScan();
      }
    } catch (e) {
      console.error('Failed to auto-fix finding:', e);
    } finally {
      setFixingId(null);
    }
  };

  const handleAiFixAll = () => {
    if (!report) return;
    const prompt = `Fix all static review issues identified in our workspace:\n${report.findings.map(f => `- ${f.file}: ${f.title} (${f.description})`).join('\n')}`;
    handleSendMessage(prompt, 'Agent', true);
  };

  const handleExportMarkdown = () => {
    if (!report) return;
    const md = `# Workspace Code Quality & Security Audit Report\n\n- **Health Score**: ${report.score}/100\n- **Files Scanned**: ${report.files_scanned}\n- **Total Issues**: ${report.summary.total_issues}\n\n## Findings\n${report.findings.map(f => `### [${f.severity.toUpperCase()}] ${f.title}\n- **File**: \`${f.file}\`\n- **Category**: ${f.category}\n- **Description**: ${f.description}\n- **Suggestion**: ${f.suggestion}\n`).join('\n')}`;
    
    navigator.clipboard.writeText(md);
    setCopiedReport(true);
    setTimeout(() => setCopiedReport(false), 2000);
  };

  const categories = useMemo(() => {
    if (!report) return ['all'];
    const set = new Set(report.findings.map(f => f.category));
    return ['all', ...Array.from(set)];
  }, [report]);

  const filteredFindings = useMemo(() => {
    if (!report) return [];
    return report.findings.filter(f => {
      const matchesSev = filterSeverity === 'all' || f.severity === filterSeverity;
      const matchesCat = filterCategory === 'all' || f.category === filterCategory;
      return matchesSev && matchesCat;
    });
  }, [report, filterSeverity, filterCategory]);

  const scoreColor = (s: number) =>
    s >= 90 ? 'text-emerald-400' : s >= 75 ? 'text-amber-400' : 'text-red-400';

  return (
    <div className="h-full flex flex-col bg-[#0d0e15] text-xs font-sans overflow-hidden border border-white/10 rounded-xl p-3 space-y-3">
      {/* ── Header ── */}
      <div className="flex items-center justify-between pb-2 border-b border-white/5">
        <div className="flex items-center gap-2">
          <ShieldAlert className="w-4 h-4 text-violet-400" />
          <div>
            <h4 className="font-bold text-white text-xs">AI Code Review & Security Audit</h4>
            <p className="text-[10px] text-gray-400">
              {report?.files_scanned || 0} files scanned · {report?.summary.total_issues || 0} issues detected
            </p>
          </div>
        </div>

        <div className="flex items-center gap-1.5">
          <button
            onClick={handleExportMarkdown}
            disabled={!report}
            className="flex items-center gap-1 text-[11px] font-semibold text-zinc-200 bg-white/5 hover:bg-white/10 border border-white/10 px-2.5 py-1 rounded-lg transition-colors cursor-pointer disabled:opacity-50"
            title="Export Audit Report as Markdown"
          >
            {copiedReport ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Download className="w-3.5 h-3.5 text-cyan-400" />}
            <span>{copiedReport ? 'Copied' : 'Export'}</span>
          </button>

          <button
            onClick={handleAiFixAll}
            disabled={!report || report.findings.length === 0}
            className="flex items-center gap-1 text-[11px] font-bold text-white bg-emerald-600 hover:bg-emerald-500 px-2.5 py-1 rounded-lg transition-colors cursor-pointer disabled:opacity-50"
          >
            <Sparkles className="w-3.5 h-3.5 fill-current" /> Auto-Fix All
          </button>

          <button
            onClick={runScan}
            disabled={loading}
            className="p-1.5 text-gray-400 hover:text-white bg-white/5 border border-white/10 rounded-lg transition-colors cursor-pointer disabled:opacity-40"
            title="Re-scan workspace"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* ── Score Dashboard ── */}
      <div className="grid grid-cols-4 gap-2 text-[11px]">
        <div className="bg-black/30 border border-white/5 p-2 rounded-lg flex items-center justify-between">
          <div>
            <div className="text-[9px] text-gray-500 uppercase font-semibold">Health Score</div>
            <div className={`font-mono text-lg font-black ${scoreColor(report?.score || 100)}`}>
              {report?.score || 100} / 100
            </div>
          </div>
        </div>

        <div
          onClick={() => setFilterSeverity(filterSeverity === 'critical' ? 'all' : 'critical')}
          className={`bg-black/30 border p-2 rounded-lg cursor-pointer transition-colors ${
            filterSeverity === 'critical' ? 'border-red-500/50 bg-red-500/10' : 'border-white/5'
          }`}
        >
          <div className="text-[9px] text-red-400 uppercase font-semibold">Critical</div>
          <div className="font-mono text-base font-bold text-white">{report?.summary.critical || 0}</div>
        </div>

        <div
          onClick={() => setFilterSeverity(filterSeverity === 'warning' ? 'all' : 'warning')}
          className={`bg-black/30 border p-2 rounded-lg cursor-pointer transition-colors ${
            filterSeverity === 'warning' ? 'border-amber-500/50 bg-amber-500/10' : 'border-white/5'
          }`}
        >
          <div className="text-[9px] text-amber-400 uppercase font-semibold">Warning</div>
          <div className="font-mono text-base font-bold text-white">{report?.summary.warning || 0}</div>
        </div>

        <div
          onClick={() => setFilterSeverity(filterSeverity === 'info' ? 'all' : 'info')}
          className={`bg-black/30 border p-2 rounded-lg cursor-pointer transition-colors ${
            filterSeverity === 'info' ? 'border-blue-500/50 bg-blue-500/10' : 'border-white/5'
          }`}
        >
          <div className="text-[9px] text-blue-400 uppercase font-semibold">Info</div>
          <div className="font-mono text-base font-bold text-white">{report?.summary.info || 0}</div>
        </div>
      </div>

      {/* ── Category Filter Pills ── */}
      {categories.length > 1 && (
        <div className="flex items-center gap-1 overflow-x-auto pb-1 scrollbar-none">
          {categories.map(cat => (
            <button
              key={cat}
              onClick={() => setFilterCategory(cat)}
              className={`px-2 py-0.5 rounded text-[10px] font-mono capitalize transition-colors cursor-pointer shrink-0 ${
                filterCategory === cat
                  ? 'bg-violet-600/30 text-violet-300 border border-violet-500/40 font-bold'
                  : 'bg-black/30 text-zinc-400 border border-white/5 hover:text-white'
              }`}
            >
              {cat}
            </button>
          ))}
        </div>
      )}

      {/* ── Findings List ── */}
      <div className="flex-1 overflow-y-auto space-y-2 pr-1 scrollbar-none">
        {loading ? (
          <div className="flex items-center justify-center py-12 text-xs text-gray-500 gap-2">
            <RefreshCw className="w-4 h-4 animate-spin text-violet-400" /> Scanning workspace codebase...
          </div>
        ) : filteredFindings.length === 0 ? (
          <div className="text-center py-12 text-xs text-gray-500 italic">
            No issues found matching your filter criteria. Codebase is clean! 🎉
          </div>
        ) : (
          filteredFindings.map((f) => (
            <div
              key={f.id}
              className="p-3 rounded-xl bg-black/40 border border-white/5 hover:border-white/15 transition-all space-y-1.5"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  {f.severity === 'critical' && <ShieldAlert className="w-4 h-4 text-red-400 shrink-0" />}
                  {f.severity === 'warning' && <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />}
                  {f.severity === 'info' && <Info className="w-4 h-4 text-blue-400 shrink-0" />}
                  
                  <span className="font-bold text-white text-xs">{f.title}</span>
                  <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-white/5 text-gray-400 border border-white/5">
                    {f.category}
                  </span>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handleSelectFile(f.file)}
                    className="text-[10px] text-gray-400 hover:text-white flex items-center gap-1 font-mono cursor-pointer truncate max-w-[160px]"
                  >
                    <FileCode className="w-3 h-3 text-gray-500 shrink-0" />
                    {f.file.split(/[\\/]/).pop()}
                  </button>

                  {f.auto_fixable && (
                    <button
                      onClick={() => handleFix(f)}
                      disabled={fixingId === f.id}
                      className="flex items-center gap-1 text-[10px] font-semibold text-emerald-300 bg-emerald-500/15 hover:bg-emerald-500/25 border border-emerald-500/30 px-2 py-0.5 rounded transition-colors cursor-pointer disabled:opacity-40"
                    >
                      <Wrench className={`w-3 h-3 ${fixingId === f.id ? 'animate-spin' : ''}`} />
                      Fix
                    </button>
                  )}
                </div>
              </div>

              <p className="text-[11px] text-gray-300 leading-relaxed">{f.description}</p>
              <div className="text-[10px] text-violet-300 font-mono bg-violet-500/10 p-1.5 rounded border border-violet-500/20">
                💡 {f.suggestion}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};

