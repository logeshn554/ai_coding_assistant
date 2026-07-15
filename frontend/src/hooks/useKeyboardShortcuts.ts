import { useState, useEffect } from 'react';

export function useKeyboardShortcuts() {
  const [isQuickOpenOpen, setIsQuickOpenOpen] = useState(false);
  const [isGoToSymbolOpen, setIsGoToSymbolOpen] = useState(false);

  useEffect(() => {
    const handleGlobalKey = (e: KeyboardEvent) => {
      const isCtrl = e.ctrlKey || e.metaKey;
      if (isCtrl && !e.shiftKey && !e.altKey && e.key.toLowerCase() === 'p') {
        e.preventDefault();
        setIsGoToSymbolOpen(false);
        setIsQuickOpenOpen((v) => !v);
        return;
      }
      if (isCtrl && e.shiftKey && !e.altKey && e.key.toLowerCase() === 'o') {
        e.preventDefault();
        setIsQuickOpenOpen(false);
        setIsGoToSymbolOpen((v) => !v);
        return;
      }
    };
    window.addEventListener('keydown', handleGlobalKey, { capture: true });
    return () => window.removeEventListener('keydown', handleGlobalKey, { capture: true });
  }, []);

  return {
    isQuickOpenOpen,
    setIsQuickOpenOpen,
    isGoToSymbolOpen,
    setIsGoToSymbolOpen
  };
}
