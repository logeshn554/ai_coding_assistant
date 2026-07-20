import React, { useState, useEffect } from 'react';
import { X, Plus, Trash2, ShieldCheck, Check, AlertCircle, RefreshCw, Bug } from 'lucide-react';

const AGENTS_LIST = [
  'Orchestrator Agent',
  'Planner Agent',
  'Requirement Analysis Agent',
  'Coding Agent',
  'File System Agent',
  'Terminal Agent',
  'Testing Agent',
  'Debugging Agent',
  'Documentation Agent',
  'Code Review Agent',
  'Refactoring Agent',
  'Git Agent'
];




interface AgentModelRowProps {
  label: string;
  value: string;
  selectableModels: string[];
  onChange: (val: string) => void;
}

function AgentModelRow({ label, value, selectableModels, onChange }: AgentModelRowProps) {
  const isDefault = value === '';
  const isCustom = value !== '' && !selectableModels.includes(value);
  const selectValue = isDefault ? '' : (isCustom ? 'custom' : value);

  return (
    <div className="flex flex-col gap-1.5 p-3 bg-white/[0.02] border border-white/5 rounded-lg">
      <div className="flex justify-between items-center">
        <span className="text-[11px] font-semibold text-gray-300">{label}</span>
      </div>
      <div className="flex gap-2">
        <select
          value={selectValue}
          onChange={(e) => {
            const val = e.target.value;
            if (val === 'custom') {
              onChange('custom-model');
            } else {
              onChange(val);
            }
          }}
          className="flex-1 px-2.5 py-1 bg-[#171922] border border-white/5 rounded-md text-xs text-white focus:outline-none focus:border-violet-500"
        >
          <option value="">Default (Use Profile)</option>
          {selectableModels.map(m => (
            <option key={m} value={m}>{m}</option>
          ))}
          <option value="custom">Custom (Type Model)...</option>
        </select>
        {(isCustom || selectValue === 'custom') && (
          <input
            type="text"
            value={value}
            onChange={(e) => onChange(e.target.value)}
            className="flex-1 px-2.5 py-1 bg-[#171922] border border-white/5 rounded-md text-xs text-white focus:outline-none focus:border-violet-500 font-mono"
            placeholder="Type model name..."
          />
        )}
      </div>
    </div>
  );
}

interface Profile {
  id?: string;
  name: string;
  api_key: string;
  base_url: string;
  model_name: string;
  api_format: 'openai' | 'anthropic' | 'google';
}

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  onProfileChanged: () => void;
}

