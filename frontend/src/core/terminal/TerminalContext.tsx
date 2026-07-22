import React, { createContext, useContext, useState } from 'react';
import type { ReactNode } from 'react';
import type { ProcessEntry } from '../../types/chat';

interface TerminalContextType {
  consoleLogs: string[];
  activeProcesses: ProcessEntry[];
  activeTerminalCommand: string | null;
  activeTerminalStatus: 'running' | 'completed' | 'failed' | null;
  activeTerminalExitCode: number | null;
  activeTerminalElapsed: number | null;
  bottomTab: 'terminal' | 'problems' | 'output' | 'ports' | 'debugConsole' | 'tasks';
  terminalHeight: number;
  isResizingTerminal: boolean;
  setConsoleLogs: React.Dispatch<React.SetStateAction<string[]>>;
  setActiveProcesses: React.Dispatch<React.SetStateAction<ProcessEntry[]>>;
  setActiveTerminalCommand: (cmd: string | null) => void;
  setActiveTerminalStatus: (status: 'running' | 'completed' | 'failed' | null) => void;
  setActiveTerminalExitCode: (code: number | null) => void;
  setActiveTerminalElapsed: (elapsed: number | null) => void;
  setBottomTab: (tab: 'terminal' | 'problems' | 'output' | 'ports' | 'debugConsole' | 'tasks') => void;
  setTerminalHeight: (h: number) => void;
  setIsResizingTerminal: (resizing: boolean) => void;
}

const TerminalContext = createContext<TerminalContextType | undefined>(undefined);

export const TerminalProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [consoleLogs, setConsoleLogs] = useState<string[]>([]);
  const [activeProcesses, setActiveProcesses] = useState<ProcessEntry[]>([]);
  const [activeTerminalCommand, setActiveTerminalCommand] = useState<string | null>(null);
  const [activeTerminalStatus, setActiveTerminalStatus] = useState<'running' | 'completed' | 'failed' | null>(null);
  const [activeTerminalExitCode, setActiveTerminalExitCode] = useState<number | null>(null);
  const [activeTerminalElapsed, setActiveTerminalElapsed] = useState<number | null>(null);
  const [bottomTab, setBottomTab] = useState<'terminal' | 'problems' | 'output' | 'ports' | 'debugConsole' | 'tasks'>('terminal');
  const [terminalHeight, setTerminalHeight] = useState(300);
  const [isResizingTerminal, setIsResizingTerminal] = useState(false);

  return (
    <TerminalContext.Provider
      value={{
        consoleLogs,
        activeProcesses,
        activeTerminalCommand,
        activeTerminalStatus,
        activeTerminalExitCode,
        activeTerminalElapsed,
        bottomTab,
        terminalHeight,
        isResizingTerminal,
        setConsoleLogs,
        setActiveProcesses,
        setActiveTerminalCommand,
        setActiveTerminalStatus,
        setActiveTerminalExitCode,
        setActiveTerminalElapsed,
        setBottomTab,
        setTerminalHeight,
        setIsResizingTerminal
      }}
    >
      {children}
    </TerminalContext.Provider>
  );
};

export const useTerminal = () => {
  const context = useContext(TerminalContext);
  if (!context) {
    throw new Error('useTerminal must be used within a TerminalProvider');
  }
  return context;
};
