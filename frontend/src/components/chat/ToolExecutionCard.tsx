import React, { useState } from 'react';
import {
  Terminal, FileText, FileCode, GitBranch, Search, Globe,
  CheckCircle2, XCircle, Clock, ChevronDown, ChevronRight,
  RotateCcw, HelpCircle, Zap, Database, Code2
} from 'lucide-react';
import type { ToolExecutionItem } from '../../types/chat';

interface ToolExecutionCardProps {
  toolItem: ToolExecutionItem;
  onExplain?: (tool: ToolExecutionItem) => void;
  onRetry?: (tool: ToolExecutionItem) => void;
}

// ── Tool icon registry ──────────────────────────────────────────────
function getToolIcon(tool: string) {
  switch (tool) {
    case 'terminal': return <Terminal className="w-3.5 h-3.5" style={{ color: '#22c55e' }} />;
    case 'file_read': return <FileText className="w-3.5 h-3.5" style={{ color: '#4f8cff' }} />;
    case 'file_edit': case 'file_write': return <FileCode className="w-3.5 h-3.5" style={{ color: '#a78bfa' }} />;
    case 'git': return <GitBranch className="w-3.5 h-3.5" style={{ color: '#fb923c' }} />;
    case 'search': case 'grep': return <Search className="w-3.5 h-3.5" style={{ color: '#38bdf8' }} />;
    case 'web': case 'fetch': return <Globe className="w-3.5 h-3.5" style={{ color: '#34d399' }} />;
    case 'sql': case 'database': return <Database className="w-3.5 h-3.5" style={{ color: '#f59e0b' }} />;
    case 'code': case 'run': return <Code2 className="w-3.5 h-3.5" style={{ color: '#c084fc' }} />;
    default: return <Zap className="w-3.5 h-3.5" style={{ color: '#757c87' }} />;
  }
}

// ── Tool icon container background ─────────────────────────────────
function getToolIconBg(tool: string): string {
  switch (tool) {
    case 'terminal': return 'rgba(34,197,94,0.1)';
    case 'file_read': return 'rgba(79,140,255,0.1)';
    case 'file_edit': case 'file_write': return 'rgba(167,139,250,0.1)';
    case 'git': return 'rgba(251,146,60,0.1)';
    case 'search': case 'grep': return 'rgba(56,189,248,0.1)';
    case 'web': case 'fetch': return 'rgba(52,211,153,0.1)';
    case 'sql': case 'database': return 'rgba(245,158,11,0.1)';
    default: return 'rgba(255,255,255,0.06)';
  }
}

// ── Status badge ────────────────────────────────────────────────────
const StatusBadge: React.FC<{ status?: string; durationMs?: number }> = ({ status, durationMs }) => {
  const secs = durationMs ? (durationMs / 1000).toFixed(1) : null;

  if (status === 'running') return (
    <span
      className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium animate-pulse"
      style={{ background: 'rgba(245,158,11,0.1)', color: '#f59e0b', border: '1px solid rgba(245,158,11,0.2)' }}
    >
      <span className="w-1.5 h-1.5 rounded-full bg-[#f59e0b] animate-ping" />
      Running...
    </span>
  );

  if (status === 'success') return (
    <span
      className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium"
      style={{ background: 'rgba(34,197,94,0.08)', color: '#22c55e', border: '1px solid rgba(34,197,94,0.15)' }}
    >
      <CheckCircle2 className="w-3 h-3" />
      {secs ? `Done in ${secs}s` : 'Completed'}
    </span>
  );

  if (status === 'error') return (
    <span
      className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium"
      style={{ background: 'rgba(239,68,68,0.08)', color: '#ef4444', border: '1px solid rgba(239,68,68,0.15)' }}
    >
      <XCircle className="w-3 h-3" />
      Failed
    </span>
  );

  return (
    <span
      className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium"
      style={{ background: 'rgba(255,255,255,0.05)', color: '#757c87', border: '1px solid rgba(255,255,255,0.07)' }}
    >
      <Clock className="w-3 h-3" />
      Pending
    </span>
  );
};