export default function SettingsModal({ isOpen, onClose, onProfileChanged }: SettingsModalProps) {
  const [activeSettingsTab, setActiveSettingsTab] = useState<'profiles' | 'permissions' | 'preferences' | 'terminal'>('profiles');
  const [permissions, setPermissions] = useState<{ project: string[]; session: string[] }>({ project: [], session: [] });
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [activeId, setActiveId] = useState<string>('');
  const [selectedProfile, setSelectedProfile] = useState<Profile | null>(null);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);

  const [modelOptions, setModelOptions] = useState<string[]>([]);
  const [isFetchingModels, setIsFetchingModels] = useState(false);
  const [hasFetchedModels, setHasFetchedModels] = useState(false);

  const [excludeList, setExcludeList] = useState<string[]>([]);
  const [autoBackupEnabled, setAutoBackupEnabled] = useState<boolean>(true);
  const [agentModelName, setAgentModelName] = useState<string>('');
  const [agentModels, setAgentModels] = useState<Record<string, string>>({});

  // New state for bug scanning
  const [bugReport, setBugReport] = useState<string>('');
  const [scanning, setScanning] = useState<boolean>(false);

  // Terminal preference state
  const [defaultShell, setDefaultShell] = useState<string>('');
  const [termFontSize, setTermFontSize] = useState<number>(13);
  const [termScrollback, setTermScrollback] = useState<number>(5000);

  const loadPreferences = async () => {
    try {
      const res = await fetch('/api/config/settings');
      if (res.ok) {
        const data = await res.json();
        setExcludeList(data.exclude_list || []);
        setAutoBackupEnabled(data.auto_backup_enabled ?? true);
        setAgentModelName(data.agent_model_name || '');
        setAgentModels(data.agent_models || {});
        // Terminal preferences
        setDefaultShell(data.default_shell || '');
        if (data.terminal_font_size) setTermFontSize(data.terminal_font_size);
        if (data.terminal_scrollback) setTermScrollback(data.terminal_scrollback);
      }
    } catch (e) {
      console.error('Error loading preferences:', e);
    }
  };

  const savePreferences = async (
    newExclusions: string[],
    newBackup: boolean,
    newAgentModel?: string,
    newAgentModels?: Record<string, string>
  ) => {
    try {
      await fetch('/api/config/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          exclude_list: newExclusions,
          auto_backup_enabled: newBackup,
          agent_model_name: newAgentModel !== undefined ? newAgentModel : agentModelName,
          agent_models: newAgentModels !== undefined ? newAgentModels : agentModels,
          // Always include terminal prefs so they aren't reset by other saves
          default_shell: defaultShell,
          terminal_font_size: termFontSize,
          terminal_scrollback: termScrollback,
        })
      });
      onProfileChanged();
    } catch (e) {
      console.error('Error saving preferences:', e);
    }
  };

  const saveTerminalPrefs = async (shell: string, fontSize: number, scrollback: number) => {
    try {
      await fetch('/api/config/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          exclude_list: excludeList,
          auto_backup_enabled: autoBackupEnabled,
          agent_model_name: agentModelName,
          agent_models: agentModels,
          default_shell: shell,
          terminal_font_size: fontSize,
          terminal_scrollback: scrollback,
        })
      });
    } catch (e) {
      console.error('Error saving terminal preferences:', e);
    }
  };

  const fetchModels = async () => {
    if (!selectedProfile) return;
    if (!selectedProfile.api_key && !selectedProfile.id) {
      alert('Please enter an API Key first.');
      return;
    }
    setIsFetchingModels(true);
    try {
      const res = await fetch('/api/models/fetch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          profile_id: selectedProfile.id,
          api_key: selectedProfile.api_key,
          base_url: selectedProfile.base_url,
          api_format: selectedProfile.api_format
        })
      });
      const data = await res.json();
      if (data.success && data.models && data.models.length > 0) {
        setModelOptions(data.models);
        setHasFetchedModels(true);
        if (!selectedProfile.model_name || !data.models.includes(selectedProfile.model_name)) {
          setSelectedProfile(prev => prev ? { ...prev, model_name: data.models[0] } : null);
        }
      } else {
        setHasFetchedModels(false);
        alert('Failed to fetch models. Please check if your API Key and Base URL are correct.');
      }
    } catch (e) {
      console.error(e);
      setHasFetchedModels(false);
      alert('Error fetching models: ' + e);
    } finally {
      setIsFetchingModels(false);
    }
  };

  const loadPermissions = async () => {
    try {
      const res = await fetch('/api/permissions');
      const data = await res.json();
      setPermissions(data);
    } catch (e) {
      console.error('Error loading permissions:', e);
    }
  };

  const handleRevokePermission = async (command: string, scope: 'session' | 'project') => {
    try {
      const res = await fetch('/api/permissions/revoke', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ command, scope })
      });
      if (res.ok) {
        loadPermissions();
      }
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    if (isOpen && activeSettingsTab === 'permissions') {
      loadPermissions();
    }
  }, [isOpen, activeSettingsTab]);

  const loadProfiles = async () => {
    try {
      const res = await fetch('/api/profiles');
      const data = await res.json();
      setProfiles(data.profiles);
      setActiveId(data.active_profile_id);
      if (data.active_profile_id && !selectedProfile) {
        const active = data.profiles.find((p: Profile) => p.id === data.active_profile_id);
        if (active) setSelectedProfile(active);
      }
    } catch (e) {
      console.error('Error loading profiles:', e);
    }
  };

  useEffect(() => {
    if (isOpen) {
      loadProfiles();
      loadPreferences();
    }
  }, [isOpen]);

  const getSelectableModels = () => {
    const list = [...modelOptions];
    if (!hasFetchedModels && selectedProfile?.model_name && !list.includes(selectedProfile.model_name)) {
      list.unshift(selectedProfile.model_name);
    }
    return list;
  };

  if (!isOpen) return null;

  const handleSelectProfile = (profile: Profile) => {
    setSelectedProfile(profile);
    setTestResult(null);
    if (profile.model_name) {
      setHasFetchedModels(true);
      setModelOptions([profile.model_name]);
    } else {
      setHasFetchedModels(false);
      setModelOptions([]);
    }
  };

  const handleCreateNewProfile = () => {
    const newProfile: Profile = {
      name: 'New Custom Profile',
      api_key: '',
      base_url: 'https://api.openai.com/v1',
      model_name: '',
      api_format: 'openai'
    };
    setSelectedProfile(newProfile);
    setTestResult(null);
    setHasFetchedModels(false);
    setModelOptions([]);
  };

  const handleSwitchActive = async (id: string) => {
    try {
      const res = await fetch('/api/profiles/active', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id })
      });
      if (res.ok) {
        setActiveId(id);
        onProfileChanged();
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleSaveProfile = async () => {
    if (!selectedProfile) return;
    try {
      const res = await fetch('/api/profiles', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(selectedProfile)
      });
      const data = await res.json();
      if (data.success) {
        await loadProfiles();
        setSelectedProfile(data.profile);
        onProfileChanged();
        alert('Profile saved successfully!');
      }
    } catch (e) {
      alert('Failed to save profile: ' + e);
    }
  };

  const handleDeleteProfile = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm('Are you sure you want to delete this profile?')) return;
    try {
      const res = await fetch(`/api/profiles/${id}`, {
        method: 'DELETE'
      });
      if (res.ok) {
        if (selectedProfile?.id === id) {
          setSelectedProfile(null);
        }
        loadProfiles();
        onProfileChanged();
      }
    } catch (err) {
      console.error(err);
    }
  };

  const handleTestConnection = async () => {
    if (!selectedProfile) return;
    setTesting(true);
    setTestResult(null);
    try {
      const res = await fetch('/api/test-connection', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(selectedProfile)
      });
      const data = await res.json();
      setTestResult({
        success: data.success,
        message: data.message
      });
    } catch (err) {
      setTestResult({
        success: false,
        message: String(err)
      });
    } finally {
      setTesting(false);
    }
  };

  // New handler for scanning bugs
  const handleScanBugs = async () => {
    setScanning(true);
    setBugReport('');
    try {
      const res = await fetch('/api/scan-bugs', { method: 'POST' });
      const data = await res.json();
      if (data.success && data.report) {
        setBugReport(data.report);
      } else {
        setBugReport('Failed to generate bug report: ' + (data.message || 'Unknown error'));
      }
    } catch (e) {
      setBugReport('Error scanning for bugs: ' + String(e));
    } finally {
      setScanning(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="w-[850px] h-[550px] flex flex-col bg-[#111318] border border-white/5 rounded-xl shadow-2xl overflow-hidden font-sans">
        
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-white/5 bg-[#14171f]">
          <h2 className="text-lg font-semibold text-white flex items-center gap-2">
            <ShieldCheck className="text-violet-400 w-5 h-5" />
            DevPilot Settings
          </h2>
          <button onClick={onClose} className="p-1 rounded hover:bg-white/5 text-gray-400 hover:text-white transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Subheader Switcher tabs */}
        <div className="flex bg-[#14171f] px-6 border-b border-white/5 gap-4">
          <button
            onClick={() => setActiveSettingsTab('profiles')}
            className={`py-2 text-xs font-semibold border-b-2 transition-all ${
              activeSettingsTab === 'profiles' 
                ? 'border-violet-500 text-white' 
                : 'border-transparent text-gray-400 hover:text-gray-200'
            }`}
          >
            Provider Profiles
          </button>
          <button
            onClick={() => setActiveSettingsTab('permissions')}
            className={`py-2 text-xs font-semibold border-b-2 transition-all ${
              activeSettingsTab === 'permissions' 
                ? 'border-violet-500 text-white' 
                : 'border-transparent text-gray-400 hover:text-gray-200'
            }`}
          >
            Terminal Permissions
          </button>
          <button
            onClick={() => setActiveSettingsTab('preferences')}
            className={`py-2 text-xs font-semibold border-b-2 transition-all ${
              activeSettingsTab === 'preferences' 
                ? 'border-violet-500 text-white' 
                : 'border-transparent text-gray-400 hover:text-gray-200'
            }`}
          >
            General Preferences
          </button>
          <button
            onClick={() => setActiveSettingsTab('terminal')}
            className={`py-2 text-xs font-semibold border-b-2 transition-all ${
              activeSettingsTab === 'terminal'
                ? 'border-violet-500 text-white'
                : 'border-transparent text-gray-400 hover:text-gray-200'
            }`}
          >
            Terminal
          </button>
        </div>

        {/* Content */}
        {activeSettingsTab === 'profiles' && (
          <div className="flex-1 flex overflow-hidden">
            
            {/* Sidebar - Profiles List */}
            <div className="w-1/3 border-r border-white/5 bg-[#0e1014] p-4 flex flex-col justify-between">
              <div className="flex-1 overflow-y-auto space-y-2 pr-1">
                <div className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Profiles</div>
                {profiles.map((p) => (
                  <div
                    key={p.id}
                    onClick={() => handleSelectProfile(p)}
                    className={`group flex items-center justify-between p-3 rounded-lg cursor-pointer border transition-all ${
                      selectedProfile?.id === p.id
                        ? 'bg-violet-600/10 border-violet-500/40 text-white'
                        : 'bg-white/5 border-transparent hover:bg-white/10 hover:border-white/5 text-gray-300'
                    }`}
                  >
                    <div className="flex flex-col min-w-0">
                      <span className="text-sm font-medium truncate">{p.name}</span>
                      <span className="text-xs text-gray-500 truncate">{p.model_name}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          if (p.id) handleSwitchActive(p.id);
                        }}
                        className={`p-1 rounded text-xs transition-colors ${
                          activeId === p.id
                            ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                            : 'opacity-0 group-hover:opacity-100 hover:bg-white/5 text-gray-400 hover:text-white'
                        }`}
                        title={activeId === p.id ? "Active Profile" : "Set Active"}
                      >
                        {activeId === p.id ? <Check className="w-3.5 h-3.5" /> : "Use"}
                      </button>
                      <button
                        onClick={(e) => p.id && handleDeleteProfile(p.id, e)}
                        className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-red-500/20 text-gray-400 hover:text-red-400 transition-all"
                        title="Delete Profile"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>

              <button
                onClick={handleCreateNewProfile}
                className="mt-4 flex items-center justify-center gap-2 w-full py-2.5 rounded-lg border border-dashed border-white/10 hover:border-violet-500/40 hover:bg-violet-600/5 text-sm text-gray-400 hover:text-violet-400 transition-all font-medium"
              >
                <Plus className="w-4 h-4" /> Add Profile
              </button>
            </div>

            {/* Configuration Form */}
            <div className="flex-1 bg-[#111318] p-6 overflow-y-auto">
              {selectedProfile ? (
                <div className="space-y-4">
                  <h3 className="text-base font-semibold text-white border-b border-white/5 pb-2 mb-4">
                    {selectedProfile.id ? 'Edit Profile' : 'Configure New Profile'}
                  </h3>

                  {/* Profile Name & API Format */}
                  <div className="grid grid-cols-2 gap-4">
                    <div className="flex flex-col gap-1.5">
                      <label className="text-xs font-semibold text-gray-400">Profile Name</label>
                      <input
                        type="text"
                        value={selectedProfile.name}
                        onChange={(e) => setSelectedProfile({ ...selectedProfile, name: e.target.value })}
                        className="w-full px-3 py-2 bg-[#171922] border border-white/5 rounded-lg text-sm text-white focus:outline-none focus:border-violet-500 focus:ring-1 focus:ring-violet-500"
                        placeholder="e.g. My Anthropic Profile"
                      />
                    </div>

                    <div className="flex flex-col gap-1.5">
                      <label className="text-xs font-semibold text-gray-400">API Format</label>
                      <select
                        value={selectedProfile.api_format}
                        onChange={(e) => {
                          const fmt = e.target.value as 'openai' | 'anthropic' | 'google';
                          let defaultUrl = selectedProfile.base_url;
                          if (fmt === 'google') {
                            defaultUrl = 'https://generativelanguage.googleapis.com/v1beta/openai/';
                          } else if (fmt === 'anthropic') {
                            defaultUrl = 'https://api.anthropic.com/v1';
                          } else {
                            defaultUrl = 'https://api.openai.com/v1';
                          }
                          setSelectedProfile({
                            ...selectedProfile,
                            api_format: fmt,
                            base_url: defaultUrl,
                            model_name: ''
                          });
                          setHasFetchedModels(false);
                          setModelOptions([]);
                        }}
                        className="w-full px-3 py-2 bg-[#171922] border border-white/5 rounded-lg text-sm text-white focus:outline-none focus:border-violet-500"
                      >
                        <option value="openai">OpenAI Compatible</option>
                        <option value="anthropic">Anthropic Messages</option>
                        <option value="google">Google Gemini</option>
                      </select>
                    </div>
                  </div>

                  {/* Base URL & API Key */}
                  <div className="grid grid-cols-2 gap-4">
                    <div className="flex flex-col gap-1.5">
                      <label className="text-xs font-semibold text-gray-400">Base URL</label>
                      <input
                        type="text"
                        value={selectedProfile.base_url}
                        onChange={(e) => {
                          setSelectedProfile({ ...selectedProfile, base_url: e.target.value });
                          setHasFetchedModels(false);
                          setModelOptions([]);
                        }}
                        className="w-full px-3 py-2 bg-[#171922] border border-white/5 rounded-lg text-sm text-white focus:outline-none focus:border-violet-500 focus:ring-1 focus:ring-violet-500"
                        placeholder="e.g. https://api.openai.com/v1"
                      />
                    </div>

                    <div className="flex flex-col gap-1.5">
                      <label className="text-xs font-semibold text-gray-400 flex justify-between">
                        <span>API Key (encrypted)</span>
                        {selectedProfile.id && <span className="text-[10px] text-gray-500">Leave unchanged</span>}
                      </label>
                      <input
                        type="password"
                        value={selectedProfile.api_key}
                        onChange={(e) => {
                          setSelectedProfile({ ...selectedProfile, api_key: e.target.value });
                          setHasFetchedModels(false);
                          setModelOptions([]);
                        }}
                        className="w-full px-3 py-2 bg-[#171922] border border-white/5 rounded-lg text-sm text-white focus:outline-none focus:border-violet-500 focus:ring-1 focus:ring-violet-500"
                        placeholder={selectedProfile.id ? "••••••••••••••••" : "Paste your API key here"}
                      />
                    </div>
                  </div>

                   {/* Model Selection area */}
                   <div className="mt-4 pt-4 border-t border-white/5 flex flex-col gap-3">
                     <div className="flex flex-col gap-1.5">
                       <div className="text-xs font-semibold text-gray-400 flex justify-between items-center">
                         <span>Model Name</span>
                         <div className="flex gap-2.5">
                           {hasFetchedModels ? (
                             <button
                               type="button"
                               onClick={() => {
                                 setHasFetchedModels(false);
                                 setModelOptions([]);
                               }}
                               className="text-[10px] text-violet-400 hover:text-violet-350 cursor-pointer"
                             >
                               Edit Manually
                             </button>
                           ) : (
                             <button
                               type="button"
                               onClick={fetchModels}
                               disabled={isFetchingModels}
                               className="text-[10px] text-violet-400 hover:text-violet-350 disabled:opacity-50 flex items-center gap-1 cursor-pointer"
                             >
                               <RefreshCw className={`w-3 h-3 ${isFetchingModels ? 'animate-spin' : ''}`} />
                               {isFetchingModels ? 'Fetching Models...' : 'Fetch & List Models'}
                             </button>
                           )}
                         </div>
                       </div>
                       
                       {hasFetchedModels && getSelectableModels().length > 0 ? (
                         <select
                           value={selectedProfile.model_name}
                           onChange={(e) => setSelectedProfile({ ...selectedProfile, model_name: e.target.value })}
                           className="w-full px-3 py-2 bg-[#171922] border border-white/5 rounded-lg text-sm text-white focus:outline-none focus:border-violet-500 focus:ring-1 focus:ring-violet-500 font-mono"
                         >
                           {getSelectableModels().map((model) => (
                             <option key={model} value={model}>
                               {model}
                             </option>
                           ))}
                         </select>
                       ) : (
                         <div className="flex gap-2">
                           <input
                             type="text"
                             value={selectedProfile.model_name}
                             onChange={(e) => setSelectedProfile({ ...selectedProfile, model_name: e.target.value })}
                             className="flex-1 px-3 py-2 bg-[#171922] border border-white/5 rounded-lg text-sm text-white focus:outline-none focus:border-violet-500 focus:ring-1 focus:ring-violet-500 font-mono"
                             placeholder="Type model name..."
                           />
                         </div>
                       )}
                     </div>
                   </div>

                  {/* Test Connection Results */}
                  {testResult && (
                    <div className={`p-3 rounded-lg border text-xs flex gap-2 items-start ${
                      testResult.success 
                        ? 'bg-emerald-500/5 border-emerald-500/20 text-emerald-400' 
                        : 'bg-red-500/5 border-red-500/20 text-red-400'
                    }`}>
                      {testResult.success ? (
                        <>
                          <Check className="w-4 h-4 mt-0.5 shrink-0" />
                          <div>
                            <strong>Success!</strong> Connection verified successfully.
                          </div>
                        </>
                      ) : (
                        <>
                          <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
                          <div>
                            <strong>Verification Failed:</strong>
                            <p className="mt-1 font-mono text-[10px] whitespace-pre-wrap">{testResult.message}</p>
                          </div>
                        </>
                      )}
                    </div>
                  )}

                  {/* Form Buttons */}
                  <div className="flex justify-between items-center pt-4 border-t border-white/5 mt-6">
                    <button
                      onClick={handleTestConnection}
                      disabled={testing}
                      className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-white/5 border border-white/5 text-xs text-gray-300 hover:text-white hover:bg-white/10 hover:border-white/10 transition-all font-medium disabled:opacity-50"
                    >
                      {testing ? (
                        <>
                          <RefreshCw className="w-3.5 h-3.5 animate-spin" /> Testing...
                        </>
                      ) : (
                        <>
                          <RefreshCw className="w-3.5 h-3.5" /> Test Connection
                        </>
                      )}
                    </button>

                    <div className="flex gap-2">
                      <button
                        onClick={() => handleSelectProfile(profiles.find((p) => p.id === selectedProfile.id) || selectedProfile)}
                        className="px-4 py-2 bg-transparent text-xs text-gray-400 hover:text-white transition-colors"
                      >
                        Reset
                      </button>
                      <button
                        onClick={handleSaveProfile}
                        className="px-4 py-2 bg-violet-600 hover:bg-violet-500 text-xs text-white rounded-lg transition-colors font-medium"
                      >
                        Save Configuration
                      </button>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="h-full flex flex-col items-center justify-center text-center text-gray-500">
                  <ShieldCheck className="w-12 h-12 text-gray-600 mb-2" />
                  <p className="text-sm">Select a profile on the left or create a new one to begin configuration.</p>
                </div>
              )}
            </div>
            
          </div>
        )}
        {activeSettingsTab === 'permissions' && (
          <div className="flex-1 bg-[#111318] p-6 overflow-y-auto flex flex-col min-h-0">
            <h3 className="text-base font-semibold text-white border-b border-white/5 pb-2 mb-4 shrink-0">
              Granted Terminal Command Permissions
            </h3>
            
            <div className="flex-1 overflow-y-auto space-y-4 pr-1 text-xs">
              {/* Project Perms */}
              <div className="space-y-2">
                <div className="text-[10px] font-bold text-violet-400 uppercase tracking-wider">
                  Project Permissions (Saved on Disk)
                </div>
                {permissions.project.length === 0 ? (
                  <div className="text-gray-500 italic p-3 bg-black/15 border border-white/5 rounded-lg">
                    No persistent command permissions granted for this project yet.
                  </div>
                ) : (
                  <div className="border border-white/5 rounded-lg overflow-hidden divide-y divide-white/5">
                    {permissions.project.map((cmd) => (
                      <div key={cmd} className="flex justify-between items-center p-3 bg-black/15 font-mono text-[10px]">
                        <span className="text-gray-200 truncate pr-4">{cmd}</span>
                        <button
                          onClick={() => handleRevokePermission(cmd, 'project')}
                          className="px-2.5 py-1 bg-red-650/10 hover:bg-red-500/20 text-red-400 hover:text-red-300 font-semibold border border-red-500/10 rounded transition-all cursor-pointer"
                        >
                          Revoke
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Session Perms */}
              <div className="space-y-2">
                <div className="text-[10px] font-bold text-violet-400 uppercase tracking-wider">
                  Session Permissions (In-Memory Only)
                </div>
                {permissions.session.length === 0 ? (
                  <div className="text-gray-500 italic p-3 bg-black/15 border border-white/5 rounded-lg">
                    No temporary session command permissions granted yet.
                  </div>
                ) : (
                  <div className="border border-white/5 rounded-lg overflow-hidden divide-y divide-white/5">
                    {permissions.session.map((cmd) => (
                      <div key={cmd} className="flex justify-between items-center p-3 bg-black/15 font-mono text-[10px]">
                        <span className="text-gray-200 truncate pr-4">{cmd}</span>
                        <button
                          onClick={() => handleRevokePermission(cmd, 'session')}
                          className="px-2.5 py-1 bg-red-650/10 hover:bg-red-500/20 text-red-400 hover:text-red-300 font-semibold border border-red-500/10 rounded transition-all cursor-pointer"
                        >
                          Revoke
                        </button>
                      </div>
                    ))}
                  </div>
                )}
            </div>
          </div>
        </div>
      )}
        {activeSettingsTab === 'preferences' && (
          <div className="flex-1 flex flex-col overflow-y-auto p-6 space-y-6">
            <div className="text-sm font-semibold text-white border-b border-white/5 pb-2">
              Workspace Settings & Preferences
            </div>

            {/* Folder Exclusions */}
            <div className="space-y-2">
              <label className="text-xs font-semibold text-gray-400 block">
                Excluded Folders & Files
              </label>
              <span className="text-[10px] text-gray-500 block">
                Comma-separated list of directories/files to hide from the explorer and code search indexing:
              </span>
              <input
                type="text"
                value={excludeList.join(', ')}
                onChange={(e) => {
                  const items = e.target.value.split(',').map(item => item.trim()).filter(Boolean);
                  setExcludeList(items);
                  savePreferences(items, autoBackupEnabled);
                }}
                className="w-full px-3 py-2 bg-[#171922] border border-white/5 rounded-lg text-sm text-white focus:outline-none focus:border-violet-500 focus:ring-1 focus:ring-violet-500 font-mono"
                placeholder="e.g. .git, node_modules, dist"
              />
            </div>

            {/* Agent Model Selection */}
            <div className="space-y-2">
              <label className="text-xs font-semibold text-gray-400 block">
                Global Agent Model Selection
              </label>
              <span className="text-[10px] text-gray-500 block">
                Choose which model the step-by-step Multi-Agent Router uses by default for all tasks:
              </span>
              <select
                value={agentModelName}
                onChange={(e) => {
                  const val = e.target.value;
                  setAgentModelName(val);
                  savePreferences(excludeList, autoBackupEnabled, val);
                }}
                className="w-full px-3 py-2 bg-[#171922] border border-white/5 rounded-lg text-sm text-white focus:outline-none focus:border-violet-500 focus:ring-1 focus:ring-violet-500 font-mono"
              >
                <option value="">Use Active Profile Model (Default)</option>
                {getSelectableModels().map((model) => (
                  <option key={model} value={model}>
                    {model}
                  </option>
                ))}
              </select>
            </div>

            {/* Per-Agent Model Configurations */}
            <div className="space-y-2">
              <label className="text-xs font-semibold text-gray-400 block">
                Per-Agent Model Configurations
              </label>
              <span className="text-[10px] text-gray-500 block mb-2">
                Configure specific models for individual agents. When set to 'Default', the agent uses the global Agent Model Selection or the Active Profile Model.
              </span>
              <div className="grid grid-cols-2 gap-3 max-h-[220px] overflow-y-auto pr-1 border border-white/5 rounded-lg p-3 bg-black/20">
                {AGENTS_LIST.map((agent) => (
                  <AgentModelRow
                    key={agent}
                    label={agent}
                    value={agentModels[agent] || ''}
                    selectableModels={getSelectableModels()}
                    onChange={(val) => {
                      const updated = { ...agentModels, [agent]: val };
                      setAgentModels(updated);
                      savePreferences(excludeList, autoBackupEnabled, agentModelName, updated);
                    }}
                  />
                ))}
              </div>
            </div>

            {/* Auto Backups */}
            <div className="flex items-start gap-3 bg-white/2 border border-white/5 rounded-xl p-4">
              <input
                type="checkbox"
                id="auto-backups-check"
                checked={autoBackupEnabled}
                onChange={(e) => {
                  const val = e.target.checked;
                  setAutoBackupEnabled(val);
                  savePreferences(excludeList, val);
                }}
                className="accent-violet-500 mt-1 cursor-pointer w-4 h-4 rounded"
              />
              <div className="flex flex-col gap-1">
                <label htmlFor="auto-backups-check" className="text-xs font-semibold text-white cursor-pointer select-none">
                  Enable Automatic File Backups
                </label>
                <span className="text-[10px] text-gray-500">
                  When enabled, DevPilot automatically creates a local timestamped backup of modified files inside the <code className="font-mono text-violet-400">.devpilot/backups/</code> folder before writing new code blocks. This enables easy revert actions.
                </span>
              </div>
            </div>

            {/* Bug Scan Section */}
            <div className="space-y-2">
              <label className="text-xs font-semibold text-gray-400 flex items-center gap-1">
                <Bug className="w-4 h-4 text-red-400" />
                Workspace Bug Scan
              </label>
              <div className="flex gap-2 items-center">
                <button
                  onClick={handleScanBugs}
                  disabled={scanning}
                  className="px-3 py-1 rounded bg-red-600 hover:bg-red-500 text-white text-xs disabled:opacity-50 flex items-center gap-1"
                >
                  {scanning ? (
                    <>
                      <RefreshCw className="w-3 h-3 animate-spin" /> Scanning...
                    </>
                  ) : (
                    <>
                      <Bug className="w-3 h-3" /> Scan for Bugs
                    </>
                  )}
                </button>
              </div>
              {bugReport && (
                <pre className="mt-2 p-3 bg-[#171922] border border-white/5 rounded-lg text-xs text-white whitespace-pre-wrap overflow-x-auto max-h-40">
                  {bugReport}
                </pre>
              )}
            </div>

          </div>
        )}

        {activeSettingsTab === 'terminal' && (
          <div className="flex-1 overflow-y-auto p-6 space-y-6">
            <div className="space-y-1">
              <h3 className="text-sm font-semibold text-white">Terminal Preferences</h3>
              <p className="text-[10px] text-gray-500">Configure default terminal shell and display settings. Changes are saved immediately.</p>
            </div>

            {/* Default Shell */}
            <div className="space-y-2">
              <label className="text-xs font-semibold text-gray-400">Default Shell</label>
              <p className="text-[10px] text-gray-600">Selected shell is used for every new terminal pane, including after page reload.</p>
              <select
                id="default-shell-select"
                value={defaultShell}
                onChange={(e) => {
                  const val = e.target.value;
                  setDefaultShell(val);
                  saveTerminalPrefs(val, termFontSize, termScrollback);
                }}
                className="bg-black/40 text-xs border border-white/10 hover:border-violet-500/40 focus:border-violet-500/60 rounded-lg px-3 py-1.5 text-white focus:outline-none transition-all cursor-pointer w-52"
              >
                <option value="">Default (OS shell)</option>
                <option value="powershell">PowerShell</option>
                <option value="cmd">CMD</option>
                <option value="bash">Bash</option>
                <option value="sh">Sh</option>
              </select>
            </div>

            {/* Font Size */}
            <div className="space-y-2">
              <label className="text-xs font-semibold text-gray-400">
                Font Size — <span className="text-violet-400 font-mono">{termFontSize}px</span>
              </label>
              <div className="flex items-center gap-3">
                <input
                  id="term-font-size"
                  type="range"
                  min={8}
                  max={32}
                  step={1}
                  value={termFontSize}
                  onChange={(e) => {
                    const val = parseInt(e.target.value, 10);
                    setTermFontSize(val);
                  }}
                  onMouseUp={(e) => {
                    const val = parseInt((e.target as HTMLInputElement).value, 10);
                    saveTerminalPrefs(defaultShell, val, termScrollback);
                  }}
                  className="accent-violet-500 w-48 cursor-pointer"
                />
                <span className="text-[10px] text-gray-500 w-6">{termFontSize}</span>
              </div>
            </div>

            {/* Scrollback */}
            <div className="space-y-2">
              <label className="text-xs font-semibold text-gray-400">Scrollback Buffer</label>
              <p className="text-[10px] text-gray-600">Lines of terminal history kept in memory (500 – 100,000).</p>
              <div className="flex items-center gap-2">
                <input
                  id="term-scrollback"
                  type="number"
                  min={500}
                  max={100000}
                  step={500}
                  value={termScrollback}
                  onChange={(e) => {
                    const val = Math.max(500, Math.min(100000, parseInt(e.target.value, 10) || 5000));
                    setTermScrollback(val);
                  }}
                  onBlur={() => saveTerminalPrefs(defaultShell, termFontSize, termScrollback)}
                  className="bg-black/40 text-xs border border-white/10 hover:border-violet-500/40 focus:border-violet-500/60 rounded-lg px-3 py-1.5 text-white focus:outline-none transition-all w-28"
                />
                <span className="text-[10px] text-gray-500">lines</span>
              </div>
            </div>

            <div className="pt-2 border-t border-white/5">
              <p className="text-[10px] text-gray-600">
                💡 Font size and scrollback take effect on <strong className="text-gray-400">new terminal panes</strong> — existing open panes keep their current settings.
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}