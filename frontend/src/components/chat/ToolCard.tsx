import React from 'react';
import ToolChips, { type ToolRow } from './ToolChips';

interface ToolCardProps {
  name: string;
  arguments: Record<string, any>;
  status: 'running' | 'completed' | 'failed';
  output?: string;
  durationMs?: number;
}

const mapIconName = (name: string): string => {
  const n = name.toLowerCase();
  if (n.includes('write') || n.includes('edit') || n.includes('replace')) return 'write';
  if (n.includes('read') || n.includes('view')) return 'read';
  if (n.includes('run') || n.includes('command') || n.includes('exec')) return 'run';
  if (n.includes('search') || n.includes('grep')) return 'search';
  return 'read';
};

export const ToolCard: React.FC<ToolCardProps> = ({
  name,
  arguments: args,
  status,
  output,
  durationMs,
}) => {
  const targetLabel =
    args.TargetFile ||
    args.path ||
    args.AbsolutePath ||
    args.file_path ||
    args.query ||
    args.Query ||
    args.command ||
    args.CommandLine ||
    'action';

  const filename = String(targetLabel).split(/[/\\]/).pop() || String(targetLabel);

  const detailLines = output
    ? output
        .split('\n')
        .slice(0, 5)
        .map((line) => ({
          text: line,
          tone: line.startsWith('+')
            ? ('add' as const)
            : line.startsWith('-')
            ? ('del' as const)
            : ('normal' as const),
        }))
    : [{ text: `Status: ${status}${durationMs ? ` (${durationMs}ms)` : ''}` }];

  const row: ToolRow = {
    icon: mapIconName(name),
    label: name,
    chip: filename,
    mono: true,
    detailMono: true,
    detail: detailLines,
  };

  return (
    <div className="my-1.5">
      <ToolChips
        customRows={[row]}
        customDiffs={[]}
        headerLabel={`1 tool call: ${name}`}
        messagesCount={1}
      />
    </div>
  );
};