export const ToolExecutionCard: React.FC<ToolExecutionCardProps> = ({ toolItem, onExplain, onRetry }) => {
  const [expanded, setExpanded] = useState(false);

  const isRunning = toolItem.status === 'running';

  return (
    <div
      className="rounded-2xl overflow-hidden transition-all duration-200 my-2"
      style={{
        background: '#0f1117',
        border: isRunning
          ? '1px solid rgba(245,158,11,0.25)'
          : '1px solid rgba(255,255,255,0.05)',
        boxShadow: isRunning
          ? '0 0 0 1px rgba(245,158,11,0.06), 0 4px 16px rgba(0,0,0,0.3)'
          : '0 4px 16px rgba(0,0,0,0.25)',
      }}
    >
      {/* Running accent line */}
      {isRunning && (
        <div
          className="h-[2px] w-full"
          style={{ background: 'linear-gradient(90deg, #f59e0b 0%, transparent 100%)', animation: 'shimmer 1.5s ease-in-out infinite' }}
        />
      )}

      {/* Card Header */}
      <div
        role="button"
        tabIndex={0}
        onClick={() => setExpanded(!expanded)}
        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') setExpanded(!expanded); }}
        className="flex items-center justify-between px-4 py-3 cursor-pointer select-none transition-colors duration-150"
        style={{ background: expanded ? 'rgba(255,255,255,0.015)' : 'transparent' }}
      >
        <div className="flex items-center gap-3 min-w-0">
          {/* Tool Icon */}
          <div
            className="w-8 h-8 rounded-xl flex items-center justify-center shrink-0"
            style={{ background: getToolIconBg(toolItem.tool || '') }}
          >
            {getToolIcon(toolItem.tool || '')}
          </div>

          {/* Tool Name & Summary */}
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <span className="text-[13px] font-semibold" style={{ color: '#e2e7ef', fontFamily: 'Inter, sans-serif' }}>
                {toolItem.name}
              </span>
              {toolItem.durationMs && toolItem.status !== 'running' && (
                <span className="text-[10px] font-mono" style={{ color: '#757c87' }}>
                  {(toolItem.durationMs / 1000).toFixed(2)}s
                </span>
              )}
            </div>
            {toolItem.params && (
              <p
                className="text-[11px] truncate max-w-xs mt-0.5 font-mono"
                style={{ color: '#757c87' }}
              >
                {JSON.stringify(toolItem.params).replace(/["{}\[\]]/g, '').slice(0, 80)}
              </p>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2.5 shrink-0">
          <StatusBadge status={toolItem.status} durationMs={toolItem.durationMs} />
          <span style={{ color: '#757c87' }}>
            {expanded
              ? <ChevronDown className="w-4 h-4" />
              : <ChevronRight className="w-4 h-4" />
            }
          </span>
        </div>
      </div>

      {/* Running progress shimmer */}
      {isRunning && (
        <div className="px-4 pb-3">
          <div className="h-1 rounded-full overflow-hidden" style={{ background: 'rgba(255,255,255,0.04)' }}>
            <div
              className="h-full rounded-full"
              style={{
                background: 'linear-gradient(90deg, transparent 0%, #f59e0b 50%, transparent 100%)',
                backgroundSize: '200% 100%',
                animation: 'shimmer-bar 1.4s ease-in-out infinite',
                width: '100%',
              }}
            />
          </div>
        </div>
      )}

      {/* Expanded Details */}
      {expanded && (
        <div
          className="px-4 pb-4 space-y-3"
          style={{ borderTop: '1px solid rgba(255,255,255,0.04)' }}
        >
          {/* Parameters */}
          {toolItem.params && (
            <div className="pt-3">
              <p className="text-[10px] font-bold uppercase tracking-widest mb-2" style={{ color: '#757c87', fontFamily: 'Inter, sans-serif' }}>
                Parameters
              </p>
              <pre
                className="text-[11px] leading-relaxed overflow-x-auto rounded-xl p-3"
                style={{
                  background: 'rgba(0,0,0,0.35)',
                  color: '#aeb6c2',
                  fontFamily: "'JetBrains Mono', monospace",
                  border: '1px solid rgba(255,255,255,0.04)',
                }}
              >
                {JSON.stringify(toolItem.params, null, 2)}
              </pre>
            </div>
          )}

          {/* Output */}
          {toolItem.output && (
            <div>
              <p className="text-[10px] font-bold uppercase tracking-widest mb-2" style={{ color: '#757c87', fontFamily: 'Inter, sans-serif' }}>
                Output
              </p>
              <pre
                className="text-[11px] leading-relaxed overflow-x-auto max-h-44 overflow-y-auto rounded-xl p-3 whitespace-pre-wrap select-text"
                style={{
                  background: 'rgba(0,0,0,0.35)',
                  color: '#22c55e',
                  fontFamily: "'JetBrains Mono', monospace",
                  border: '1px solid rgba(34,197,94,0.08)',
                  scrollbarWidth: 'thin',
                  scrollbarColor: 'rgba(255,255,255,0.08) transparent',
                }}
              >
                {toolItem.output}
              </pre>
            </div>
          )}

          {/* Action Bar */}
          {(onExplain || onRetry) && (
            <div className="flex items-center justify-end gap-2 pt-1" style={{ borderTop: '1px solid rgba(255,255,255,0.04)' }}>
              {onExplain && (
                <button
                  onClick={() => onExplain(toolItem)}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-[11px] font-medium transition-all duration-150 cursor-pointer hover:scale-[1.03]"
                  style={{ background: 'rgba(79,140,255,0.08)', color: '#4f8cff', border: '1px solid rgba(79,140,255,0.12)', fontFamily: 'Inter, sans-serif' }}
                >
                  <HelpCircle className="w-3 h-3" /> Explain
                </button>
              )}
              {onRetry && (
                <button
                  onClick={() => onRetry(toolItem)}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-[11px] font-medium transition-all duration-150 cursor-pointer hover:scale-[1.03]"
                  style={{ background: 'rgba(245,158,11,0.08)', color: '#f59e0b', border: '1px solid rgba(245,158,11,0.12)', fontFamily: 'Inter, sans-serif' }}
                >
                  <RotateCcw className="w-3 h-3" /> Retry
                </button>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
