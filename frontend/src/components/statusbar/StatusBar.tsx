import React, { useState, useEffect } from 'react';
import { GitBranch, AlertCircle, AlertTriangle, Zap, Cpu, CheckCircle2, DollarSign } from 'lucide-react';
import { useWorkspace } from '../../core/workspace/WorkspaceContext';
import { useGit } from '../../core/git/GitContext';
import { useSettings } from '../../core/settings/SettingsContext';
import { useAI } from '../../core/ai/AIContext';
import { useUI } from '../../core/ui/UIContext';
import { useEditor } from '../../core/editor/EditorContext';
import { useLSP } from '../../core/lsp/LSPContext';

export const StatusBar: React.FC = () => {
  const { workspacePath } = useWorkspace();
  const { statusBarBranch, statusBarDebug } = useGit();
  const { activeProfileName } = useSettings();
  const { isGenerating, isWsConnected, isModelFallback, totalCostUsd } = useAI();
  const { activeFilePath } = useEditor();
  const { setSidebarTab, setIsSidebarOpen } = useUI();
  const { activeLanguage, isReady, error: lspError } = useLSP();

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
      className="h-[22px] flex items-center justify-between px-2 shrink-0 select-none font-sans z-30 text-[11px]"
      style={{
        background: '#1A1B1E',
        borderTop: '1px solid #393B40',
        color: '#9DA0A8',
      }}
    >
      {/* â”€â”€ Left â”€â”€ */}
      <div className="flex items-center gap-0">

        {/* Git Branch â€” JetBrains style accent chip on far left */}
        {workspacePath && statusBarBranch && (
          <div
            className="flex items-center gap-1 px-2 h-[22px] cursor-pointer transition-colors"
            style={{ background: '#4C8DFF', color: '#fff' }}
            title="Git Branch"
          >
            <GitBranch className="w-3 h-3" />
            <span className="text-[11px] font-medium">{statusBarBranch}</span>
          </div>
        )}

        {/* Diagnostics */}
        <div className="flex items-center gap-3 px-3">
          <div
            className={`flex items-center gap-1 cursor-pointer hover:text-[var(--dp-text-primary)] transition-colors ${diagnostics.errors > 0 ? 'text-[#FF6B6B]' : ''}`}
            title={`${diagnostics.errors} Error(s)`}
          >
            <AlertCircle className="w-3 h-3" />
            <span className="font-mono">{diagnostics.errors}</span>
          </div>
          <div
            className={`flex items-center gap-1 cursor-pointer hover:text-[var(--dp-text-primary)] transition-colors ${diagnostics.warnings > 0 ? 'text-[#FFB74D]' : ''}`}
            title={`${diagnostics.warnings} Warning(s)`}
          >
            <AlertTriangle className="w-3 h-3" />
            <span className="font-mono">{diagnostics.warnings}</span>
          </div>
        </div>

        {/* Run status */}
        {statusBarDebug === 'Running' && (
          <div className="flex items-center gap-1 px-2" style={{ color: '#62D26F' }}>
            <CheckCircle2 className="w-3 h-3" />
            <span className="font-medium">Running</span>
          </div>
        )}
      </div>

      {/* â”€â”€ Right â”€â”€ */}
      <div className="flex items-center gap-0 h-full">

        {/* WS disconnected */}
        {!isWsConnected && (
          <div className="flex items-center gap-1 px-2 animate-pulse" style={{ color: '#FF6B6B' }} title="Backend Disconnected">
            <AlertCircle className="w-3 h-3" />
            <span>Disconnected</span>
          </div>
        )}

        {/* Model fallback */}
        {isModelFallback && (
          <div className="flex items-center gap-1 px-2" style={{ color: '#FFB74D' }}>
            <AlertTriangle className="w-3 h-3" />
            <span>Fallback</span>
          </div>
        )}

        {/* AI Status */}
        {isGenerating ? (
          <div className="flex items-center gap-1 px-2 h-full" style={{ color: '#4C8DFF' }}>
            <Zap className="w-3 h-3 animate-pulse" />
            <span>Generating...</span>
          </div>
        ) : (
          <div
            onClick={() => { setSidebarTab('profile'); setIsSidebarOpen(true); }}
            className="flex items-center gap-1 px-2 h-full cursor-pointer transition-colors hover:bg-white/5"
            title="Active Model"
          >
            <Cpu className="w-3 h-3" style={{ color: '#4C8DFF' }} />
            <span>{activeProfileName || 'DevPilot AI'}</span>
          </div>
        )}

        {/* Cost tracker — only shown when real cost is being tracked */}
        {totalCostUsd > 0 && (
          <div
            className="flex items-center gap-1 px-2 h-full cursor-default"
            title={`Session cost: $${totalCostUsd.toFixed(6)}`}
            style={{ color: totalCostUsd >= 1.0 ? '#FFB74D' : '#9DA0A8' }}
          >
            <DollarSign className="w-3 h-3" />
            <span className="font-mono">{totalCostUsd.toFixed(3)}</span>
          </div>
        )}

        {/* Language + LSP status — dot color reflects connection health */}
        {getFileLanguage() && (
          <div
            className="flex items-center gap-1 px-2 h-full cursor-pointer hover:bg-white/5 transition-colors"
            title={activeLanguage ? (isReady ? `LSP: ${activeLanguage} connected` : lspError || `LSP: ${activeLanguage} unavailable`) : 'Language mode'}
          >
            {activeLanguage && (
              <span
                className="w-1.5 h-1.5 rounded-full shrink-0 transition-colors"
                style={{
                  background: isReady ? '#62D26F' : lspError ? '#FF6B6B' : '#6F737A',
                }}
              />
            )}
            <span>{getFileLanguage()}</span>
          </div>
        )}

        {/* Cursor position */}
        {activeFilePath && (
          <div className="flex items-center px-2 h-full cursor-default">
            <span className="font-mono">{cursorInfo.line}:{cursorInfo.column}</span>
          </div>
        )}

        {/* Encoding */}
        <div className="flex items-center px-2 h-full">
          <span>UTF-8</span>
        </div>

        {/* Indent */}
        <div className="flex items-center px-2 h-full">
          <span>Spaces: 2</span>
        </div>
      </div>
    </div>
  );
};
