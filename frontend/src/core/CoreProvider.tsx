import React from 'react';
import type { ReactNode } from 'react';
import { ToastProvider } from './toast/ToastContext';
import { WorkspaceProvider } from './workspace/WorkspaceContext';
import { EditorProvider } from './editor/EditorContext';
import { TerminalProvider } from './terminal/TerminalContext';
import { SettingsProvider } from './settings/SettingsContext';
import { GitProvider } from './git/GitContext';
import { CommandProvider } from './command/CommandContext';
import { UIProvider } from './ui/UIContext';
import { AIProvider } from './ai/AIContext';

interface CoreProviderProps {
  children: ReactNode;
}

export const CoreProvider: React.FC<CoreProviderProps> = ({ children }) => {
  return (
    <ToastProvider>
      <WorkspaceProvider>
        <EditorProvider>
          <TerminalProvider>
            <SettingsProvider>
              <GitProvider>
                <CommandProvider>
                  <UIProvider>
                    <AIProvider>
                      {children}
                    </AIProvider>
                  </UIProvider>
                </CommandProvider>
              </GitProvider>
            </SettingsProvider>
          </TerminalProvider>
        </EditorProvider>
      </WorkspaceProvider>
    </ToastProvider>
  );
};
