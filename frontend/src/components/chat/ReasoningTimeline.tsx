/**
 * ReasoningTimeline.tsx
 *
 * Clean, timeline-based activity log styled like ChatGPT Codex, Claude Code, and Warp Terminal.
 * Text-first, natural-language execution transcript that blends seamlessly into chat without cards or borders.
 */
import React, { useState, useEffect, useRef } from 'react';
import { ChevronRight } from 'lucide-react';
import type { ToolExecutionItem, ChatMessage } from '../../types/chat';

// ── Types ─────────────────────────────────────────────────────────────────────

export interface TimelineRow {
  id: string;
  action: string;        // Main natural language action text (e.g. "Reading project files...")
  substep?: string;       // Substep indicator (e.g. "Timed 30 seconds")
  detail?: string;        // Indented operation detail (e.g. "Check npm run build completion")
  resultText?: string;    // Result status sentence (e.g. "I am waiting for the frontend build to complete.")
  tool: string;
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

function getFilename(pathStr: string): string {
  if (!pathStr) return 'file';
  const parts = pathStr.split(/[/\\]/);
  return parts[parts.length - 1] || pathStr;
}

function formatDurationHeader(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  const totalSecs = Math.round(ms / 1000);
  if (totalSecs < 60) return `${totalSecs}s`;
  const mins = Math.floor(totalSecs / 60);
  return `${mins}m`;
}

// ── Natural Language Event Parser ─────────────────────────────────────────────

export function parseToolEvent(
  name: string,
  tool: string,
  params: Record<string, any> | string,
  _output?: string,
  _status: string = 'success'
): {
  action: string;
  substep?: string;
  detail?: string;
  resultText?: string;
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
      p = { raw: params };
    }
  }

  // 1. Schedule / Timer / Waiting
  if (n === 'schedule' || n.includes('timer') || n.includes('wait')) {
    const duration = p.DurationSeconds || p.duration_seconds || 30;
    const prompt = p.Prompt || p.prompt || 'Check task completion';
    return {
      action: "Let's schedule a wait to get the execution result.",
      substep: `Timed ${duration} seconds`,
      detail: prompt,
      resultText: "I am waiting for the operation to complete.",
      toolType: 'schedule',
    };
  }

  // 2. File Reading / Inspection
  if (t === 'file_read' || n.includes('read_file') || n.includes('view_file')) {
    const filename = getFilename(p.path || p.AbsolutePath || p.TargetFile || '');
    const startLine = p.StartLine || p.start_line;
    const endLine = p.EndLine || p.end_line;
    return {
      action: `Reading ${filename}...`,
      substep: startLine && endLine ? `Inspecting lines ${startLine}–${endLine}` : `Inspecting ${filename}`,
      detail: p.path || p.AbsolutePath,
      toolType: 'file_read',
    };
  }

  // 3. File Editing / Writing
  if (t === 'file_write' || t === 'file_edit' || n.includes('replace_file') || n.includes('write_to_file')) {
    const filename = getFilename(p.TargetFile || p.path || p.AbsolutePath || '');
    return {
      action: `Editing ${filename}...`,
      substep: p.Instruction || 'Applying code changes',
      detail: p.TargetFile || p.path,
      toolType: 'file_edit',
    };
  }

  // 4. Command Execution
  if (t === 'terminal' || n.includes('run_command') || n.includes('run_terminal')) {
    const cmd = p.CommandLine || p.command || p.cmd || '';
    const cleanCmd = cmd.length > 50 ? cmd.slice(0, 50) + '…' : cmd;
    return {
      action: cmd ? `Running ${cleanCmd}...` : 'Executing command...',
      substep: cmd ? `Command: ${cmd}` : 'Shell execution',
      detail: p.Cwd ? `CWD: ${p.Cwd}` : undefined,
      toolType: 'terminal',
    };
  }

  // 5. Codebase Search
  if (t === 'search' || n.includes('grep') || n.includes('search_codebase')) {
    const query = p.Query || p.query || p.raw || '';
    return {
      action: query ? `Searching codebase for "${query}"...` : 'Exploring codebase...',
      substep: query ? `Query: ${query}` : 'Workspace search',
      toolType: 'search',
    };
  }

  // 6. Subagent Delegation
  if (n === 'spawn_subagent') {
    const prompt = p.prompt || p.Prompt || '';
    return {
      action: 'Delegating to sub-agent...',
      substep: prompt ? `Task: ${prompt}` : 'Subtask execution',
      toolType: 'subagent',
    };
  }

  // 7. General Fallback
  return {
    action: `Processing ${n.replace(/_/g, ' ')}...`,
    substep: p.raw || (Object.keys(p).length > 0 ? JSON.stringify(p).slice(0, 60) : undefined),
    toolType: 'other',
  };
}

// ── Timeline Entry Item ───────────────────────────────────────────────────────

