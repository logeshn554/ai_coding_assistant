import React from 'react';
import { Search, FileText, Edit3, Terminal, CheckCircle, XCircle, Clock } from 'lucide-react';

interface ToolCardProps {
  name: string;
  arguments: Record<string, any>;
  status: 'running' | 'completed' | 'failed';
  output?: string;
  durationMs?: number;
}

export const ToolCard: React.FC<ToolCardProps> = ({ name, arguments: args, status, output, durationMs }) => {
  const getToolIcon = () => {
    switch (name.toLowerCase()) {
      case 'search_files':
      case 'find_symbol':
        return <Search className="w-4 h-4 text-info" />;
      case 'read_file':
        return <FileText className="w-4 h-4 text-primary" />;
      case 'write_file':
      case 'edit_file':
        return <Edit3 className="w-4 h-4 text-warning" />;
      case 'run_command':
      case 'run_test':
        return <Terminal className="w-4 h-4 text-accent" />;
      default:
        return <FileText className="w-4 h-4" />;
    }
  };

  const getTargetLabel = () => {
    return args.path || args.TargetFile || args.file_path || args.query || args.symbol || args.command || args.CommandLine || '';
  };

  return (
    <div className="tool-card my-1.5 p-2 rounded bg-base-200 border border-base-300 text-xs font-sans">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 font-medium">
          {getToolIcon()}
          <span>{name}</span>
          <span className="font-mono text-base-content/70 text-[11px] truncate max-w-[200px]">
            {getTargetLabel()}
          </span>
        </div>

        <div className="flex items-center gap-2">
          {durationMs && <span className="text-[10px] text-base-content/50">{durationMs}ms</span>}
          {status === 'running' && <Clock className="w-3.5 h-3.5 text-info animate-spin" />}
          {status === 'completed' && <CheckCircle className="w-3.5 h-3.5 text-success" />}
          {status === 'failed' && <XCircle className="w-3.5 h-3.5 text-error" />}
        </div>
      </div>

      {output && (
        <pre className="mt-1.5 p-1.5 bg-base-300 rounded font-mono text-[10px] text-base-content/80 overflow-x-auto max-h-24">
          {output}
        </pre>
      )}
    </div>
  );
};
