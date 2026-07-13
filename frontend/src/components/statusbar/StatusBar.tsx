import React, { useState, useEffect } from 'react';
import { GitBranch, Globe, AlertCircle, AlertTriangle, Zap, Cpu, CheckCircle2 } from 'lucide-react';
import { useWorkspace } from '../../core/workspace/WorkspaceContext';
import { useGit } from '../../core/git/GitContext';
import { useSettings } from '../../core/settings/SettingsContext';
import { useAI } from '../../core/ai/AIContext';
import { useEditor } from '../../core/editor/EditorContext';

export const StatusBar: React.FC = () => {
  const { workspacePath } = useWorkspace();
  const { statusBarBranch, statusBarDebug } = useGit();
  const { activeProfileName } = useSettings();
  const { isGenerating } = useAI();
  const { activeFilePath } = useEditor();

  const [cursorInfo, setCursorInfo] = useState({ line: 1, column: 1 });
  const [diagnostics, setDiagnostics] = useState({ errors: 0, warnings: 0 });

  // Listen for Monaco cursor position updates
  useEffect(() => {
    const handler = (e: CustomEvent) => {
      if (e.detail) {
        setCursorInfo({ line: e.detail.line || 1, column: e.detail.column || 1 });
      }
    };
    window.addEventListener('editor-cursor-change' as any, handler);
    return () => window.removeEventListener('editor-cursor-change' as any, handler);
  }, []);

  // Listen for diagnostics updates
  useEffect(() => {
    const handler = (e: CustomEvent) => {
      if (e.detail) {
        setDiagnostics({ errors: e.detail.errors || 0, warnings: e.detail.warnings || 0 });
      }
    };
    window.addEventListener('editor-diagnostics' as any, handler);
    return () => window.removeEventListener('editor-diagnostics' as any, handler);
  }, []);

  const getWorkspaceFolderBasename = () => {
    if (!workspacePath) return 'No Folder';
    const normalized = workspacePath.replace(/\\/g, '/');
    return normalized.split('/').pop() || normalized;
  };

  const getFileLanguage = () => {
    if (!activeFilePath) return '';
    const ext = activeFilePath.split('.').pop()?.toLowerCase();
    const map: Record<string, string> = {
      py: 'Python', ts: 'TypeScript', tsx: 'TypeScript React',
      js: 'JavaScript', jsx: 'JavaScript React', json: 'JSON',
      html: 'HTML', css: 'CSS', scss: 'SCSS', md: 'Markdown',
      yml: 'YAML', yaml: 'YAML', toml: 'TOML', sh: 'Shell',
      bat: 'Batch', sql: 'SQL', rs: 'Rust', go: 'Go',
      java: 'Java', c: 'C', cpp: 'C++', rb: 'Ruby', php: 'PHP',
      xml: 'XML', svg: 'SVG', graphql: 'GraphQL',
    };
    return ext ? (map[ext] || ext.toUpperCase()) : '';
  };

  return (
    <div className="h-[24px] border-t border-[var(--dp-border)] bg-[var(--dp-bg-secondary)] px-3 flex items-center justify-between text-[11px] text-gray-400 shrink-0 select-none font-sans z-30">
      {/* Left Section */}
      <div className="flex items-center gap-3">
        {/* Workspace name */}
        {workspacePath && (
          <div className="flex items-center gap-1.5 hover:bg-white/5 px-1 py-0.5 rounded cursor-default transition-colors" title="Active workspace">
            <Globe className="w-3 h-3 text-[var(--dp-accent)]/80" />
            <span className="font-mono text-gray-300 text-[10px]">{getWorkspaceFolderBasename()}</span>
          </div>
        )}

        {/* Git branch */}
        {workspacePath && (
          <div className="flex items-center gap-1 hover:bg-white/5 px-1 py-0.5 rounded cursor-pointer transition-colors" title="Git Branch">
            <GitBranch className="w-3 h-3" />
            <span className="text-[10px]">{statusBarBranch}</span>
          </div>
        )}

        {/* Diagnostics */}
        <div className="flex items-center gap-2">
          <div className={`flex items-center gap-0.5 ${diagnostics.errors > 0 ? 'text-[var(--dp-error)]' : 'text-gray-500'}`} title={`${diagnostics.errors} Error(s)`}>
            <AlertCircle className="w-3 h-3" />
            <span className="text-[10px] font-mono">{diagnostics.errors}</span>
          </div>
          <div className={`flex items-center gap-0.5 ${diagnostics.warnings > 0 ? 'text-[var(--dp-warning)]' : 'text-gray-500'}`} title={`${diagnostics.warnings} Warning(s)`}>
            <AlertTriangle className="w-3 h-3" />
            <span className="text-[10px] font-mono">{diagnostics.warnings}</span>
          </div>
        </div>
      </div>

      {/* Right Section */}
      <div className="flex items-center gap-3">
        {/* AI Status */}
        {isGenerating ? (
          <div className="flex items-center gap-1.5 text-[var(--dp-accent)] animate-pulse-subtle">
            <Zap className="w-3 h-3" />
            <span className="text-[10px] font-medium">AI Generating...</span>
          </div>
        ) : (
          <div className="flex items-center gap-1 text-gray-500 hover:text-gray-300 transition-colors" title="AI Model">
            <Cpu className="w-3 h-3" />
            <span className="text-[10px]">{activeProfileName || 'No Model'}</span>
          </div>
        )}

        {/* Run status */}
        {statusBarDebug === 'Running' && (
          <div className="flex items-center gap-1 text-[var(--dp-success)] font-semibold">
            <CheckCircle2 className="w-3 h-3" />
            <span className="text-[10px]">Running</span>
          </div>
        )}

        {/* Cursor position */}
        {activeFilePath && (
          <span className="text-[10px] font-mono text-gray-500 hover:text-gray-300 cursor-default transition-colors" title="Cursor Position">
            Ln {cursorInfo.line}, Col {cursorInfo.column}
          </span>
        )}

        {/* Language */}
        {getFileLanguage() && (
          <span className="text-[10px] font-mono text-gray-400 hover:text-gray-200 cursor-pointer transition-colors" title="File Language">
            {getFileLanguage()}
          </span>
        )}

        {/* Encoding & Indentation */}
        <span className="text-[10px] text-gray-500">UTF-8</span>
        <span className="text-[10px] text-gray-500">Spaces: 2</span>
      </div>
    </div>
  );
};
