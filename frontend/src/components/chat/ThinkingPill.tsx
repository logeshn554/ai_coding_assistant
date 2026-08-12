import React from 'react';
import ThinkingState, { type Row } from './ThinkingState';

interface ThinkingPillProps {
  content: string;
  durationMs?: number;
  variant?: "Steps" | "Reasoning" | "Search" | "Coding";
}

export const ThinkingPill: React.FC<ThinkingPillProps> = ({
  content,
  durationMs,
  variant,
}) => {
  const secs = durationMs ? (durationMs / 1000).toFixed(0) : "4";
  
  // Parse content into rows for the reasoning/steps trace
  const rawLines = content
    .split(/\n+/)
    .map((line) => line.replace(/^[-*•\d.]+\s*/, '').trim())
    .filter(Boolean);

  const rows: Row[] = rawLines.length > 0
    ? rawLines.map((line) => ({ primary: line }))
    : [{ primary: content.trim() || "Analyzing request..." }];

  const activeVariant = variant ?? (rawLines.length > 1 ? "Steps" : "Reasoning");

  return (
    <div className="w-full my-2">
      <ThinkingState
        variant={activeVariant}
        customRows={rows}
        activeLabel="Thinking"
        doneLabel={`Thought for ${secs} seconds`}
        isWorking={false}
      />
    </div>
  );
};
