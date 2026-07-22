import React, { useState } from 'react';
import { Copy, Check, Terminal } from 'lucide-react';
import hljs from 'highlight.js';
import 'highlight.js/styles/github-dark.css';

interface CodeBlockProps {
  inline?: boolean;
  className?: string;
  children?: React.ReactNode;
  onRunCommand?: (command: string) => void;
}

export const CodeBlock: React.FC<CodeBlockProps> = ({
  inline,
  className,
  children,
  onRunCommand,
}) => {
  const [copied, setCopied] = useState(false);

  // Raw string content
  const codeString = String(children || '').replace(/\n$/, '');

  // Extract language from className (e.g., "language-powershell" => "powershell")
  const match = /language-(\w+)/.exec(className || '');
  const language = match ? match[1] : 'code';

  // Render inline code chips
  if (inline) {
    return (
      <code className="bg-zinc-800 rounded-md font-mono text-zinc-300 px-1.5 py-0.5 text-[12px] border border-zinc-700/50">
        {children}
      </code>
    );
  }

  // Handle copy to clipboard
  const handleCopy = () => {
    navigator.clipboard.writeText(codeString);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  // Handle run/insert command in terminal
  const handleRunInTerminal = () => {
    if (onRunCommand) {
      onRunCommand(codeString);
    } else {
      // Fallback: copy and dispatch custom event or clipboard
      navigator.clipboard.writeText(codeString);
      const customEvent = new CustomEvent('insert-terminal-cmd', { detail: codeString });
      window.dispatchEvent(customEvent);
    }
  };

  // Apply syntax highlighting HTML if language is known
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

  return (
    <div className="my-3 rounded-lg overflow-hidden border border-zinc-700 bg-zinc-900 shadow-md font-mono text-[12.5px]">
      {/* Header bar */}
      <div className="flex items-center justify-between px-3 py-1.5 bg-zinc-950/80 border-b border-zinc-800 select-none">
        <span className="text-[11px] font-semibold text-zinc-400 font-mono lowercase">
          {language}
        </span>

        <div className="flex items-center gap-1.5 text-zinc-400">
          <button
            type="button"
            onClick={handleRunInTerminal}
            className="p-1 hover:bg-zinc-800 hover:text-blue-400 rounded transition-colors cursor-pointer"
            title="Insert/Run in terminal (@)"
          >
            <Terminal className="w-3.5 h-3.5" />
          </button>
          <button
            type="button"
            onClick={handleCopy}
            className="flex items-center gap-1 px-1.5 py-0.5 hover:bg-zinc-800 hover:text-zinc-200 rounded transition-colors text-[11px] cursor-pointer"
            title="Copy code"
          >
            {copied ? (
              <>
                <Check className="w-3.5 h-3.5 text-green-400" />
                <span className="text-green-400 text-[10px] font-sans font-semibold">Copied!</span>
              </>
            ) : (
              <Copy className="w-3.5 h-3.5" />
            )}
          </button>
        </div>
      </div>

      {/* Code Container */}
      <div className="p-3 overflow-x-auto text-zinc-300 font-mono leading-relaxed select-text scrollbar-thin bg-zinc-900">
        {highlightedHtml ? (
          <code
            className="hljs whitespace-pre"
            dangerouslySetInnerHTML={{ __html: highlightedHtml }}
          />
        ) : (
          <code className="whitespace-pre text-zinc-300">{codeString}</code>
        )}
      </div>
    </div>
  );
};
