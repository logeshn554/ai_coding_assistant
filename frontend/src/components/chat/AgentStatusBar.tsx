import React from 'react';
import { Settings } from 'lucide-react';

interface AgentStatusBarProps {
  contextPercentage?: number;
  contextTokens?: string;
  activeProfileName: string;
  onOpenSettings: () => void;
}

export const AgentStatusBar: React.FC<AgentStatusBarProps> = ({
  contextPercentage = 0,
  contextTokens = '0',
  activeProfileName,
  onOpenSettings,
}) => {
  return (
    <div className="flex items-center justify-between font-mono text-[9px] select-none text-gray-500 pb-2 px-0.5 border-t border-[#2d2d2d] pt-2">
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={onOpenSettings}
          className="p-1 hover:text-gray-300 transition-colors cursor-pointer"
          title="Settings & Model Config"
        >
          <Settings className="w-3 h-3" />
        </button>
        <span className="text-gray-600 truncate max-w-[120px]" title={`Profile: ${activeProfileName}`}>
          Profile: {activeProfileName}
        </span>
      </div>
      <div className="flex items-center gap-3">
        <span>Tokens: {contextTokens}</span>
        <div className="flex items-center gap-1.5">
          <div className="w-12 h-1 bg-[#1a1a1a] rounded-full overflow-hidden border border-white/5">
            <div
              className={`h-full transition-all duration-300 ${
                contextPercentage > 80 ? 'bg-red-500' : contextPercentage > 50 ? 'bg-yellow-500' : 'bg-violet-500'
              }`}
              style={{ width: `${Math.min(contextPercentage, 100)}%` }}
            />
          </div>
          <span>{contextPercentage}%</span>
        </div>
      </div>
    </div>
  );
};
