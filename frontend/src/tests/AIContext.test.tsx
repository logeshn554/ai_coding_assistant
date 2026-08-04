import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { AIProvider, useAI } from '../core/ai/AIContext';

// Mock dependencies
vi.mock('../core/workspace/WorkspaceContext', () => ({
  useWorkspace: () => ({ workspacePath: '/mock/workspace', triggerRefresh: vi.fn() })
}));
vi.mock('../core/editor/EditorContext', () => ({
  useEditor: () => ({ setProposedDiff: vi.fn(), handleSelectFile: vi.fn(), openFiles: [] })
}));
vi.mock('../core/terminal/TerminalContext', () => ({
  useTerminal: () => ({
    setActiveTerminalCommand: vi.fn(),
    setActiveTerminalStatus: vi.fn(),
    setActiveTerminalExitCode: vi.fn(),
    setActiveTerminalElapsed: vi.fn(),
    setActiveProcesses: vi.fn(),
    setConsoleLogs: vi.fn(),
    setBottomTab: vi.fn()
  })
}));
vi.mock('../core/git/GitContext', () => ({
  useGit: () => ({ updateStatusBarInfo: vi.fn() })
}));
vi.mock('../core/toast/ToastContext', () => ({
  useToast: () => ({ showToast: vi.fn() })
}));

const TestComponent = () => {
  const ai = useAI();
  return (
    <div>
      <span data-testid="cost">{ai.totalCostUsd}</span>
      <span data-testid="connected">{ai.isWsConnected ? 'yes' : 'no'}</span>
    </div>
  );
};

describe('AIContext Smoke Test', () => {
  it('renders AIProvider and initializes state correctly', () => {
    render(
      <AIProvider>
        <TestComponent />
      </AIProvider>
    );

    expect(screen.getByTestId('cost').textContent).toBe('0');
    expect(screen.getByTestId('connected').textContent).toBe('no');
  });
});
