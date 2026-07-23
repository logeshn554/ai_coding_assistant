import React, { useState, useEffect } from 'react';
import { GitBranch, AlertCircle, AlertTriangle, Zap, Cpu, CheckCircle2, Globe, Wifi } from 'lucide-react';
import { useWorkspace } from '../../core/workspace/WorkspaceContext';
import { useGit } from '../../core/git/GitContext';
import { useSettings } from '../../core/settings/SettingsContext';
import { useAI } from '../../core/ai/AIContext';
import { useUI } from '../../core/ui/UIContext';
import { useEditor } from '../../core/editor/EditorContext';

export const StatusBar: React.FC = () => {
  const { workspacePath } = useWorkspace();
  const { statusBarBranch, statusBarDebug } = useGit();
  const { activeProfileName } = useSettings();
  const { isGenerating, isWsConnected, isModelFallback } = useAI();
  const { activeFilePath } = useEditor();
  const { setSidebarTab, setIsSidebarOpen } = useUI();

  const [cursorInfo, setCursorInfo] = useState({ line: 1, column: 1 });
  const [diagnostics, setDiagnostics] = useState({ errors: 0, warnings: 0 });

  useEffect(() => {
    const handler = (e: CustomEvent) => {
      if (e.detail) setCursorInfo({ line: e.detail.line || 1, column: e.detail.column || 1 });
    };
    window.addEventListener('editor-cursor-change' as any, handler);
    return () => window.removeEventListener('editor-cursor-change' as any, handler);
  }, []);

  useEffect(() => {
    const handler = (e: CustomEvent) => {
      if (e.detail) setDiagnostics({ errors: e.detail.errors || 0, warnings: e.detail.warnings || 0 });
    };
    window.addEventListener('editor-diagnostics' as any, handler);
    return () => window.removeEventListener('editor-diagnostics' as any, handler);
  }, []);

  const getWorkspaceName = () => {
    if (!workspacePath) return 'No Folder';
    return workspacePath.replace(/\\/g, '/').split('/').pop() || workspacePath;
  };

  const getFileLanguage = () => {
    if (!activeFilePath) return '';
    const ext = activeFilePath.split('.').pop()?.toLowerCase();
    const map: Record<string, string> = {
      py: 'Python', ts: 'TypeScript', tsx: 'TypeScript JSX',
      js: 'JavaScript', jsx: 'JavaScript JSX', json: 'JSON',
      html: 'HTML', css: 'CSS', scss: 'SCSS', md: 'Markdown',
      yml: 'YAML', yaml: 'YAML', toml: 'TOML', sh: 'Shell',
      sql: 'SQL', rs: 'Rust', go: 'Go', java: 'Java',
      c: 'C', cpp: 'C++', rb: 'Ruby', php: 'PHP', xml: 'XML',
    };
    return ext ? (map[ext] || ext.toUpperCase()) : '';
  };

  return (
    <div
      className="h-[26px] flex items-center justify-between px-3 shrink-0 select-none font-sans z-30 text-[11px]"
      style={{
        background: 'linear-gradient(90deg, #12082e 0%, #080e20 50%, #0a0e1a 100%)',
        borderTop: '1px solid rgba(124,106,240,0.18)',
      }}
    >
      {/* ── Left ── */}
      <div className="flex items-center gap-3">

        {/* Workspace */}
        {workspacePath && (
          <div className="flex items-center gap-1.5 text-violet-300/70 hover:text-violet-200 cursor-default transition-colors" title="Workspace">
            <Globe className="w-3 h-3" />
            <span className="font-mono text-[10px]">{getWorkspaceName()}</span>
          </div>
        )}

        {/* Git Branch */}
        {workspacePath && statusBarBranch && (
          <div className="flex items-center gap-1 text-[var(--dp-text-muted)] hover:text-[var(--dp-text-secondary)] cursor-pointer transition-colors" title="Git Branch">
            <GitBranch className="w-3 h-3" />
            <span className="text-[10px] font-mono">{statusBarBranch}</span>
          </div>
        )}

        {/* Diagnostics */}
        <div className="flex items-center gap-2">
          <div
            className={`flex items-center gap-0.5 ${diagnostics.errors > 0 ? 'text-[var(--dp-error)]' : 'text-[var(--dp-text-muted)]'}`}
            title={`${diagnostics.errors} Error(s)`}
          >
            <AlertCircle className="w-3 h-3" />
            <span className="text-[10px] font-mono">{diagnostics.errors}</span>
          </div>
          <div
            className={`flex items-center gap-0.5 ${diagnostics.warnings > 0 ? 'text-[var(--dp-warning)]' : 'text-[var(--dp-text-muted)]'}`}
            title={`${diagnostics.warnings} Warning(s)`}
          >
            <AlertTriangle className="w-3 h-3" />
            <span className="text-[10px] font-mono">{diagnostics.warnings}</span>
          </div>
        </div>

        {/* Run status */}
        {statusBarDebug === 'Running' && (
          <div className="flex items-center gap-1 text-[var(--dp-success)]">
            <CheckCircle2 className="w-3 h-3" />
            <span className="text-[10px] font-semibold">Running</span>
          </div>
        )}
      </div>

      {/* ── Right ── */}
      <div className="flex items-center gap-3">

        {/* WS disconnected */}
        {!isWsConnected && (
          <div className="flex items-center gap-1 text-[var(--dp-error)] animate-pulse" title="Disconnected">
            <AlertCircle className="w-3 h-3" />
            <span className="text-[10px] font-semibold">Disconnected</span>
          </div>
        )}

        {/* Model fallback */}
        {isModelFallback && (
          <div className="flex items-center gap-1 text-[var(--dp-warning)]">
            <AlertTriangle className="w-3 h-3" />
            <span className="text-[10px] font-semibold">Fallback</span>
          </div>
        )}

        {/* AI Status */}
        {isGenerating ? (
          <div className="flex items-center gap-1.5 animate-pulse-subtle">
            <Zap className="w-3 h-3 text-[var(--dp-accent)]" />
            <span className="text-[10px] font-medium animate-shimmer">AI Generating...</span>
          </div>
        ) : (
          <div
            onClick={() => { setSidebarTab('profile'); setIsSidebarOpen(true); }}
            className="flex items-center gap-1 text-[var(--dp-text-muted)] hover:text-[var(--dp-text-secondary)] transition-colors cursor-pointer"
            title="Active Model (Click to open Developer Profile)"
          >
            <Cpu className="w-3 h-3" />
            <span className="text-[10px]">{activeProfileName || 'No Model'}</span>
          </div>
        )}

        {/* Connectivity */}
        <div className="flex items-center gap-1 text-[var(--dp-text-muted)]">
          <Wifi className="w-3 h-3 text-[var(--dp-success)]" />
        </div>

        {/* Cursor position */}
        {activeFilePath && (
          <span className="text-[10px] font-mono text-[var(--dp-text-muted)] cursor-default" title="Cursor Position">
            Ln {cursorInfo.line}, Col {cursorInfo.column}
          </span>
        )}

        {/* Language */}
        {getFileLanguage() && (
          <span className="text-[10px] font-mono text-[var(--dp-text-muted)] hover:text-[var(--dp-text-secondary)] cursor-pointer transition-colors">
            {getFileLanguage()}
          </span>
        )}

        {/* Encoding */}
        <span className="text-[10px] text-[var(--dp-text-muted)]">UTF-8</span>

        {/* Spaces */}
        <span className="text-[10px] text-[var(--dp-text-muted)]">Spaces: 2</span>
      </div>
    </div>
  );
};
