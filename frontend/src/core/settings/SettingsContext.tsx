import React, { createContext, useContext, useState, useEffect } from 'react';
import type { ReactNode } from 'react';
import { useToast } from '../toast/ToastContext';

interface SettingsContextType {
  isSettingsOpen: boolean;
  activeProfileName: string;
  setIsSettingsOpen: (open: boolean) => void;
  setActiveProfileName: (name: string) => void;
  fetchActiveProfile: () => Promise<void>;
  handleSettingsChanged: () => void;
}

const SettingsContext = createContext<SettingsContextType | undefined>(undefined);

export const SettingsProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [activeProfileName, setActiveProfileName] = useState('No Profile Connected');
  const { showToast } = useToast();

  const fetchActiveProfile = async () => {
    try {
      const res = await fetch('/api/profiles');
      if (res.ok) {
        const data = await res.json();
        const activeId = data.active_profile_id;
        const active = data.profiles?.find((p: any) => p.id === activeId);
        if (active) {
          setActiveProfileName(active.name);
        } else if (data.profiles && data.profiles.length > 0) {
          const firstActive = data.profiles.find((p: any) => p.isActive) || data.profiles[0];
          setActiveProfileName(firstActive.name);
        } else {
          setActiveProfileName('No Profile Connected');
        }
      }
    } catch (e) {
      console.error(e);
      setActiveProfileName('No Profile Connected');
    }
  };

  const handleSettingsChanged = () => {
    fetchActiveProfile();
    showToast('AI Profile settings updated!', 'info');
  };

  useEffect(() => {
    fetchActiveProfile();
  }, []);

  return (
    <SettingsContext.Provider
      value={{
        isSettingsOpen,
        activeProfileName,
        setIsSettingsOpen,
        setActiveProfileName,
        fetchActiveProfile,
        handleSettingsChanged
      }}
    >
      {children}
    </SettingsContext.Provider>
  );
};

export const useSettings = () => {
  const context = useContext(SettingsContext);
  if (!context) {
    throw new Error('useSettings must be used within a SettingsProvider');
  }
  return context;
};
