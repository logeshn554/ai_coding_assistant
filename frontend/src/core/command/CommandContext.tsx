import React, { createContext, useContext, useState, useEffect } from 'react';
import type { ReactNode } from 'react';

interface CommandContextType {
  isCommandPaletteOpen: boolean;
  commandSearch: string;
  setIsCommandPaletteOpen: (open: boolean) => void;
  setCommandSearch: (search: string) => void;
  toggleCommandPalette: () => void;
}

const CommandContext = createContext<CommandContextType | undefined>(undefined);

export const CommandProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [isCommandPaletteOpen, setIsCommandPaletteOpen] = useState(false);
  const [commandSearch, setCommandSearch] = useState('');

  const toggleCommandPalette = () => {
    setIsCommandPaletteOpen(prev => !prev);
  };

  // Keyboard shortcut Ctrl+Shift+P / Cmd+Shift+P
  useEffect(() => {
    const handlePaletteKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key.toLowerCase() === 'p') {
        e.preventDefault();
        toggleCommandPalette();
      } else if (e.key === 'Escape') {
        setIsCommandPaletteOpen(false);
      }
    };
    window.addEventListener('keydown', handlePaletteKey);
    return () => window.removeEventListener('keydown', handlePaletteKey);
  }, []);

  return (
    <CommandContext.Provider
      value={{
        isCommandPaletteOpen,
        commandSearch,
        setIsCommandPaletteOpen,
        setCommandSearch,
        toggleCommandPalette
      }}
    >
      {children}
    </CommandContext.Provider>
  );
};

export const useCommand = () => {
  const context = useContext(CommandContext);
  if (!context) {
    throw new Error('useCommand must be used within a CommandProvider');
  }
  return context;
};
