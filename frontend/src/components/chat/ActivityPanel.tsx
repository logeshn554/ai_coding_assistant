import React from 'react';
import type { ChatMessage } from '../../types/chat';
import ToolChips, { type ToolRow } from './ToolChips';

interface ActivityPanelProps {
  toolMessages: ChatMessage[];
  isGenerating?: boolean;
}

export const ActivityPanel: React.FC<ActivityPanelProps> = ({ toolMessages, isGenerating }) => {
  if (toolMessages.length === 0 && !isGenerating) return null;

  const rows: ToolRow[] = toolMessages.map((m) => {
    const name = m.name || 'tool';
    const n = name.toLowerCase();
    let icon = 'read';
    if (n.includes('write') || n.includes('edit') || n.includes('delete') || n.includes('replace')) icon = 'write';
    else if (n.includes('run') || n.includes('command') || n.includes('exec') || n.includes('terminal')) icon = 'run';
    else if (n.includes('search') || n.includes('grep')) icon = 'search';

    const contentStr = typeof m.content === 'string' ? m.content : JSON.stringify(m.content);
    const firstLine = contentStr.split('\n')[0] || '';

    return {
      icon,
      label: name.replace(/^Processing\s+/i, '').replace(/_/g, ' '),
      chip: firstLine.slice(0, 40) || 'Executed',
      mono: true,
      detailMono: true,
      detail: contentStr.split('\n').slice(0, 6).map((line) => ({
        text: line,
        tone: line.startsWith('+') ? ('add' as const) : line.startsWith('-') ? ('del' as const) : ('normal' as const),
      })),
    };
  });

  return (
    <div className="my-2 select-none">
      <ToolChips
        customRows={rows}
        customDiffs={[]}
        headerLabel={`${rows.length} tool call${rows.length !== 1 ? 's' : ''}`}
        messagesCount={1}
        initialExpanded={Boolean(isGenerating)}
      />
    </div>
  );
};
