import React, { useState } from 'react';
import { Copy, Check, Terminal, ChevronDown, ChevronUp } from 'lucide-react';
import hljs from 'highlight.js';
import 'highlight.js/styles/github-dark.css';

interface CodeBlockProps {
  inline?: boolean;
  className?: string;
  children?: React.ReactNode;
  onRunCommand?: (command: string) => void;
}

// Language display names
const LANG_LABELS: Record<string, string> = {
  js: 'JavaScript', javascript: 'JavaScript', ts: 'TypeScript', typescript: 'TypeScript',
  tsx: 'TSX', jsx: 'JSX', py: 'Python', python: 'Python', sh: 'Shell', bash: 'Bash',
  zsh: 'Zsh', powershell: 'PowerShell', ps1: 'PowerShell', json: 'JSON', yaml: 'YAML',
  yml: 'YAML', toml: 'TOML', css: 'CSS', scss: 'SCSS', html: 'HTML', xml: 'XML',
  sql: 'SQL', go: 'Go', rs: 'Rust', rust: 'Rust', java: 'Java', c: 'C', cpp: 'C++',
  cs: 'C#', php: 'PHP', rb: 'Ruby', swift: 'Swift', kt: 'Kotlin', md: 'Markdown',
  dockerfile: 'Dockerfile', graphql: 'GraphQL', lua: 'Lua', r: 'R', code: 'Code',
};

// Language dot colors
const LANG_COLORS: Record<string, string> = {
  js: '#f7df1e', javascript: '#f7df1e', ts: '#3178c6', typescript: '#3178c6',
  tsx: '#3178c6', jsx: '#f7df1e', py: '#3572a5', python: '#3572a5',
  sh: '#89e051', bash: '#89e051', json: '#cbcb41', yaml: '#cb171e', yml: '#cb171e',
  css: '#563d7c', html: '#e34f26', go: '#00add8', rs: '#dea584', rust: '#dea584',
  sql: '#e38c00', graphql: '#e10098',
};

