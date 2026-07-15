import { useEffect } from 'react';
import { useTerminal } from '../core/terminal/TerminalContext';
import { useUI } from '../core/ui/UIContext';

export function useResizeManager() {
  const {
    terminalHeight,
    setTerminalHeight,
    isResizingTerminal,
    setIsResizingTerminal
  } = useTerminal();

  const {
    sidebarWidth,
    setSidebarWidth,
    isResizingSidebar,
    setIsResizingSidebar,
    aiPanelWidth,
    setAiPanelWidth,
    isResizingAiPanel,
    setIsResizingAiPanel
  } = useUI();

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (isResizingSidebar) {
        const newWidth = Math.max(150, Math.min(500, e.clientX - 56));
        setSidebarWidth(newWidth);
      } else if (isResizingAiPanel) {
        const newWidth = Math.max(250, Math.min(600, window.innerWidth - e.clientX));
        setAiPanelWidth(newWidth);
      } else if (isResizingTerminal) {
        const newHeight = Math.max(100, Math.min(500, window.innerHeight - e.clientY - 24));
        setTerminalHeight(newHeight);
      }
    };

    const handleMouseUp = () => {
      setIsResizingSidebar(false);
      setIsResizingAiPanel(false);
      setIsResizingTerminal(false);
    };

    if (isResizingSidebar || isResizingAiPanel || isResizingTerminal) {
      window.addEventListener('mousemove', handleMouseMove);
      window.addEventListener('mouseup', handleMouseUp);
    }

    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [
    isResizingSidebar,
    isResizingAiPanel,
    isResizingTerminal,
    setSidebarWidth,
    setAiPanelWidth,
    setTerminalHeight,
    setIsResizingSidebar,
    setIsResizingAiPanel,
    setIsResizingTerminal
  ]);

  return {
    terminalHeight,
    isResizingTerminal,
    setIsResizingTerminal,
    sidebarWidth,
    isResizingSidebar,
    setIsResizingSidebar,
    aiPanelWidth,
    isResizingAiPanel,
    setIsResizingAiPanel
  };
}
