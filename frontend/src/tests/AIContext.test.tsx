import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
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
      <span data-testid="session-id">{ai.activeSessionId}</span>
    </div>
  );
};

describe('AIContext Smoke Test', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it('renders AIProvider and initializes state correctly', () => {
    render(
      <AIProvider>
        <TestComponent />
      </AIProvider>
    );

    expect(screen.getByTestId('cost').textContent).toBe('0');
    expect(screen.getByTestId('connected').textContent).toBe('no');
  });

  it('adopts the backend active session and keeps localStorage in sync', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url;
      if (url === '/api/chat/sessions') {
        return {
          ok: true,
          json: async () => ({ sessions: [{ id: 'server-session-42', title: 'Server Session', workspace_root: '/mock/workspace' }], active_session_id: 'server-session-42' })
        } as Response;
      }
      if (url === '/api/chat/history?session_id=server-session-42') {
        return { ok: true, json: async () => ({ messages: [] }) } as Response;
      }
      return { ok: true, json: async () => ({}) } as Response;
    });
    vi.stubGlobal('fetch', fetchMock);

    localStorage.setItem('loopix_session_id', 'stale-session');

    render(
      <AIProvider>
        <TestComponent />
      </AIProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId('session-id').textContent).toBe('server-session-42');
    });
    expect(localStorage.getItem('loopix_session_id')).toBe('server-session-42');
  });
});
