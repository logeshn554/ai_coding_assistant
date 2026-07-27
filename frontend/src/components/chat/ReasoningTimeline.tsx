/**
 * ReasoningTimeline.tsx
 *
 * Compact, streaming IDE-style activity log for AI reasoning steps.
 * Replaces large ToolCallView / ToolExecutionCard blocks with a minimal
 * chronological timeline that collapses when reasoning is complete.
 *
 * Design: dark developer-first — inspired by Cursor, Claude Code, Linear.
 */
import React, { useState, useRef, useEffect } from 'react';
import { ChevronDown, ChevronRight, Loader2 } from 'lucide-react';
import type { ToolExecutionItem, ChatMessage } from '../../types/chat';

// ── Types ─────────────────────────────────────────────────────────────────────

export interface TimelineRow {
  id: string;
  iconEmoji: string;
  action: string;
  target: string;
  meta?: string;
  tool: ToolExecutionItem['tool'] | 'other';
  status: 'running' | 'success' | 'error';
  startedAt: number;
  durationMs?: number;
  params?: Record<string, any>;
  output?: string;
}

interface ReasoningTimelineProps {
  rows: TimelineRow[];
  isGenerating: boolean;
  elapsedMs?: number;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function getDomain(urlStr: string): string {
  try {
    const clean = urlStr.replace(/^(https?:\/\/)?(www\.)?/, '');
    const parts = clean.split('/');
    return parts[0];
  } catch {
    return urlStr;
  }
}

function getFilename(pathStr: string): string {
  if (!pathStr) return '';
  const parts = pathStr.split(/[/\\]/);
  return parts[parts.length - 1] || pathStr;
}

function formatDuration(ms: number): string {
  return ms < 1000 ? `${ms}ms` : `${(ms / 1000).toFixed(1)}s`;
}

// ── Event Formatter mapping ───────────────────────────────────────────────────

export function parseToolEvent(
  name: string,
  tool: string,
  params: Record<string, any> | string,
  output?: string,
  status: string = 'success'
): {
  iconEmoji: string;
  action: string;
  target: string;
  meta?: string;
  toolType: string;
} {
  const n = (name || '').toLowerCase();
  const t = (tool || '').toLowerCase();

  let p: Record<string, any> = {};
  if (typeof params === 'object' && params !== null) {
    p = params;
  } else if (typeof params === 'string') {
    try {
      p = JSON.parse(params);
    } catch {
      if (t === 'terminal' || n === 'run_terminal') {
        p = { command: params };
      } else if (t === 'file_read' || t === 'file_edit' || t === 'file_write') {
        p = { path: params };
      } else if (t === 'search') {
        p = { query: params };
      } else {
        p = { raw: params };
      }
    }
  }

  // Default values
  let iconEmoji = '⚡';
  let action = 'Executed';
  let target = n || 'action';
  let meta: string | undefined = undefined;
  let toolType = 'other';

  // 1. File operations
  if (n === 'read_file' || t === 'file_read') {
    iconEmoji = '📄';
    action = 'Read';
    const rawPath = p.path || p.file || p.filename || p.raw || 'file';
    target = getFilename(rawPath);
    toolType = 'file_read';
  } else if (n === 'write_file' || t === 'file_write') {
    iconEmoji = '✏️';
    action = 'Updated';
    const rawPath = p.path || p.file || p.filename || p.raw || 'file';
    target = getFilename(rawPath);
    toolType = 'file_write';
  } else if (n === 'edit_file' || t === 'file_edit') {
    iconEmoji = '✏️';
    action = 'Edited';
    const rawPath = p.path || p.file || p.filename || p.raw || 'file';
    target = getFilename(rawPath);
    toolType = 'file_edit';
  } else if (n === 'create_file') {
    iconEmoji = '➕';
    action = 'Created';
    const rawPath = p.path || p.file || p.filename || p.raw || 'file';
    target = getFilename(rawPath);
    toolType = 'file_edit';
  } else if (n === 'delete_file') {
    iconEmoji = '🗑';
    action = 'Deleted';
    const rawPath = p.path || p.file || p.filename || p.raw || 'file';
    target = getFilename(rawPath);
    toolType = 'file_edit';
  } else if (n === 'rename_file') {
    iconEmoji = '🔄';
    action = 'Renamed';
    const oldName = p.old || p.source || '';
    const newName = p.new || p.dest || p.target || '';
    target = oldName && newName ? `${getFilename(oldName)} → ${getFilename(newName)}` : 'file';
    toolType = 'file_edit';
  } else if (n === 'copy_file') {
    iconEmoji = '📋';
    action = 'Copied';
    const rawPath = p.path || p.file || p.filename || p.raw || 'file';
    target = getFilename(rawPath);
    toolType = 'file_edit';
  }
  // 2. Directory operations
  else if (n === 'list_directory' || n === 'list_dir') {
    iconEmoji = '📁';
    action = 'Explored';
    const rawPath = p.path || p.DirectoryPath || p.raw || 'directory';
    target = getFilename(rawPath);
    toolType = 'file_read';
  } else if (n === 'create_directory') {
    iconEmoji = '📁';
    action = 'Created';
    const rawPath = p.path || p.raw || 'directory';
    target = getFilename(rawPath);
    toolType = 'file_edit';
  } else if (n === 'delete_directory') {
    iconEmoji = '🗑';
    action = 'Removed';
    const rawPath = p.path || p.raw || 'directory';
    target = getFilename(rawPath);
    toolType = 'file_edit';
  }
  // 3. Search operations
  else if (n === 'search') {
    iconEmoji = '🔍';
    action = 'Searched';
    target = p.query || p.raw || 'query';
    target = `"${target}"`;
    toolType = 'search';
  } else if (n === 'grep' || n === 'grep_search') {
    iconEmoji = '🔎';
    action = 'Found';
    target = p.pattern || p.query || p.raw || 'pattern';
    target = `"${target}"`;
    toolType = 'search';
  } else if (n === 'find_file') {
    iconEmoji = '📂';
    action = 'Located';
    target = p.name || p.raw || 'filename';
    target = `"${target}"`;
    toolType = 'search';
  }
  // 4. Terminal operations
  else if (n === 'run_terminal' || t === 'terminal' || n === 'run_command') {
    const cmd = (p.command || p.cmd || p.CommandLine || p.raw || '').trim();
    toolType = 'terminal';
    if (cmd.includes('npm install') || cmd.includes('yarn install') || cmd.includes('pnpm install')) {
      iconEmoji = '📦';
      action = 'Installed';
      target = 'dependencies';
    } else if (cmd.includes('npm run dev') || cmd.includes('vite') || cmd.includes('yarn dev') || cmd.includes('pnpm dev')) {
      iconEmoji = '▶';
      action = 'Started';
      target = 'development server';
    } else if (cmd.includes('npm run build') || cmd.includes('tsc') || cmd.includes('vite build')) {
      iconEmoji = '🏗';
      action = 'Built';
      target = 'project';
    } else if (cmd.includes('git status')) {
      iconEmoji = '🌿';
      action = 'Checked';
      target = 'repository status';
    } else if (cmd.includes('git diff')) {
      iconEmoji = '🌿';
      action = 'Compared';
      target = 'changes';
    } else {
      iconEmoji = '⚡';
      action = 'Executed';
      target = cmd ? `"${cmd.length > 40 ? cmd.slice(0, 40) + '…' : cmd}"` : 'command';
    }
  }
  // 5. Web operations
  else if (n === 'fetch' || n === 'read_url_content') {
    iconEmoji = '🌐';
    action = 'Retrieved';
    target = p.url || p.Url || p.raw || 'domain';
    target = getDomain(target);
    toolType = 'web';
  } else if (n === 'open_url' || n === 'open_browser_url' || n === 'browser_subagent') {
    iconEmoji = '🌍';
    action = 'Opened';
    target = p.url || p.Url || p.raw || 'domain';
    target = getDomain(target);
    toolType = 'web';
  } else if (n === 'download') {
    iconEmoji = '⬇';
    action = 'Downloaded';
    target = 'resource';
    toolType = 'web';
  }
  // 6. AI operations
  else if (n === 'analyze_file') {
    iconEmoji = '🧠';
    action = 'Analyzed';
    target = p.file || p.raw || 'file';
    target = getFilename(target);
    toolType = 'other';
  } else if (n === 'plan_task') {
    iconEmoji = '📝';
    action = 'Planned';
    target = 'implementation';
    toolType = 'other';
  } else if (n === 'reason') {
    iconEmoji = '💭';
    action = 'Thinking';
    target = '';
    toolType = 'other';
  } else if (n === 'generate_code') {
    iconEmoji = '✨';
    action = 'Generated';
    target = 'code';
    toolType = 'other';
  } else if (n === 'summarize') {
    iconEmoji = '📋';
    action = 'Summarized';
    target = 'findings';
    toolType = 'other';
  }

  // Language emoji helper based on file extension
  const getLangEmoji = (filename: string) => {
    const fn = filename.toLowerCase();
    if (fn.endsWith('.py')) return '🐍';
    if (fn.endsWith('.tsx') || fn.endsWith('.jsx')) return '⚛️';
    if (fn.endsWith('.ts') || fn.endsWith('.js')) return '📘';
    if (fn.endsWith('.json') || fn.endsWith('.toml') || fn.endsWith('.yaml') || fn.endsWith('.yml')) return '⚙️';
    if (fn.endsWith('.md') || fn.endsWith('.txt')) return '📝';
    return '📄';
  };

  // Fallbacks if nothing matched but it's a known tool type
  if (action === 'Executed' && target === n) {
    if (t === 'file_read' || n.includes('view_file') || n.includes('read_file')) {
      const filename = p.path || p.AbsolutePath || p.TargetFile || 'file';
      iconEmoji = getLangEmoji(filename);
      action = 'Analyzed';
      target = getFilename(filename);
      toolType = 'file_read';
    } else if (t === 'file_write' || t === 'file_edit' || n.includes('replace_file') || n.includes('write_to_file')) {
      const filename = p.path || p.TargetFile || p.AbsolutePath || 'file';
      iconEmoji = getLangEmoji(filename);
      action = 'Edited';
      target = getFilename(filename);
      toolType = 'file_edit';
    } else if (t === 'search' || n.includes('grep_search') || n.includes('list_dir')) {
      iconEmoji = '🔍';
      action = 'Explored';
      target = p.query ? `"${p.query}"` : 'workspace';
      toolType = 'search';
    } else if (t === 'terminal' || n.includes('run_command')) {
      iconEmoji = '⚡';
      action = 'Executed';
      const cmd = p.command || p.cmd || p.CommandLine || '';
      target = cmd ? `"${cmd.length > 40 ? cmd.slice(0, 40) + '…' : cmd}"` : 'command';
      toolType = 'terminal';
    }
  }

  // Add file language emoji if target is a filename
  if (target.includes('.')) {
    iconEmoji = getLangEmoji(target);
  }

  // Line numbers meta
  if ((toolType === 'file_read' || toolType === 'file_edit' || toolType === 'file_write') && p.start_line && p.end_line) {
    meta = `#L${p.start_line}–${p.end_line}`;
  } else if ((toolType === 'file_read' || toolType === 'file_edit' || toolType === 'file_write') && p.StartLine && p.EndLine) {
    meta = `#L${p.StartLine}–${p.EndLine}`;
  }

  // Diff additions/deletions meta for file edits
  if (toolType === 'file_edit' || action === 'Edited') {
    if (p.added || p.deleted) {
      meta = `+${p.added || 0} -${p.deleted || 0}`;
    } else if (p.ReplacementContent) {
      const addLines = p.ReplacementContent.split('\n').length;
      const delLines = p.TargetContent ? p.TargetContent.split('\n').length : 0;
      meta = `+${addLines} -${delLines}`;
    } else if (p.CodeContent) {
      const addLines = p.CodeContent.split('\n').length;
      meta = `+${addLines} -0`;
    }
  }

  // Search results count meta
  if (toolType === 'search' && output && status !== 'running') {
    try {
      const parsed = JSON.parse(output);
      if (Array.isArray(parsed)) {
        meta = `${parsed.length} results`;
      } else if (parsed && typeof parsed === 'object') {
        const keys = Object.keys(parsed);
        meta = `${keys.length} results`;
      }
    } catch {
      const linesCount = Math.max(0, (output.match(/\n/g)?.length ?? 0));
      meta = `${linesCount} results`;
    }
  }

  return { iconEmoji, action, target, meta, toolType };
}


// ── Single Row Component ──────────────────────────────────────────────────────

const TimelineRowItem: React.FC<{ row: TimelineRow; index: number }> = ({ row, index }) => {
  const [expanded, setExpanded] = useState(false);
  const [hovered, setHovered] = useState(false);
  const hasDetail = Boolean(row.params && Object.keys(row.params).length > 0) || Boolean(row.output);
  const elapsed = row.durationMs ? formatDuration(row.durationMs) : null;

  return (
    <div
      style={{
        opacity: 0,
        animation: `tlRowIn 180ms ease-out ${Math.min(index * 35, 600)}ms forwards`,
      }}
    >
      <div
        role={hasDetail ? 'button' : undefined}
        tabIndex={hasDetail ? 0 : undefined}
        onClick={hasDetail ? () => setExpanded(v => !v) : undefined}
        onKeyDown={hasDetail ? (e) => { if (e.key === 'Enter' || e.key === ' ') setExpanded(v => !v); } : undefined}
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
        className="flex items-center gap-2.5 px-3 transition-colors duration-100"
        style={{
          height: '32px',
          cursor: hasDetail ? 'pointer' : 'default',
          background: hovered ? 'rgba(255,255,255,0.025)' : 'transparent',
          borderRadius: '6px',
        }}
      >
        <span className="text-[13px] shrink-0 mr-1 select-none flex items-center justify-center">
          {row.status === 'running' ? (
            <Loader2 className="w-3.5 h-3.5 animate-spin" style={{ color: '#4F8CFF' }} />
          ) : (
            row.iconEmoji || '⚡'
          )}
        </span>

        <span
          className="text-[13px] font-normal shrink-0 mr-1.5"
          style={{ color: '#9CA3AF', fontFamily: 'Inter, sans-serif' }}
        >
          {row.action}
        </span>

        <span
          className="text-[13px] font-medium truncate min-w-0"
          style={{ color: '#F3F4F6', fontFamily: 'Inter, sans-serif' }}
        >
          {row.target}
        </span>

        {row.meta && (
          <span className="text-[12px] font-mono shrink-0 ml-1.5" style={{ color: '#9CA3AF' }}>
            {row.meta}
          </span>
        )}

        <span className="flex-1" />

        <span
          className="shrink-0 text-[10px] font-mono transition-opacity duration-150"
          style={{
            color: row.status === 'error' ? '#EF4444' : '#374151',
            opacity: (hovered || expanded) ? 1 : 0,
          }}
        >
          {row.status === 'error' ? 'failed' : (elapsed ?? (row.status === 'running' ? '…' : ''))}
        </span>

        {hasDetail && (
          <span
            className="shrink-0 transition-all duration-150"
            style={{
              color: '#374151',
              opacity: (hovered || expanded) ? 1 : 0,
              transform: expanded ? 'rotate(90deg)' : 'rotate(0deg)',
              display: 'flex',
            }}
          >
            <ChevronRight className="w-3 h-3" />
          </span>
        )}
      </div>

      {expanded && hasDetail && (
        <div
          className="mx-3 mb-1.5 rounded-lg overflow-hidden"
          style={{
            background: '#0D1117',
            border: '1px solid rgba(255,255,255,0.06)',
            animation: 'tlExpandIn 150ms ease-out',
          }}
        >
          {row.params && Object.keys(row.params).length > 0 && (
            <div className="px-3 py-2 border-b border-white/5 select-text">
              <p className="text-[9px] font-bold uppercase tracking-widest mb-1.5"
                style={{ color: '#4B5563', fontFamily: 'Inter, sans-serif' }}>
                Arguments
              </p>
              {Object.entries(row.params).map(([k, v]) => (
                <div key={k} className="flex items-start gap-2 text-[11px] font-mono leading-5">
                  <span style={{ color: '#4B5563', minWidth: '60px', flexShrink: 0 }}>{k}</span>
                  <span className="break-all" style={{ color: '#9CA3AF' }}>
                    {typeof v === 'string' ? v : JSON.stringify(v)}
                  </span>
                </div>
              ))}
            </div>
          )}
          {row.output && (
            <pre
              className="px-3 py-2 text-[10.5px] font-mono whitespace-pre-wrap break-words max-h-40 overflow-y-auto select-text leading-5"
              style={{
                color: '#6EE7B7',
                scrollbarWidth: 'thin',
                scrollbarColor: 'rgba(255,255,255,0.06) transparent',
              }}
            >
              {row.output}
            </pre>
          )}
        </div>
      )}
    </div>
  );
};

// ── Running Ticker Ticker ─────────────────────────────────────────────────────

const RunningTicker: React.FC<{ rows: TimelineRow[]; elapsedMs: number }> = ({ rows, elapsedMs }) => {
  const files = new Set(
    rows.filter(r => r.tool === 'file_read' || r.tool === 'file_edit' || r.tool === 'file_write').map(r => r.target)
  ).size;
  const searches = rows.filter(r => r.tool === 'search').length;
  const parts: string[] = [];
  if (files > 0) parts.push(`Exploring ${files} file${files > 1 ? 's' : ''}`);
  if (searches > 0) parts.push(`${searches} search${searches > 1 ? 'es' : ''}`);
  if (parts.length === 0) parts.push('Thinking');
  const secs = Math.floor(elapsedMs / 1000);

  return (
    <div className="flex items-center gap-2 px-3 pb-2 pt-1">
      <Loader2 className="w-3.5 h-3.5 animate-spin shrink-0" style={{ color: '#4F8CFF' }} />
      <span className="text-[11px] font-medium" style={{ color: '#9CA3AF', fontFamily: 'Inter, sans-serif' }}>
        {parts.join(' • ')}…
      </span>
      {secs > 0 && (
        <span className="text-[10px] font-mono ml-auto" style={{ color: '#4B5563' }}>
          {secs}s
        </span>
      )}
    </div>
  );
};

// ── Collapsed Summary Component ───────────────────────────────────────────────

const CollapsedSummary: React.FC<{
  rows: TimelineRow[];
  totalMs: number;
  onExpand: () => void;
}> = ({ rows, totalMs, onExpand }) => {
  const total = rows.length;
  const filesExplored = new Set(
    rows.filter(r => r.tool === 'file_read' || r.tool === 'file_edit' || r.tool === 'file_write').map(r => r.target)
  ).size;
  const searchesCount = rows.filter(r => r.tool === 'search').length;
  const terminalCommandsCount = rows.filter(r => r.tool === 'terminal').length;
  const errors = rows.filter(r => r.status === 'error').length;
  const secs = totalMs > 0 ? (totalMs / 1000).toFixed(1) : null;
  const hasError = errors > 0;

  // Determine summary subtitle
  let summarySubtitle = '';
  if (total > 8) {
    summarySubtitle = `${total} actions across ${filesExplored} file${filesExplored !== 1 ? 's' : ''}`;
  } else {
    const parts: string[] = [];
    if (filesExplored > 0) parts.push(`Explored ${filesExplored} file${filesExplored !== 1 ? 's' : ''}`);
    if (searchesCount > 0) parts.push(`Performed ${searchesCount} search${searchesCount !== 1 ? 'es' : ''}`);
    if (terminalCommandsCount > 0) parts.push(`Executed ${terminalCommandsCount} terminal command${terminalCommandsCount !== 1 ? 's' : ''}`);
    summarySubtitle = parts.join(' • ') || `${total} actions`;
  }

  const maxVisible = 6;
  const visibleRows = rows.slice(0, maxVisible);
  const remainingCount = total - maxVisible;

  return (
    <div className="p-3 text-[13px] leading-relaxed select-none" style={{ color: '#9CA3AF', fontFamily: 'Inter, sans-serif' }}>
      {/* Title line */}
      <div className="flex items-center gap-2 font-semibold text-[13.5px]">
        {hasError ? (
          <span style={{ color: '#EF4444' }} className="font-bold">✕</span>
        ) : (
          <span style={{ color: '#22C55E' }} className="font-bold">✓</span>
        )}
        <span style={{ color: hasError ? '#EF4444' : '#F3F4F6' }}>
          Reasoning complete {secs && `• ${secs}s`}
        </span>
      </div>

      {/* Subtitle count descriptor */}
      <div className="text-[12px] text-[#9CA3AF] mt-0.5">
        {summarySubtitle}
      </div>

      {/* Recent activity list */}
      {visibleRows.length > 0 && (
        <div className="mt-3">
          <div className="text-[10px] font-semibold text-[#4B5563] uppercase tracking-wider mb-1.5">
            Recent activity
          </div>
          <div className="space-y-0.5">
            {visibleRows.map((row) => (
              <div key={row.id} className="flex items-center gap-2 px-1 rounded hover:bg-white/[0.015] transition-colors" style={{ height: '28px' }}>
                <span className="text-[13px] shrink-0">{row.iconEmoji || '⚡'}</span>
                <span className="text-[13px] font-normal text-[#9CA3AF] shrink-0 mr-0.5">{row.action}</span>
                <span className="text-[13px] font-medium text-[#F3F4F6] truncate min-w-0">{row.target}</span>
                {row.meta && (
                  <span className="text-[11px] font-mono text-[#9CA3AF] ml-1.5 shrink-0">
                    {row.meta}
                  </span>
                )}
              </div>
            ))}
          </div>
          {remainingCount > 0 && (
            <div className="text-[11.5px] text-[#4B5563] pl-6 mt-1 font-semibold">
              + {remainingCount} more actions
            </div>
          )}
        </div>
      )}

      {/* View detailed execution toggle */}
      <button
        onClick={onExpand}
        className="flex items-center gap-1.5 mt-3.5 px-2.5 py-1 rounded bg-white/4 hover:bg-white/8 transition-colors text-[11px] font-semibold text-[#4F8CFF]"
        style={{ border: 'none', cursor: 'pointer', outline: 'none' }}
      >
        <span>▼ View detailed execution</span>
      </button>
    </div>
  );
};

// ── Main Component ────────────────────────────────────────────────────────────

export const ReasoningTimeline: React.FC<ReasoningTimelineProps> = ({
  rows,
  isGenerating,
  elapsedMs = 0,
}) => {
  const [collapsed, setCollapsed] = useState(false);
  const [userExpanded, setUserExpanded] = useState(false);
  const scrollAnchorRef = useRef<HTMLDivElement>(null);

  // Collapse when generation finishes
  useEffect(() => {
    if (!isGenerating && rows.length > 0 && !userExpanded) {
      const t = setTimeout(() => setCollapsed(true), 700);
      return () => clearTimeout(t);
    }
  }, [isGenerating, rows.length, userExpanded]);

  // Reset when generation starts
  useEffect(() => {
    if (isGenerating) {
      setCollapsed(false);
      setUserExpanded(false);
    }
  }, [isGenerating]);

  // Gentle scroll-to-bottom
  useEffect(() => {
    if (isGenerating) {
      scrollAnchorRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  }, [rows.length, isGenerating]);

  if (rows.length === 0 && !isGenerating) return null;

  const totalMs = elapsedMs > 0
    ? elapsedMs
    : rows.reduce((acc, r) => acc + (r.durationMs ?? 0), 0);

  return (
    <>
      <style>{`
        @keyframes tlRowIn {
          from { opacity: 0; transform: translateY(4px); }
          to   { opacity: 1; transform: translateY(0);   }
        }
        @keyframes tlExpandIn {
          from { opacity: 0; max-height: 0;   }
          to   { opacity: 1; max-height: 500px; }
        }
      `}</style>

      <div className="w-full my-2">
        <div
          className="rounded-xl overflow-hidden"
          style={{
            background: '#161B22',
            border: '1px solid rgba(255,255,255,0.06)',
          }}
        >
          {collapsed && !isGenerating ? (
            <div className="px-1 py-0.5">
              <CollapsedSummary
                rows={rows}
                totalMs={totalMs}
                onExpand={() => { setCollapsed(false); setUserExpanded(true); }}
              />
            </div>
          ) : (
            <>
              {/* Running header ticker */}
              {isGenerating && rows.length > 0 && (
                <div style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                  <RunningTicker rows={rows} elapsedMs={elapsedMs} />
                </div>
              )}

              {/* Row list */}
              <div className="py-1.5 px-1 space-y-0.5">
                {rows.length === 0 && isGenerating ? (
                  <div className="flex items-center gap-1.5 px-3" style={{ height: '32px' }}>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" style={{ color: '#4F8CFF' }} />
                    <span className="text-[12px]" style={{ color: '#4B5563' }}>Starting…</span>
                  </div>
                ) : (
                  rows.map((row, i) => <TimelineRowItem key={row.id} row={row} index={i} />)
                )}
              </div>

              {/* Collapse button */}
              {!isGenerating && userExpanded && rows.length > 0 && (
                <div style={{ borderTop: '1px solid rgba(255,255,255,0.04)' }} className="px-1 py-0.5">
                  <button
                    onClick={() => setCollapsed(true)}
                    className="flex items-center gap-1.5 px-3 text-[11px] w-full rounded-lg transition-colors cursor-pointer"
                    style={{ background: 'transparent', color: '#374151', border: 'none', height: '28px', fontFamily: 'Inter, sans-serif', outline: 'none' }}
                    onMouseEnter={(e) => { e.currentTarget.style.background = 'rgba(255,255,255,0.025)'; }}
                    onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent'; }}
                  >
                    <ChevronDown className="w-3 h-3" />
                    Collapse execution log
                  </button>
                </div>
              )}
            </>
          )}
        </div>
        <div ref={scrollAnchorRef} />
      </div>
    </>
  );
};

// ── Conversion helpers ────────────────────────────────────────────────────────

export function toolItemsToTimelineRows(items: ToolExecutionItem[]): TimelineRow[] {
  return items.map((item) => {
    const formatted = parseToolEvent(
      item.name,
      item.tool,
      item.params || {},
      item.output,
      item.status
    );
    return {
      id: item.id,
      iconEmoji: formatted.iconEmoji,
      action: formatted.action,
      target: formatted.target,
      meta: formatted.meta,
      tool: item.tool,
      status: item.status,
      startedAt: Date.now() - (item.durationMs ?? 0),
      durationMs: item.durationMs,
      params: item.params,
      output: item.output,
    };
  });
}

export function toolMessagesToTimelineRows(messages: ChatMessage[]): TimelineRow[] {
  return messages
    .filter(m => m.role === 'tool')
    .map((m) => {
      const name = m.name || 'action';
      const contentStr = typeof m.content === 'string' ? m.content : JSON.stringify(m.content);
      const formatted = parseToolEvent(
        name,
        nameToToolType(name),
        contentStr,
        contentStr,
        m.status || 'success'
      );
      return {
        id: m.id,
        iconEmoji: formatted.iconEmoji,
        action: formatted.action,
        target: formatted.target,
        meta: formatted.meta,
        tool: formatted.toolType as ToolExecutionItem['tool'],
        status: (m.status === 'error' ? 'error' : 'success') as TimelineRow['status'],
        startedAt: Date.now(),
        output: contentStr.length > 500 ? contentStr.slice(0, 500) + '…' : contentStr,
      };
    });
}

function nameToToolType(name: string): string {
  const n = name.toLowerCase();
  if (n.includes('read'))   return 'file_read';
  if (n.includes('write') || n.includes('edit')) return 'file_edit';
  if (n.includes('search') || n.includes('grep')) return 'search';
  if (n.includes('terminal') || n.includes('command') || n.includes('bash')) return 'terminal';
  if (n.includes('git'))  return 'git';
  return 'other';
}

