import React, { useState, useEffect } from 'react';
import { X, Plus, Trash2, ShieldCheck, Check, AlertCircle, RefreshCw } from 'lucide-react';

interface Profile {
  id?: string;
  name: string;
  api_key: string;
  base_url: string;
  model_name: string;
  api_format: 'openai' | 'anthropic';
}

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  onProfileChanged: () => void;
}

export default function SettingsModal({ isOpen, onClose, onProfileChanged }: SettingsModalProps) {
  const [activeSettingsTab, setActiveSettingsTab] = useState<'profiles' | 'permissions' | 'preferences'>('profiles');
  const [permissions, setPermissions] = useState<{ project: string[]; session: string[] }>({ project: [], session: [] });
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [activeId, setActiveId] = useState<string>('');
  const [selectedProfile, setSelectedProfile] = useState<Profile | null>(null);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);

  const [modelOptions, setModelOptions] = useState<string[]>([]);
  const [isFetchingModels, setIsFetchingModels] = useState(false);

  const [excludeList, setExcludeList] = useState<string[]>([]);
  const [autoBackupEnabled, setAutoBackupEnabled] = useState<boolean>(true);
  const [agentModelName, setAgentModelName] = useState<string>('');

  const loadPreferences = async () => {
    try {
      const res = await fetch('/api/config/settings');
      if (res.ok) {
        const data = await res.json();
        setExcludeList(data.exclude_list || []);
        setAutoBackupEnabled(data.auto_backup_enabled ?? true);
        setAgentModelName(data.agent_model_name || '');
      }
    } catch (e) {
      console.error('Error loading preferences:', e);
    }
  };

  const savePreferences = async (newExclusions: string[], newBackup: boolean, newAgentModel?: string) => {
    try {
      await fetch('/api/config/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          exclude_list: newExclusions,
          auto_backup_enabled: newBackup,
          agent_model_name: newAgentModel !== undefined ? newAgentModel : agentModelName
        })
      });
      onProfileChanged();
    } catch (e) {
      console.error('Error saving preferences:', e);
    }
  };

  const fetchModels = async () => {
    if (!selectedProfile || !selectedProfile.api_key) return;
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
      } else {
        if (selectedProfile.api_format === 'openai') {
          setModelOptions(['gpt-4o', 'gpt-4o-mini', 'o1-mini', 'o1-preview', 'llama3.1', 'deepseek-chat', 'deepseek-coder']);
        } else {
          setModelOptions(['claude-3-5-sonnet-20241022', 'claude-3-5-haiku-20241022', 'claude-3-opus-20240229']);
        }
      }
    } catch (e) {
      console.error(e);
    } finally {
      setIsFetchingModels(false);
    }
  };

  useEffect(() => {
    if (!selectedProfile) {
      setModelOptions([]);
      return;
    }
    
    if (selectedProfile.api_format === 'openai') {
      setModelOptions(['gpt-4o', 'gpt-4o-mini', 'o1-mini', 'o1-preview', 'llama3.1', 'deepseek-chat', 'deepseek-coder']);
    } else {
      setModelOptions(['claude-3-5-sonnet-20241022', 'claude-3-5-haiku-20241022', 'claude-3-opus-20240229']);
    }

    if (!selectedProfile.api_key) return;

    const delayDebounce = setTimeout(() => {
      fetchModels();
    }, 800);
    
    return () => clearTimeout(delayDebounce);
  }, [selectedProfile?.id, selectedProfile?.api_key, selectedProfile?.base_url, selectedProfile?.api_format]);

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

  // Load profiles
  const loadProfiles = async () => {
    try {
      const res = await fetch('/api/profiles');
      const data = await res.json();
      setProfiles(data.profiles);
      setActiveId(data.active_profile_id);
      
      // Auto-select active profile if none selected
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
    if (selectedProfile?.model_name && !list.includes(selectedProfile.model_name)) {
      list.unshift(selectedProfile.model_name);
    }
    return list;
  };

  if (!isOpen) return null;

  const handleSelectProfile = (profile: Profile) => {
    setSelectedProfile(profile);
    setTestResult(null);
  };

  const handleCreateNewProfile = () => {
    const newProfile: Profile = {
      name: 'New Custom Profile',
      api_key: '',
      base_url: 'https://api.openai.com/v1',
      model_name: 'gpt-4o',
      api_format: 'openai'
    };
    setSelectedProfile(newProfile);
    setTestResult(null);
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

                  {/* Profile Name */}
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

                  {/* API Format & Model Name */}
                  <div className="grid grid-cols-2 gap-4">
                    <div className="flex flex-col gap-1.5">
                      <label className="text-xs font-semibold text-gray-400">API Format</label>
                      <select
                        value={selectedProfile.api_format}
                        onChange={(e) => setSelectedProfile({ ...selectedProfile, api_format: e.target.value as 'openai' | 'anthropic' })}
                        className="w-full px-3 py-2 bg-[#171922] border border-white/5 rounded-lg text-sm text-white focus:outline-none focus:border-violet-500"
                      >
                        <option value="openai">OpenAI Compatible</option>
                        <option value="anthropic">Anthropic Messages</option>
                      </select>
                    </div>
                    
                    <div className="flex flex-col gap-1.5">
                      <label className="text-xs font-semibold text-gray-400 flex justify-between">
                        <span>Model Name</span>
                        {isFetchingModels && <span className="text-[9px] text-violet-400 animate-pulse">Checking API...</span>}
                      </label>
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
                    </div>
                  </div>

                  {/* Base URL */}
                  <div className="flex flex-col gap-1.5">
                    <label className="text-xs font-semibold text-gray-400">Base URL</label>
                    <input
                      type="text"
                      value={selectedProfile.base_url}
                      onChange={(e) => setSelectedProfile({ ...selectedProfile, base_url: e.target.value })}
                      className="w-full px-3 py-2 bg-[#171922] border border-white/5 rounded-lg text-sm text-white focus:outline-none focus:border-violet-500 focus:ring-1 focus:ring-violet-500"
                      placeholder="e.g. https://api.openai.com/v1"
                    />
                  </div>

                  {/* API Key */}
                  <div className="flex flex-col gap-1.5">
                    <label className="text-xs font-semibold text-gray-400 flex justify-between">
                      <span>API Key (encrypted on disk)</span>
                      {selectedProfile.id && <span className="text-[10px] text-gray-500">Leave unchanged to keep current key</span>}
                    </label>
                    <input
                      type="password"
                      value={selectedProfile.api_key}
                      onChange={(e) => setSelectedProfile({ ...selectedProfile, api_key: e.target.value })}
                      className="w-full px-3 py-2 bg-[#171922] border border-white/5 rounded-lg text-sm text-white focus:outline-none focus:border-violet-500 focus:ring-1 focus:ring-violet-500"
                      placeholder={selectedProfile.id ? "••••••••••••••••" : "Paste your API key here"}
                    />
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
                Agent Model Selection
              </label>
              <span className="text-[10px] text-gray-500 block">
                Choose which model the step-by-step Multi-Agent Router uses for all tasks:
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
          </div>
        )}
      </div>
    </div>
  );
}
