import React from 'react';
import { ChevronRight, FileCode, Folder, Code2, Box } from 'lucide-react';

interface BreadcrumbBarProps {
  filePath: string | null;
  currentSymbol?: string | null;
  onSelectPathSegment?: (segmentPath: string) => void;
}

export const BreadcrumbBar: React.FC<BreadcrumbBarProps> = ({
  filePath,
  currentSymbol,
  onSelectPathSegment
}) => {
  if (!filePath) return null;

  const parts = filePath.split(/[\\/]/).filter(Boolean);
  const fileName = parts.pop() || filePath;

  return (
    <div
      className="h-7 px-3 flex items-center gap-1.5 text-[11px] font-mono select-none overflow-x-auto shrink-0 scrollbar-none"
      style={{
        background: 'var(--dp-bg-secondary)',
        borderBottom: '1px solid var(--dp-border)',
        color: 'var(--dp-text-muted)'
      }}
    >
      <Folder className="w-3.5 h-3.5 text-[var(--dp-accent)] shrink-0" />
      
      {parts.map((part, idx) => {
        const segPath = parts.slice(0, idx + 1).join('/');
        return (
          <React.Fragment key={segPath}>
            <button
              onClick={() => onSelectPathSegment?.(segPath)}
              className="hover:text-[var(--dp-text-bright)] transition-colors cursor-pointer truncate max-w-[120px]"
            >
              {part}
            </button>
            <ChevronRight className="w-3 h-3 text-[var(--dp-text-muted)] opacity-50 shrink-0" />
          </React.Fragment>
        );
      })}

      <div className="flex items-center gap-1 font-semibold text-[var(--dp-text-bright)] shrink-0">
        <FileCode className="w-3.5 h-3.5 text-blue-400 shrink-0" />
        <span>{fileName}</span>
      </div>

      {currentSymbol && (
        <>
          <ChevronRight className="w-3 h-3 text-[var(--dp-text-muted)] opacity-50 shrink-0" />
          <div className="flex items-center gap-1 text-[var(--dp-accent)] bg-[var(--dp-accent-dim)] px-1.5 py-0.5 rounded text-[10px] shrink-0 font-medium">
            <Box className="w-3 h-3 shrink-0" />
            <span>{currentSymbol}</span>
          </div>
        </>
      )}
    </div>
  );
};