export const CodeBlock: React.FC<CodeBlockProps> = ({ inline, className, children, onRunCommand }) => {
  const [copied, setCopied] = useState(false);
  const [collapsed, setCollapsed] = useState(false);

  const codeString = String(children || '').replace(/\n$/, '');
  const match = /language-(\w+)/.exec(className || '');
  const language = match ? match[1] : 'code';
  const langLabel = LANG_LABELS[language] || language;
  const langColor = LANG_COLORS[language] || '#757c87';

  // Inline code — premium pill style
  if (inline) {
    return (
      <code
        className="font-mono px-1.5 py-0.5 rounded-md text-[12.5px]"
        style={{
          background: 'rgba(79,140,255,0.08)',
          color: '#8ab4f8',
          border: '1px solid rgba(79,140,255,0.12)',
          fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
        }}
      >
        {children}
      </code>
    );
  }

  const handleCopy = () => {
    navigator.clipboard.writeText(codeString);
    setCopied(true);
    setTimeout(() => setCopied(false), 1800);
  };

  const handleRun = () => {
    if (onRunCommand) {
      onRunCommand(codeString);
    } else {
      navigator.clipboard.writeText(codeString);
      window.dispatchEvent(new CustomEvent('insert-terminal-cmd', { detail: codeString }));
    }
  };

  let highlightedHtml: string | null = null;
  try {
    if (language && hljs.getLanguage(language)) {
      highlightedHtml = hljs.highlight(codeString, { language }).value;
    } else {
      highlightedHtml = hljs.highlightAuto(codeString).value;
    }
  } catch {
    highlightedHtml = null;
  }

  const lineCount = codeString.split('\n').length;

  return (
    <div
      className="my-4 rounded-2xl overflow-hidden group/code transition-all duration-200"
      style={{
        background: '#0d0f14',
        border: '1px solid rgba(255,255,255,0.06)',
        boxShadow: '0 4px 20px rgba(0,0,0,0.4)',
        fontFamily: "'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace",
      }}
    >
      {/* ── Floating Header ── */}
      <div
        className="flex items-center justify-between px-4 py-2.5 select-none"
        style={{
          background: 'rgba(255,255,255,0.025)',
          borderBottom: '1px solid rgba(255,255,255,0.05)',
        }}
      >
        {/* Language badge */}
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full shrink-0" style={{ background: langColor }} />
          <span
            className="text-[11px] font-semibold tracking-wide"
            style={{ color: '#aeb6c2', fontFamily: 'Inter, sans-serif' }}
          >
            {langLabel}
          </span>
          {lineCount > 1 && (
            <span className="text-[10px]" style={{ color: '#757c87', fontFamily: 'Inter, sans-serif' }}>
              {lineCount} lines
            </span>
          )}
        </div>

        {/* Controls — visible on hover */}
        <div className="flex items-center gap-1 opacity-0 group-hover/code:opacity-100 transition-opacity duration-150">
          {/* Collapse / Expand */}
          <button
            type="button"
            onClick={() => setCollapsed(!collapsed)}
            title={collapsed ? 'Expand' : 'Collapse'}
            className="flex items-center gap-1 px-2 py-1 rounded-lg text-[10px] font-medium transition-all duration-150 cursor-pointer hover:scale-[1.05]"
            style={{ background: 'rgba(255,255,255,0.05)', color: '#757c87' }}
          >
            {collapsed
              ? <ChevronDown className="w-3 h-3" />
              : <ChevronUp className="w-3 h-3" />
            }
          </button>

          {/* Run in terminal */}
          <button
            type="button"
            onClick={handleRun}
            title="Run in terminal"
            className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[10px] font-medium transition-all duration-150 cursor-pointer hover:scale-[1.05]"
            style={{ background: 'rgba(79,140,255,0.08)', color: '#4f8cff', border: '1px solid rgba(79,140,255,0.15)' }}
          >
            <Terminal className="w-3 h-3" />
            <span style={{ fontFamily: 'Inter, sans-serif' }}>Run</span>
          </button>

          {/* Copy */}
          <button
            type="button"
            onClick={handleCopy}
            title="Copy code"
            className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[10px] font-medium transition-all duration-150 cursor-pointer hover:scale-[1.05]"
            style={copied
              ? { background: 'rgba(34,197,94,0.1)', color: '#22c55e', border: '1px solid rgba(34,197,94,0.2)' }
              : { background: 'rgba(255,255,255,0.05)', color: '#aeb6c2' }
            }
          >
            {copied
              ? <><Check className="w-3 h-3" /><span style={{ fontFamily: 'Inter, sans-serif' }}>Copied!</span></>
              : <><Copy className="w-3 h-3" /><span style={{ fontFamily: 'Inter, sans-serif' }}>Copy</span></>
            }
          </button>
        </div>
      </div>

      {/* ── Code Body ── */}
      {!collapsed && (
        <div
          className="overflow-x-auto select-text"
          style={{ padding: '18px 20px', maxHeight: '480px', overflowY: 'auto', scrollbarWidth: 'thin', scrollbarColor: 'rgba(255,255,255,0.08) transparent' }}
        >
          {highlightedHtml ? (
            <code
              className="hljs text-[12.5px] leading-relaxed whitespace-pre"
              dangerouslySetInnerHTML={{ __html: highlightedHtml }}
              style={{ fontFamily: 'inherit' }}
            />
          ) : (
            <code className="text-[12.5px] leading-relaxed whitespace-pre" style={{ color: '#c8cfd9', fontFamily: 'inherit' }}>
              {codeString}
            </code>
          )}
        </div>
      )}

      {/* Collapsed state */}
      {collapsed && (
        <button
          type="button"
          onClick={() => setCollapsed(false)}
          className="w-full flex items-center justify-center gap-1.5 py-2 text-[11px] transition-colors cursor-pointer"
          style={{ color: '#757c87', fontFamily: 'Inter, sans-serif' }}
        >
          <ChevronDown className="w-3.5 h-3.5" />
          Show {lineCount} lines
        </button>
      )}
    </div>
  );
};