const TimelineEntryItem: React.FC<{
  row: TimelineRow;
  onToggleSubstep: () => void;
  isOpen: boolean;
}> = ({ row, onToggleSubstep, isOpen }) => {
  return (
    <div
      className="flex flex-col space-y-1 py-1 px-1.5 rounded transition-colors duration-180 hover:bg-white/[0.02]"
      style={{ fontFamily: 'Inter, sans-serif' }}
    >
      {/* Main Action Text (15px, #ECECEC, 1.7 line height) */}
      <div className="text-[15px] leading-[1.7]" style={{ color: '#ECECEC' }}>
        {row.action}
      </div>

      {/* Substep Accordion */}
      {row.substep && (
        <div className="flex flex-col space-y-1">
          <button
            type="button"
            onClick={onToggleSubstep}
            className="flex items-center gap-1.5 text-[14px] leading-[1.7] cursor-pointer text-left focus:outline-none transition-colors"
            style={{ color: '#A1A1AA' }}
          >
            <span>{row.substep}</span>
            <span className="text-[10px]" style={{ color: '#6B7280' }}>
              {isOpen ? '▼' : '►'}
            </span>
          </button>

          {/* Indented Substep Detail */}
          {isOpen && row.detail && (
            <div
              className="pl-5 text-[14px] leading-[1.7] font-mono transition-all duration-180 select-text"
              style={{ color: '#6B7280' }}
            >
              {row.detail}
            </div>
          )}
        </div>
      )}

      {/* Optional Result Text */}
      {row.resultText && (
        <div className="text-[15px] leading-[1.7]" style={{ color: '#ECECEC' }}>
          {row.resultText}
        </div>
      )}
    </div>
  );
};

// ── Main Component ────────────────────────────────────────────────────────────

export const ReasoningTimeline: React.FC<ReasoningTimelineProps> = ({
  rows,
  isGenerating,
  elapsedMs = 0,
}) => {
  const [isExpanded, setIsExpanded] = useState(true);
  const [openSubstepId, setOpenSubstepId] = useState<string | null>(null);
  const scrollAnchorRef = useRef<HTMLDivElement>(null);

  // Calculate total execution duration
  const totalMs = elapsedMs > 0
    ? elapsedMs
    : rows.reduce((acc, r) => acc + (r.durationMs ?? 0), 0);

  const formattedHeaderTime = formatDurationHeader(totalMs);

  // Auto-collapse previous entries when new steps arrive; expand latest step
  useEffect(() => {
    if (rows.length > 0) {
      setOpenSubstepId(rows[rows.length - 1].id);
    }
  }, [rows.length]);

  // Auto-scroll as new timeline events arrive
  useEffect(() => {
    if (isGenerating) {
      scrollAnchorRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  }, [rows.length, isGenerating]);

  if (rows.length === 0 && !isGenerating) return null;

  return (
    <div className="w-full my-3 bg-transparent text-left font-sans select-none" style={{ fontFamily: 'Inter, sans-serif' }}>
      {/* ── Header: Worked for 6m > ── */}
      <button
        type="button"
        onClick={() => setIsExpanded(!isExpanded)}
        className="flex items-center gap-1.5 py-1 text-[15px] font-medium transition-colors cursor-pointer focus:outline-none"
        style={{ color: '#C8C8C8' }}
      >
        <span>Worked for {formattedHeaderTime}</span>
        <ChevronRight
          className="w-4 h-4 transition-transform duration-180"
          style={{
            color: '#C8C8C8',
            transform: isExpanded ? 'rotate(90deg)' : 'rotate(0deg)',
          }}
        />
      </button>

      {/* ── Timeline Activity Log ── */}
      {isExpanded && (
        <div className="mt-3 flex flex-col space-y-4">
          {rows.map((row) => (
            <TimelineEntryItem
              key={row.id}
              row={row}
              isOpen={openSubstepId === row.id}
              onToggleSubstep={() => setOpenSubstepId(openSubstepId === row.id ? null : row.id)}
            />
          ))}
          {isGenerating && rows.length === 0 && (
            <div className="text-[15px] leading-[1.7] animate-pulse" style={{ color: '#A1A1AA' }}>
              Reading project files...
            </div>
          )}
          <div ref={scrollAnchorRef} />
        </div>
      )}
    </div>
  );
};

// ── Conversion helpers ────────────────────────────────────────────────────────

export function toolItemsToTimelineRows(items: ToolExecutionItem[]): TimelineRow[] {
  return items.map((item) => {
    const parsed = parseToolEvent(
      item.name,
      item.tool,
      item.params || {},
      item.output,
      item.status
    );
    return {
      id: item.id,
      action: parsed.action,
      substep: parsed.substep,
      detail: parsed.detail,
      resultText: parsed.resultText,
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
      const parsed = parseToolEvent(
        name,
        nameToToolType(name),
        contentStr,
        contentStr,
        m.status || 'success'
      );
      return {
        id: m.id,
        action: parsed.action,
        substep: parsed.substep,
        detail: parsed.detail,
        resultText: parsed.resultText,
        tool: parsed.toolType,
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
  if (n.includes('schedule') || n.includes('timer')) return 'schedule';
  return 'other';
}
