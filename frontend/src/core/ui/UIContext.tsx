import React, { createContext, useContext, useState } from 'react';
import type { ReactNode } from 'react';

type SidebarTabType = 'explorer' | 'search' | 'git' | 'debug' | 'extensions' | 'testing' | 'packages' | 'agents' | 'workspace' | 'profile';
type ActiveMenuType = 'file' | 'edit' | 'view' | 'terminal' | 'help' | null;

interface UIContextType {
  sidebarWidth: number;
  isResizingSidebar: boolean;
  aiPanelWidth: number;
  isResizingAiPanel: boolean;
  sidebarTab: SidebarTabType;
  isSidebarOpen: boolean;
  activeMenu: ActiveMenuType;
  setSidebarWidth: (width: number) => void;
  setIsResizingSidebar: (resizing: boolean) => void;
  setAiPanelWidth: (width: number) => void;
  setIsResizingAiPanel: (resizing: boolean) => void;
  setSidebarTab: (tab: SidebarTabType) => void;
  setIsSidebarOpen: (open: boolean) => void;
  isAiPanelOpen: boolean;
  setIsAiPanelOpen: (open: boolean) => void;
  setActiveMenu: (menu: ActiveMenuType) => void;
}

const UIContext = createContext<UIContextType | undefined>(undefined);

export const UIProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [sidebarWidth, setSidebarWidth] = useState(320);
  const [isResizingSidebar, setIsResizingSidebar] = useState(false);
  const [aiPanelWidth, setAiPanelWidth] = useState(380);
  const [isResizingAiPanel, setIsResizingAiPanel] = useState(false);
  const [sidebarTab, setSidebarTab] = useState<SidebarTabType>('explorer');
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [isAiPanelOpen, setIsAiPanelOpen] = useState(true);
  const [activeMenu, setActiveMenu] = useState<ActiveMenuType>(null);

  return (
    <UIContext.Provider
      value={{
        sidebarWidth,
        isResizingSidebar,
        aiPanelWidth,
        isResizingAiPanel,
        sidebarTab,
        isSidebarOpen,
        isAiPanelOpen,
        activeMenu,
        setSidebarWidth,
        setIsResizingSidebar,
        setAiPanelWidth,
        setIsResizingAiPanel,
        setSidebarTab,
        setIsSidebarOpen,
        setIsAiPanelOpen,
        setActiveMenu
      }}
    >
      {children}
    </UIContext.Provider>
  );
};

export const useUI = () => {
  const context = useContext(UIContext);
  if (!context) {
    throw new Error('useUI must be used within a UIProvider');
  }
  return context;
};
