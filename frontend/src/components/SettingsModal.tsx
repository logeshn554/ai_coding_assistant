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
          className="flex-1 px-2.5 py-1 bg-[#171922] border border-white/5 rounded-md text-xs text-white focus:outline-none focus:border-[#4C8DFF]"
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
            className="flex-1 px-2.5 py-1 bg-[#171922] border border-white/5 rounded-md text-xs text-white focus:outline-none focus:border-[#4C8DFF] font-mono"
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
  api_format?: string;
}

const DEFAULT_PROVIDER_URLS: Record<string, string> = {
  openai: 'https://api.openai.com/v1',
  anthropic: 'https://api.anthropic.com/v1',
  google: 'https://generativelanguage.googleapis.com/v1beta/openai/',
  groq: 'https://api.groq.com/openai/v1',
  deepseek: 'https://api.deepseek.com/v1',
  nvidia: 'https://integrate.api.nvidia.com/v1',
  openrouter: 'https://openrouter.ai/api/v1',
  mistral: 'https://api.mistral.ai/v1',
  ollama: 'http://localhost:11434/v1',
  other: 'https://api.openai.com/v1'
};

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  onProfileChanged: () => void;
}

export default function SettingsModal({ isOpen, onClose, onProfileChanged }: SettingsModalProps) {
  const [activeSettingsTab, setActiveSettingsTab] = useState<'profiles' | 'agent_behavior' | 'permissions' | 'preferences' | 'terminal'>('profiles');
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
  const [agentProfiles, setAgentProfiles] = useState<Record<string, string>>({});
  const [imageAnalysisModel, setImageAnalysisModel] = useState<string>('');
  const [imageAnalysisMode, setImageAnalysisMode] = useState<string>('auto');
  const [secondaryAgentModel, setSecondaryAgentModel] = useState<string>('');
  const [devpilotRpm, setDevpilotRpm] = useState<number>(15);
  const [concurrencyMode, setConcurrencyMode] = useState<string>('parallel');
  const [temperature, setTemperature] = useState<number>(1.0);
  const [topP, setTopP] = useState<number>(1.0);
  const [maxTokens, setMaxTokens] = useState<number>(16384);
  const [seed, setSeed] = useState<number>(42);
  const [stream, setStream] = useState<boolean>(true);
  const [decisionEngine, setDecisionEngine] = useState<string>('rule_based');
  const [dualLlmMode, setDualLlmMode] = useState<boolean>(false);

  // Agent Behavior & Local Permissions State
  const [artifactReviewPolicy, setArtifactReviewPolicy] = useState<string>('Always Ask');
  const [fileAccessRules, setFileAccessRules] = useState<any[]>([]);
  const [networkAccessRules, setNetworkAccessRules] = useState<any[]>([]);
  const [terminalCommandRules, setTerminalCommandRules] = useState<any[]>([]);
  const [unsandboxedCommandRules, setUnsandboxedCommandRules] = useState<any[]>([]);
  const [mcpToolRules, setMcpToolRules] = useState<any[]>([]);
  const [activeRuleModal, setActiveRuleModal] = useState<'file' | 'network' | 'terminal' | 'unsandboxed' | 'mcp' | null>(null);
  const [newRuleInput, setNewRuleInput] = useState('');
  const [newRuleType, setNewRuleType] = useState('allow');

  // New state for bug scanning
  const [bugReport, setBugReport] = useState<string>('');
  const [scanning, setScanning] = useState<boolean>(false);

  // Terminal preference state
  const [defaultShell, setDefaultShell] = useState<string>('');
  const [termFontSize, setTermFontSize] = useState<number>(13);
  const [termScrollback, setTermScrollback] = useState<number>(5000);

  // Theme + editor state
  const [activeTheme, setActiveTheme] = useState<string>(() =>
    localStorage.getItem('devpilot_theme') || 'dark'
  );
  const [editorFontSize, setEditorFontSize] = useState<number>(() =>
    parseInt(localStorage.getItem('devpilot_editor_font_size') || '13', 10)
  );
  const [aiInlineEnabled, setAiInlineEnabled] = useState<boolean>(() =>
    localStorage.getItem('devpilot_ai_inline_completions') !== 'false'
  );

  const applyTheme = (theme: string) => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('devpilot_theme', theme);
    setActiveTheme(theme);
    window.dispatchEvent(new Event('devpilot-theme-change'));
  };


  const loadPreferences = async () => {
    try {
      const res = await fetch('/api/config/settings');
      if (res.ok) {
        const data = await res.json();
        setExcludeList(Array.isArray(data?.exclude_list) ? data.exclude_list : []);
        setAutoBackupEnabled(data?.auto_backup_enabled ?? true);
        setAgentModelName(data?.agent_model_name || '');
        setSecondaryAgentModel(data?.secondary_agent_model || '');
        setAgentModels(data?.agent_models && typeof data.agent_models === 'object' ? data.agent_models : {});
        setAgentProfiles(data?.agent_profiles && typeof data.agent_profiles === 'object' ? data.agent_profiles : {});
        setImageAnalysisModel(data?.image_analysis_model || '');
        setImageAnalysisMode(data?.image_analysis_mode || 'auto');
        if (data?.devpilot_rpm !== undefined) setDevpilotRpm(data.devpilot_rpm);
        if (data?.concurrency_mode !== undefined) setConcurrencyMode(data.concurrency_mode);
        if (data?.temperature !== undefined) setTemperature(data.temperature);
        if (data?.top_p !== undefined) setTopP(data.top_p);
        if (data?.max_tokens !== undefined) setMaxTokens(data.max_tokens);
        if (data?.seed !== undefined) setSeed(data.seed);
        if (data?.stream !== undefined) setStream(data.stream);
        if (data?.decision_engine !== undefined) setDecisionEngine(data.decision_engine);
        if (data?.dual_llm_mode !== undefined) setDualLlmMode(data.dual_llm_mode);
        // Terminal preferences
        setDefaultShell(data?.default_shell || '');
        if (data?.terminal_font_size) setTermFontSize(data.terminal_font_size);
        if (data?.terminal_scrollback) setTermScrollback(data.terminal_scrollback);
        // Agent Behavior & Local Permissions
        if (data?.artifact_review_policy) setArtifactReviewPolicy(data.artifact_review_policy);
        setFileAccessRules(Array.isArray(data?.file_access_rules) ? data.file_access_rules : []);
        setNetworkAccessRules(Array.isArray(data?.network_access_rules) ? data.network_access_rules : []);
        setTerminalCommandRules(Array.isArray(data?.terminal_command_rules) ? data.terminal_command_rules : []);
        setUnsandboxedCommandRules(Array.isArray(data?.unsandboxed_command_rules) ? data.unsandboxed_command_rules : []);
        setMcpToolRules(Array.isArray(data?.mcp_tool_rules) ? data.mcp_tool_rules : []);
      }
    } catch (e) {
      console.error('Error loading preferences:', e);
    }
  };

  const savePreferences = async (
    newExclusions: string[],
    newBackup: boolean,
    newAgentModel?: string,
    newAgentModels?: Record<string, string>,
    policyOverride?: string,
    fileRulesOverride?: any[],
    netRulesOverride?: any[],
    termRulesOverride?: any[],
    unsandboxedRulesOverride?: any[],
    mcpRulesOverride?: any[],
    newImgModel?: string,
    newRpm?: number,
    newConcurrency?: string,
    newAgentProfiles?: Record<string, string>,
    newTemperature?: number,
    newTopP?: number,
    newMaxTokens?: number,
    newSeed?: number,
    newStream?: boolean,
    newDecisionEngine?: string,
    newDualLlmMode?: boolean,
    newImgMode?: string,
    newSecAgentModel?: string
  ) => {
    try {
      await fetch('/api/config/settings', {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({
          exclude_list: newExclusions,
          auto_backup_enabled: newBackup,
          agent_model_name: newAgentModel !== undefined ? newAgentModel : agentModelName,
          secondary_agent_model: newSecAgentModel !== undefined ? newSecAgentModel : secondaryAgentModel,
          agent_models: newAgentModels !== undefined ? newAgentModels : agentModels,
          agent_profiles: newAgentProfiles !== undefined ? newAgentProfiles : agentProfiles,
          image_analysis_model: newImgModel !== undefined ? newImgModel : imageAnalysisModel,
          image_analysis_mode: newImgMode !== undefined ? newImgMode : imageAnalysisMode,
          default_shell: defaultShell,
          terminal_font_size: termFontSize,
          terminal_scrollback: termScrollback,
          artifact_review_policy: policyOverride !== undefined ? policyOverride : artifactReviewPolicy,
          file_access_rules: fileRulesOverride !== undefined ? fileRulesOverride : fileAccessRules,
          network_access_rules: netRulesOverride !== undefined ? netRulesOverride : networkAccessRules,
          terminal_command_rules: termRulesOverride !== undefined ? termRulesOverride : terminalCommandRules,
          unsandboxed_command_rules: unsandboxedRulesOverride !== undefined ? unsandboxedRulesOverride : unsandboxedCommandRules,
          mcp_tool_rules: mcpRulesOverride !== undefined ? mcpRulesOverride : mcpToolRules,
          devpilot_rpm: newRpm !== undefined ? newRpm : devpilotRpm,
          concurrency_mode: newConcurrency !== undefined ? newConcurrency : concurrencyMode,
          temperature: newTemperature !== undefined ? newTemperature : temperature,
          top_p: newTopP !== undefined ? newTopP : topP,
          max_tokens: newMaxTokens !== undefined ? newMaxTokens : maxTokens,
          seed: newSeed !== undefined ? newSeed : seed,
          stream: newStream !== undefined ? newStream : stream,
          decision_engine: newDecisionEngine !== undefined ? newDecisionEngine : decisionEngine,
          dual_llm_mode: newDualLlmMode !== undefined ? newDualLlmMode : dualLlmMode,
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
        headers: getAuthHeaders(),
        body: JSON.stringify({
          exclude_list: excludeList,
          auto_backup_enabled: autoBackupEnabled,
          agent_model_name: agentModelName,
          agent_models: agentModels,
          agent_profiles: agentProfiles,
          default_shell: shell,
          terminal_font_size: fontSize,
          terminal_scrollback: scrollback,
          artifact_review_policy: artifactReviewPolicy,
          file_access_rules: fileAccessRules,
          network_access_rules: networkAccessRules,
          terminal_command_rules: terminalCommandRules,
          unsandboxed_command_rules: unsandboxedCommandRules,
          mcp_tool_rules: mcpToolRules,
          devpilot_rpm: devpilotRpm,
          concurrency_mode: concurrencyMode,
          temperature: temperature,
          top_p: topP,
          max_tokens: maxTokens,
          seed: seed,
          stream: stream,
          decision_engine: decisionEngine,
          dual_llm_mode: dualLlmMode,
        })
      });
    } catch (e) {
      console.error('Error saving terminal preferences:', e);
    }
  };


  const getAuthHeaders = (): Record<string, string> => {
    const token = localStorage.getItem('session_token') || '';
    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
    return headers;
  };

  const fetchModels = async () => {
    if (!selectedProfile) return;
    setIsFetchingModels(true);
    try {
      const res = await fetch('/api/models/fetch', {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({
          profile_id: selectedProfile.id,
          api_key: selectedProfile.api_key,
          base_url: selectedProfile.base_url,
          api_format: selectedProfile.api_format || 'openai'
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
      const res = await fetch('/api/permissions', { headers: getAuthHeaders() });
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
        headers: getAuthHeaders(),
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
    if (isOpen) {
      loadProfiles();
      loadPreferences();
      loadPermissions();
    }
  }, [isOpen]);

  const loadProfiles = async () => {
    try {
      const res = await fetch('/api/profiles', { headers: getAuthHeaders() });
      if (res.ok) {
        const data = await res.json();
        const profList = Array.isArray(data?.profiles) ? data.profiles : [];
        setProfiles(profList);
        setActiveId(data?.active_profile_id || '');
        if (data?.active_profile_id && !selectedProfile) {
          const active = profList.find((p: Profile) => p.id === data.active_profile_id);
          if (active) setSelectedProfile(active);
        } else if (profList.length > 0 && !selectedProfile) {
          setSelectedProfile(profList[0]);
        }
      }
    } catch (e) {
      console.error('Error loading profiles:', e);
      setProfiles([]);
    }
  };

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
        headers: getAuthHeaders(),
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
    if (!selectedProfile.name?.trim()) {
      alert('Please enter a Profile Name.');
      return;
    }
    if (!selectedProfile.base_url?.trim()) {
      alert('Please enter a Base URL.');
      return;
    }
    try {
      // Send explicit clean payload — avoid undefined fields failing Pydantic validation
      const payload = {
        id: selectedProfile.id ?? null,
        name: selectedProfile.name.trim(),
        api_key: selectedProfile.api_key ?? '',
        base_url: selectedProfile.base_url.trim(),
        model_name: selectedProfile.model_name ?? '',
        api_format: selectedProfile.api_format ?? 'openai'
      };
      const res = await fetch('/api/profiles', {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (data.success && data.profile) {
        const savedId = data.profile.id;
        if (savedId) {
          await fetch('/api/profiles/active', {
            method: 'POST',
            headers: getAuthHeaders(),
            body: JSON.stringify({ id: savedId })
          });
        }
        await loadProfiles();
        setSelectedProfile(data.profile);
        onProfileChanged();
        alert('Profile saved & set active successfully!');
      } else {
        alert('Failed to save profile: ' + (data.detail || data.message || 'Unknown error'));
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
        method: 'DELETE',
        headers: getAuthHeaders()
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
      // Always send all fields including api_format and profile id
      // so backend can correctly resolve masked keys from saved profile
      const payload = {
        id: selectedProfile.id,
        name: selectedProfile.name,
        api_key: selectedProfile.api_key,
        base_url: selectedProfile.base_url,
        model_name: selectedProfile.model_name,
        api_format: selectedProfile.api_format || 'openai'
      };
      const res = await fetch('/api/test-connection', {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify(payload)
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
            <ShieldCheck className="text-[#4C8DFF] w-5 h-5" />
            DevPilot Settings
          </h2>
          <button onClick={onClose} className="p-1 rounded hover:bg-white/5 text-gray-400 hover:text-white transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Subheader Switcher tabs */}
        <div className="flex bg-[#14171f] px-6 border-b border-white/5 gap-4 overflow-x-auto">
          <button
            onClick={() => setActiveSettingsTab('profiles')}
            className={`py-2 text-xs font-semibold border-b-2 transition-all whitespace-nowrap ${
              activeSettingsTab === 'profiles' 
                ? 'border-[#4C8DFF] text-white' 
                : 'border-transparent text-gray-400 hover:text-gray-200'
            }`}
          >
            Provider Profiles
          </button>
          <button
            onClick={() => setActiveSettingsTab('agent_behavior')}
            className={`py-2 text-xs font-semibold border-b-2 transition-all whitespace-nowrap ${
              activeSettingsTab === 'agent_behavior' 
                ? 'border-[#4C8DFF] text-white' 
                : 'border-transparent text-gray-400 hover:text-gray-200'
            }`}
          >
            Agent & Local Permissions
          </button>
          <button
            onClick={() => setActiveSettingsTab('permissions')}
            className={`py-2 text-xs font-semibold border-b-2 transition-all whitespace-nowrap ${
              activeSettingsTab === 'permissions' 
                ? 'border-[#4C8DFF] text-white' 
                : 'border-transparent text-gray-400 hover:text-gray-200'
            }`}
          >
            Terminal Permissions
          </button>
          <button
            onClick={() => setActiveSettingsTab('keybindings' as any)}
            className={`py-2 text-xs font-semibold border-b-2 transition-all whitespace-nowrap ${
              (activeSettingsTab as string) === 'keybindings'
                ? 'border-[#4C8DFF] text-white'
                : 'border-transparent text-gray-400 hover:text-gray-200'
            }`}
          >
            Keyboard Shortcuts
          </button>
          <button
            onClick={() => setActiveSettingsTab('preferences')}
            className={`py-2 text-xs font-semibold border-b-2 transition-all whitespace-nowrap ${
              activeSettingsTab === 'preferences' 
                ? 'border-[#4C8DFF] text-white' 
                : 'border-transparent text-gray-400 hover:text-gray-200'
            }`}
          >
            General Preferences
          </button>
          <button
            onClick={() => setActiveSettingsTab('terminal')}
            className={`py-2 text-xs font-semibold border-b-2 transition-all whitespace-nowrap ${
              activeSettingsTab === 'terminal'
                ? 'border-[#4C8DFF] text-white'
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
                {(profiles || []).map((p) => (
                  <div
                    key={p.id}
                    onClick={() => handleSelectProfile(p)}
                    className={`group flex items-center justify-between p-3 rounded-lg cursor-pointer border transition-all ${
                      selectedProfile?.id === p.id
                        ? 'bg-[#3B7AE8]/10 border-[#4C8DFF]/40 text-white'
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
                className="mt-4 flex items-center justify-center gap-2 w-full py-2.5 rounded-lg border border-dashed border-white/10 hover:border-[#4C8DFF]/40 hover:bg-[#3B7AE8]/5 text-sm text-gray-400 hover:text-[#4C8DFF] transition-all font-medium"
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

                  {/* Profile Name & API Provider */}
                  <div className="grid grid-cols-2 gap-4">
                    <div className="flex flex-col gap-1.5">
                      <label className="text-xs font-semibold text-gray-400">Profile Name</label>
                      <input
                        type="text"
                        value={selectedProfile.name}
                        onChange={(e) => setSelectedProfile({ ...selectedProfile, name: e.target.value })}
                        className="w-full px-3 py-2 bg-[#171922] border border-white/5 rounded-lg text-sm text-white focus:outline-none focus:border-[#4C8DFF] focus:ring-1 focus:ring-[#4C8DFF]"
                        placeholder="e.g. My Anthropic Profile"
                      />
                    </div>

                    <div className="flex flex-col gap-1.5">
                      <label className="text-xs font-semibold text-gray-400">API Provider / Format</label>
                      <select
                        value={selectedProfile.api_format || 'openai'}
                        onChange={(e) => {
                          const fmt = e.target.value;
                          const defaultUrl = DEFAULT_PROVIDER_URLS[fmt] || selectedProfile.base_url || 'https://api.openai.com/v1';
                          setSelectedProfile({
                            ...selectedProfile,
                            api_format: fmt,
                            base_url: defaultUrl,
                            model_name: ''
                          });
                          setHasFetchedModels(false);
                          setModelOptions([]);
                        }}
                        className="w-full px-3 py-2 bg-[#171922] border border-white/5 rounded-lg text-sm text-white focus:outline-none focus:border-[#4C8DFF]"
                      >
                        <option value="openai">OpenAI</option>
                        <option value="anthropic">Anthropic (Claude)</option>
                        <option value="google">Google Gemini</option>
                        <option value="groq">Groq</option>
                        <option value="deepseek">DeepSeek</option>
                        <option value="nvidia">NVIDIA NIM</option>
                        <option value="openrouter">OpenRouter</option>
                        <option value="mistral">Mistral AI</option>
                        <option value="ollama">Ollama (Local)</option>
                        <option value="other">Other / Custom API</option>
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
                        className="w-full px-3 py-2 bg-[#171922] border border-white/5 rounded-lg text-sm text-white focus:outline-none focus:border-[#4C8DFF] focus:ring-1 focus:ring-[#4C8DFF]"
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
                        className="w-full px-3 py-2 bg-[#171922] border border-white/5 rounded-lg text-sm text-white focus:outline-none focus:border-[#4C8DFF] focus:ring-1 focus:ring-[#4C8DFF]"
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
                               className="text-[10px] text-[#4C8DFF] hover:text-[#4C8DFF] cursor-pointer"
                             >
                               Edit Manually
                             </button>
                           ) : (
                             <button
                               type="button"
                               onClick={fetchModels}
                               disabled={isFetchingModels}
                               className="text-[10px] text-[#4C8DFF] hover:text-[#4C8DFF] disabled:opacity-50 flex items-center gap-1 cursor-pointer"
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
                           className="w-full px-3 py-2 bg-[#171922] border border-white/5 rounded-lg text-sm text-white focus:outline-none focus:border-[#4C8DFF] focus:ring-1 focus:ring-[#4C8DFF] font-mono"
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
                             className="flex-1 px-3 py-2 bg-[#171922] border border-white/5 rounded-lg text-sm text-white focus:outline-none focus:border-[#4C8DFF] focus:ring-1 focus:ring-[#4C8DFF] font-mono"
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
                        className="px-4 py-2 bg-[#3B7AE8] hover:bg-[#4C8DFF] text-xs text-white rounded-lg transition-colors font-medium"
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
        {activeSettingsTab === 'agent_behavior' && (
          <div className="flex-1 bg-[#111318] p-6 overflow-y-auto space-y-6">
            
            {/* Agent Behavior */}
            <div className="space-y-3">
              <h3 className="text-sm font-semibold text-white border-b border-white/5 pb-2">
                Agent Behavior
              </h3>
              <div className="p-4 bg-[#171922] border border-white/5 rounded-xl flex items-center justify-between shadow-sm">
                <div className="flex flex-col gap-1 max-w-[70%]">
                  <span className="text-xs font-semibold text-gray-200">Artifact Review Policy</span>
                  <span className="text-[11px] text-gray-400 leading-normal">
                    Specifies Agent's behavior when asking for review on artifacts, which are documents it creates to enable a richer conversation experience.
                  </span>
                </div>
                <select
                  value={artifactReviewPolicy}
                  onChange={(e) => {
                    const val = e.target.value;
                    setArtifactReviewPolicy(val);
                    savePreferences(excludeList, autoBackupEnabled, undefined, undefined, val);
                  }}
                  className="px-3 py-1.5 bg-[#0d0e14] border border-white/10 rounded-lg text-xs text-white focus:outline-none focus:border-[#4C8DFF] cursor-pointer min-w-[130px]"
                >
                  <option value="Always Ask">Always Ask</option>
                  <option value="On Demand">On Demand</option>
                  <option value="Never Ask">Never Ask</option>
                </select>
              </div>
            </div>

            {/* Local Permissions */}
            <div className="space-y-3 pt-2">
              <div className="flex flex-col gap-1">
                <h3 className="text-sm font-semibold text-white border-b border-white/5 pb-2">
                  Local Permissions
                </h3>
                <p className="text-[11px] text-gray-400">
                  Inherits from <span className="text-[#4C8DFF] cursor-pointer hover:underline">global settings</span>. Local permissions have higher priority. <span className="text-[#4C8DFF] cursor-pointer hover:underline">Learn more</span>.
                </p>
              </div>

              <div className="border border-white/5 rounded-xl overflow-hidden divide-y divide-white/5 bg-[#171922]/60">
                {/* Card 1: File Access Rules */}
                <div className="p-4 flex items-center justify-between hover:bg-white/[0.02] transition-colors">
                  <div className="flex flex-col gap-0.5 max-w-[75%]">
                    <span className="text-xs font-semibold text-gray-200">File Access Rules</span>
                    <span className="text-[11px] text-gray-400">Configure allowed and denied paths for file reads and writes.</span>
                  </div>
                  <button
                    onClick={() => { setNewRuleInput(''); setNewRuleType('allow'); setActiveRuleModal('file'); }}
                    className="px-4 py-1.5 bg-white/5 hover:bg-white/10 border border-white/10 rounded-lg text-xs text-gray-200 font-medium transition-all cursor-pointer"
                  >
                    Open
                  </button>
                </div>

                {/* Card 2: Network Access Rules */}
                <div className="p-4 flex items-center justify-between hover:bg-white/[0.02] transition-colors">
                  <div className="flex flex-col gap-0.5 max-w-[75%]">
                    <span className="text-xs font-semibold text-gray-200">Network Access Rules</span>
                    <span className="text-[11px] text-gray-400">Configure allowed and denied URLs for reading.</span>
                  </div>
                  <button
                    onClick={() => { setNewRuleInput(''); setNewRuleType('allow'); setActiveRuleModal('network'); }}
                    className="px-4 py-1.5 bg-white/5 hover:bg-white/10 border border-white/10 rounded-lg text-xs text-gray-200 font-medium transition-all cursor-pointer"
                  >
                    Open
                  </button>
                </div>

                {/* Card 3: Terminal Commands */}
                <div className="p-4 flex items-center justify-between hover:bg-white/[0.02] transition-colors">
                  <div className="flex flex-col gap-0.5 max-w-[75%]">
                    <span className="text-xs font-semibold text-gray-200">Terminal Commands</span>
                    <span className="text-[11px] text-gray-400">Configure allowed terminal commands.</span>
                  </div>
                  <button
                    onClick={() => { setNewRuleInput(''); setNewRuleType('allow'); setActiveRuleModal('terminal'); }}
                    className="px-4 py-1.5 bg-white/5 hover:bg-white/10 border border-white/10 rounded-lg text-xs text-gray-200 font-medium transition-all cursor-pointer"
                  >
                    Open
                  </button>
                </div>

                {/* Card 4: Commands Outside Sandbox */}
                <div className="p-4 flex items-center justify-between hover:bg-white/[0.02] transition-colors">
                  <div className="flex flex-col gap-0.5 max-w-[75%]">
                    <span className="text-xs font-semibold text-gray-200">Commands Outside Sandbox</span>
                    <span className="text-[11px] text-gray-400">Configure allowed commands outside the sandbox.</span>
                  </div>
                  <button
                    onClick={() => { setNewRuleInput(''); setNewRuleType('allow'); setActiveRuleModal('unsandboxed'); }}
                    className="px-4 py-1.5 bg-white/5 hover:bg-white/10 border border-white/10 rounded-lg text-xs text-gray-200 font-medium transition-all cursor-pointer"
                  >
                    Open
                  </button>
                </div>

                {/* Card 5: MCP Tools */}
                <div className="p-4 flex items-center justify-between hover:bg-white/[0.02] transition-colors">
                  <div className="flex flex-col gap-0.5 max-w-[75%]">
                    <span className="text-xs font-semibold text-gray-200">MCP Tools</span>
                    <span className="text-[11px] text-gray-400">Configure external tools via Model Context Protocol.</span>
                  </div>
                  <button
                    onClick={() => { setNewRuleInput(''); setNewRuleType('allow'); setActiveRuleModal('mcp'); }}
                    className="px-4 py-1.5 bg-white/5 hover:bg-white/10 border border-white/10 rounded-lg text-xs text-gray-200 font-medium transition-all cursor-pointer"
                  >
                    Open
                  </button>
                </div>
              </div>
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
                <div className="text-[10px] font-bold text-[#4C8DFF] uppercase tracking-wider">
                  Project Permissions (Saved on Disk)
                </div>
                {(!permissions?.project || permissions.project.length === 0) ? (
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
                <div className="text-[10px] font-bold text-[#4C8DFF] uppercase tracking-wider">
                  Session Permissions (In-Memory Only)
                </div>
                {(!permissions?.session || permissions.session.length === 0) ? (
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

        {(activeSettingsTab as string) === 'keybindings' && (

          <div className="flex-1 bg-[#111318] p-6 overflow-y-auto flex flex-col min-h-0 space-y-4">
            <div className="flex items-center justify-between border-b border-white/5 pb-3">
              <div>
                <h3 className="text-sm font-semibold text-white">Keyboard Shortcuts & Keybindings</h3>
                <p className="text-[10px] text-gray-400">View and customize global keybindings for quick navigation.</p>
              </div>
            </div>

            <div className="border border-white/5 rounded-xl overflow-hidden divide-y divide-white/5 bg-[#171922]/60 font-mono text-xs">
              {[
                { command: 'Quick Open File', keybinding: 'Ctrl + P', defaultKey: 'Ctrl + P' },
                { command: 'Workspace Symbol Search', keybinding: 'Ctrl + T', defaultKey: 'Ctrl + T' },
                { command: 'File Symbol Search', keybinding: 'Ctrl + Shift + O', defaultKey: 'Ctrl + Shift + O' },
                { command: 'Toggle Integrated Terminal', keybinding: 'Ctrl + `', defaultKey: 'Ctrl + `' },
                { command: 'Global Text Search', keybinding: 'Ctrl + Shift + F', defaultKey: 'Ctrl + Shift + F' },
                { command: 'Command Palette', keybinding: 'Ctrl + Shift + P', defaultKey: 'Ctrl + Shift + P' },
                { command: 'AI Inline Suggestions', keybinding: 'Tab / Esc', defaultKey: 'Tab / Esc' }
              ].map((kb, idx) => (
                <div key={idx} className="p-3 flex items-center justify-between hover:bg-white/[0.02]">
                  <span className="font-sans text-xs font-medium text-gray-200">{kb.command}</span>
                  <span className="px-2 py-0.5 rounded bg-black/40 border border-white/10 text-[#4C8DFF] font-bold text-[11px]">
                    {kb.keybinding}
                  </span>
                </div>
              ))}
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
                className="w-full px-3 py-2 bg-[#171922] border border-white/5 rounded-lg text-sm text-white focus:outline-none focus:border-[#4C8DFF] focus:ring-1 focus:ring-[#4C8DFF] font-mono"
                placeholder="e.g. .git, node_modules, dist"
              />
            </div>

            {/* Agent Models Selection (Primary & Secondary for Dual-LLM) */}
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <label className="text-xs font-semibold text-gray-400 block">
                  Primary Agent Model (Brain / Planner)
                </label>
                <span className="text-[10px] text-gray-500 block">
                  Default model used for high-level reasoning and step-by-step task orchestration:
                </span>
                <select
                  value={agentModelName}
                  onChange={(e) => {
                    const val = e.target.value;
                    setAgentModelName(val);
                    savePreferences(excludeList, autoBackupEnabled, val);
                  }}
                  className="w-full px-3 py-2 bg-[#171922] border border-white/5 rounded-lg text-sm text-white focus:outline-none focus:border-[#4C8DFF] focus:ring-1 focus:ring-[#4C8DFF] font-mono"
                >
                  <option value="">Use Active Profile Model (Default)</option>
                  {getSelectableModels().map((model) => (
                    <option key={model} value={model}>
                      {model}
                    </option>
                  ))}
                </select>
              </div>

              <div className="space-y-2">
                <label className="text-xs font-semibold text-gray-400 block">
                  Secondary Agent Model (Generator / Executor)
                </label>
                <span className="text-[10px] text-gray-500 block">
                  Secondary model used for tool execution in Dual-LLM mode:
                </span>
                <select
                  value={secondaryAgentModel}
                  onChange={(e) => {
                    const val = e.target.value;
                    setSecondaryAgentModel(val);
                    savePreferences(excludeList, autoBackupEnabled, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, val);
                  }}
                  className="w-full px-3 py-2 bg-[#171922] border border-white/5 rounded-lg text-sm text-white focus:outline-none focus:border-[#4C8DFF] focus:ring-1 focus:ring-[#4C8DFF] font-mono"
                >
                  <option value="">Use Primary Model (Default)</option>
                  {getSelectableModels().map((model) => (
                    <option key={model} value={model}>
                      {model}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* Image & Visual Analysis Settings */}
            <div className="space-y-3 p-3.5 bg-white/[0.02] border border-white/5 rounded-xl">
              <label className="text-xs font-semibold text-gray-300 block">
                Image & Visual Analysis Settings
              </label>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <span className="text-[11px] font-semibold text-gray-400">Analysis Mode</span>
                  <span className="text-[10px] text-gray-500 block">
                    Choose whether to ask Vision AI model, use OCR to extract text, or auto fallback:
                  </span>
                  <select
                    value={imageAnalysisMode}
                    onChange={(e) => {
                      const val = e.target.value;
                      setImageAnalysisMode(val);
                      savePreferences(excludeList, autoBackupEnabled, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, val);
                    }}
                    className="w-full px-3 py-2 bg-[#171922] border border-white/5 rounded-lg text-sm text-white focus:outline-none focus:border-[#4C8DFF]"
                  >
                    <option value="auto">Auto (Vision Model with OCR Fallback)</option>
                    <option value="model">Ask Vision Model in Coding</option>
                    <option value="ocr">Use OCR to Extract Text Only</option>
                  </select>
                </div>

                <div className="space-y-1.5">
                  <span className="text-[11px] font-semibold text-gray-400">Vision Model</span>
                  <span className="text-[10px] text-gray-500 block">
                    Specific model for analyzing image attachments & screenshots:
                  </span>
                  <select
                    value={imageAnalysisModel}
                    disabled={imageAnalysisMode === 'ocr'}
                    onChange={(e) => {
                      const val = e.target.value;
                      setImageAnalysisModel(val);
                      savePreferences(excludeList, autoBackupEnabled, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, val);
                    }}
                    className="w-full px-3 py-2 bg-[#171922] border border-white/5 rounded-lg text-sm text-white focus:outline-none focus:border-[#4C8DFF] font-mono disabled:opacity-40"
                  >
                    <option value="">Active Profile Model (Default)</option>
                    {getSelectableModels().map((model) => (
                      <option key={model} value={model}>
                        {model}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
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

            {/* Per-Agent Connection Profiles (API Keys) */}
            <div className="space-y-2">
              <label className="text-xs font-semibold text-gray-400 block">
                Per-Agent Connection Profiles (API Keys)
              </label>
              <span className="text-[10px] text-gray-500 block mb-2">
                Configure specific connection profiles (API keys & endpoints) for individual agents. When set to 'Default', the agent uses the active profile.
              </span>
              <div className="grid grid-cols-2 gap-3 max-h-[220px] overflow-y-auto pr-1 border border-white/5 rounded-lg p-3 bg-black/20">
                {AGENTS_LIST.map((agent) => (
                  <div key={agent} className="flex flex-col gap-1.5 p-3 bg-white/[0.02] border border-white/5 rounded-lg">
                    <span className="text-[11px] font-semibold text-gray-300">{agent}</span>
                    <select
                      value={agentProfiles[agent] || ''}
                      onChange={(e) => {
                        const updated = { ...agentProfiles, [agent]: e.target.value };
                        setAgentProfiles(updated);
                        savePreferences(excludeList, autoBackupEnabled, agentModelName, agentModels, undefined, undefined, undefined, undefined, undefined, undefined, imageAnalysisModel, devpilotRpm, concurrencyMode, updated);
                      }}
                      className="w-full px-2.5 py-1 bg-[#171922] border border-white/5 rounded-md text-xs text-white focus:outline-none focus:border-[#4C8DFF]"
                    >
                      <option value="">Default (Active Profile)</option>
                      {profiles.map(p => (
                        <option key={p.id} value={p.id}>{p.name}</option>
                      ))}
                    </select>
                  </div>
                ))}
              </div>
            </div>

            {/* LLM Rate Limit & Execution Mode */}
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <label className="text-xs font-semibold text-gray-400 block">
                  LLM Request Rate Limit (RPM)
                </label>
                <span className="text-[10px] text-gray-500 block">
                  Maximum requests per minute. Set to 3 for free tier Anthropic/OpenAI keys.
                </span>
                <input
                  type="number"
                  min={1}
                  value={devpilotRpm}
                  onChange={(e) => {
                    const val = Math.max(1, parseInt(e.target.value, 10) || 15);
                    setDevpilotRpm(val);
                    savePreferences(excludeList, autoBackupEnabled, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, val);
                  }}
                  className="w-full px-3 py-2 bg-[#171922] border border-white/5 rounded-lg text-sm text-white focus:outline-none focus:border-[#4C8DFF] focus:ring-1 focus:ring-[#4C8DFF] font-mono"
                  placeholder="e.g. 15"
                />
              </div>

              <div className="space-y-2">
                <label className="text-xs font-semibold text-gray-400 block">
                  Execution Mode
                </label>
                <span className="text-[10px] text-gray-500 block">
                  Run specialist tasks in parallel (faster) or sequentially (safer for low RPM limits).
                </span>
                <select
                  value={concurrencyMode}
                  onChange={(e) => {
                    const val = e.target.value;
                    setConcurrencyMode(val);
                    savePreferences(excludeList, autoBackupEnabled, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, val);
                  }}
                  className="w-full px-3 py-2 bg-[#171922] border border-white/5 rounded-lg text-sm text-white focus:outline-none focus:border-[#4C8DFF] focus:ring-1 focus:ring-[#4C8DFF]"
                >
                  <option value="parallel">Parallel Execution</option>
                  <option value="sequential">Sequential (Low RPM)</option>
                </select>
              </div>
            </div>

            {/* Model Generation Parameters */}
            <div className="space-y-4 border-t border-white/5 pt-5">
              <div className="flex flex-col gap-1">
                <label className="text-xs font-semibold text-gray-400 block">
                  Model Generation Parameters
                </label>
                <span className="text-[10px] text-gray-500 block">
                  Fine-tune the output behavior, randomness, and length parameters for LLM responses.
                </span>
              </div>

              <div className="grid grid-cols-2 gap-4">
                {/* Temperature */}
                <div className="space-y-2 p-3 bg-white/[0.02] border border-white/5 rounded-lg">
                  <div className="flex justify-between items-center">
                    <span className="text-[11px] font-semibold text-gray-300">Temperature (Randomness)</span>
                    <span className="text-[11px] font-mono text-[#4C8DFF]">{temperature.toFixed(2)}</span>
                  </div>
                  <div className="flex gap-3 items-center">
                    <input
                      type="range"
                      min={0.0}
                      max={2.0}
                      step={0.1}
                      value={temperature}
                      onChange={(e) => {
                        const val = parseFloat(e.target.value);
                        setTemperature(val);
                      }}
                      onMouseUp={(e) => {
                        const val = parseFloat((e.target as HTMLInputElement).value);
                        savePreferences(excludeList, autoBackupEnabled, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, val);
                      }}
                      className="accent-[#4C8DFF] flex-1 cursor-pointer"
                    />
                  </div>
                </div>

                {/* Top P */}
                <div className="space-y-2 p-3 bg-white/[0.02] border border-white/5 rounded-lg">
                  <div className="flex justify-between items-center">
                    <span className="text-[11px] font-semibold text-gray-300">Top P (Nucleus Sampling)</span>
                    <span className="text-[11px] font-mono text-[#4C8DFF]">{topP.toFixed(2)}</span>
                  </div>
                  <div className="flex gap-3 items-center">
                    <input
                      type="range"
                      min={0.0}
                      max={1.0}
                      step={0.05}
                      value={topP}
                      onChange={(e) => {
                        const val = parseFloat(e.target.value);
                        setTopP(val);
                      }}
                      onMouseUp={(e) => {
                        const val = parseFloat((e.target as HTMLInputElement).value);
                        savePreferences(excludeList, autoBackupEnabled, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, val);
                      }}
                      className="accent-[#4C8DFF] flex-1 cursor-pointer"
                    />
                  </div>
                </div>

                {/* Max Tokens */}
                <div className="space-y-2 p-3 bg-white/[0.02] border border-white/5 rounded-lg">
                  <label className="text-[11px] font-semibold text-gray-300 block">Max Output Tokens</label>
                  <input
                    type="number"
                    min={1}
                    max={1000000}
                    value={maxTokens}
                    onChange={(e) => {
                      const val = Math.max(1, parseInt(e.target.value, 10) || 16384);
                      setMaxTokens(val);
                    }}
                    onBlur={(e) => {
                      const val = Math.max(1, parseInt(e.target.value, 10) || 16384);
                      savePreferences(excludeList, autoBackupEnabled, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, val);
                    }}
                    className="w-full px-2.5 py-1.5 bg-[#171922] border border-white/5 rounded-md text-xs text-white focus:outline-none focus:border-[#4C8DFF] font-mono"
                  />
                </div>

                {/* Seed */}
                <div className="space-y-2 p-3 bg-white/[0.02] border border-white/5 rounded-lg">
                  <label className="text-[11px] font-semibold text-gray-300 block">Random Seed</label>
                  <input
                    type="number"
                    value={seed ?? ''}
                    placeholder="None (random)"
                    onChange={(e) => {
                      const val = e.target.value ? parseInt(e.target.value, 10) : undefined;
                      setSeed(val as any);
                    }}
                    onBlur={(e) => {
                      const val = e.target.value ? parseInt(e.target.value, 10) : undefined;
                      savePreferences(excludeList, autoBackupEnabled, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, val);
                    }}
                    className="w-full px-2.5 py-1.5 bg-[#171922] border border-white/5 rounded-md text-xs text-white focus:outline-none focus:border-[#4C8DFF] font-mono"
                  />
                </div>
              </div>

              {/* Streaming responses checkbox */}
              <div className="flex items-start gap-3 bg-white/2 border border-white/5 rounded-xl p-4">
                <input
                  type="checkbox"
                  id="model-stream-check"
                  checked={stream}
                  onChange={(e) => {
                    const val = e.target.checked;
                    setStream(val);
                    savePreferences(excludeList, autoBackupEnabled, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, val);
                  }}
                  className="accent-[#4C8DFF] mt-1 cursor-pointer w-4 h-4 rounded"
                />
                <div className="flex flex-col gap-1">
                  <label htmlFor="model-stream-check" className="text-xs font-semibold text-white cursor-pointer select-none">
                    Stream Model Responses
                  </label>
                  <span className="text-[10px] text-gray-500">
                    When enabled, response chunks are displayed as they are generated by the model. When disabled, the complete response is displayed only after generation finishes.
                  </span>
                </div>
              </div>

              {/* File Selection Decision Engine */}
              <div className="space-y-2 p-3 bg-white/[0.02] border border-white/5 rounded-lg">
                <label className="text-xs font-semibold text-gray-400 block">
                  File Selection Decision Engine
                </label>
                <span className="text-[10px] text-gray-500 block">
                  Choose the strategy for selecting target codebase files. LLM-based selection calls the model to decide which files to write/modify.
                </span>
                <select
                  value={decisionEngine}
                  onChange={(e) => {
                    const val = e.target.value;
                    setDecisionEngine(val);
                    savePreferences(excludeList, autoBackupEnabled, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, val);
                  }}
                  className="w-full px-3 py-2 bg-[#171922] border border-white/5 rounded-lg text-sm text-white focus:outline-none focus:border-[#4C8DFF] focus:ring-1 focus:ring-[#4C8DFF]"
                >
                  <option value="rule_based">Rule-Based Heuristic (RAG)</option>
                  <option value="llm">LLM-Based Selection Engine (LLM Decides)</option>
                </select>
              </div>

              {/* Dual-LLM Execution Mode */}
              <div className="flex items-start gap-3 bg-white/2 border border-white/5 rounded-xl p-4">
                <input
                  type="checkbox"
                  id="dual-llm-mode-check"
                  checked={dualLlmMode}
                  onChange={(e) => {
                    const val = e.target.checked;
                    setDualLlmMode(val);
                    savePreferences(excludeList, autoBackupEnabled, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, val);
                  }}
                  className="accent-[#4C8DFF] mt-1 cursor-pointer w-4 h-4 rounded"
                />
                <div className="flex flex-col gap-1">
                  <label htmlFor="dual-llm-mode-check" className="text-xs font-semibold text-white cursor-pointer select-none">
                    Enable Dual-LLM Mode (Brain + Generator)
                  </label>
                  <span className="text-[10px] text-gray-500">
                    When enabled, the Brain LLM acts as high-level planner and delegates execution tasks to a separate Generator LLM, conveying context strictly through the Shared Memory.
                  </span>
                </div>
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
                className="accent-[#4C8DFF] mt-1 cursor-pointer w-4 h-4 rounded"
              />
              <div className="flex flex-col gap-1">
                <label htmlFor="auto-backups-check" className="text-xs font-semibold text-white cursor-pointer select-none">
                  Enable Automatic File Backups
                </label>
                <span className="text-[10px] text-gray-500">
                  When enabled, DevPilot automatically creates a local timestamped backup of modified files inside the <code className="font-mono text-[#4C8DFF]">.devpilot/backups/</code> folder before writing new code blocks. This enables easy revert actions.
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

            {/* ── Theme Picker ── */}
            <div className="space-y-3 border-t border-white/5 pt-5">
              <label className="text-xs font-semibold text-gray-400 block">Color Theme</label>
              <div className="grid grid-cols-5 gap-2">
                {([
                  { id: 'dark', label: 'DevPilot Dark', bg: '#0d0e14', accent: '#7c6af0', text: '#c8ccd8' },
                  { id: 'light', label: 'DevPilot Light', bg: '#f0f0f5', accent: '#6b54e8', text: '#1a1b26' },
                  { id: 'monokai', label: 'Monokai', bg: '#272822', accent: '#f92672', text: '#f8f8f2' },
                  { id: 'solarized', label: 'Solarized Dark', bg: '#002b36', accent: '#268bd2', text: '#839496' },
                  { id: 'high-contrast', label: 'High Contrast', bg: '#000000', accent: '#00ffff', text: '#ffffff' },
                ] as const).map((t) => (
                  <button
                    key={t.id}
                    onClick={() => applyTheme(t.id)}
                    title={t.label}
                    className="flex flex-col items-center gap-1.5 p-2 rounded-xl border-2 cursor-pointer transition-all"
                    style={{
                      background: t.bg,
                      borderColor: activeTheme === t.id ? t.accent : 'rgba(255,255,255,0.08)',
                      boxShadow: activeTheme === t.id ? `0 0 12px ${t.accent}55` : 'none',
                    }}
                  >
                    <div className="w-8 h-5 rounded-md" style={{ background: t.accent, opacity: 0.9 }} />
                    <span className="text-[9px] font-medium leading-tight text-center" style={{ color: t.text }}>
                      {t.label}
                    </span>
                    {activeTheme === t.id && (
                      <div className="w-2 h-2 rounded-full" style={{ background: t.accent }} />
                    )}
                  </button>
                ))}
              </div>
            </div>

            {/* ── AI Inline Completions ── */}
            <div className="flex items-start gap-3 bg-white/2 border border-white/5 rounded-xl p-4">
              <input
                type="checkbox"
                id="ai-inline-completions"
                checked={aiInlineEnabled}
                onChange={(e) => {
                  const val = e.target.checked;
                  setAiInlineEnabled(val);
                  localStorage.setItem('devpilot_ai_inline_completions', val ? 'true' : 'false');
                }}
                className="accent-[#4C8DFF] mt-1 cursor-pointer w-4 h-4 rounded"
              />
              <div className="flex flex-col gap-1">
                <label htmlFor="ai-inline-completions" className="text-xs font-semibold text-white cursor-pointer select-none">
                  AI Inline Completions (Ghost Text)
                </label>
                <span className="text-[10px] text-gray-500">
                  Show AI-powered ghost text suggestions in the editor as you type. Press Tab to accept, Escape to dismiss.
                </span>
              </div>
            </div>

            {/* ── Editor Font Size ── */}
            <div className="space-y-2 border-t border-white/5 pt-5">
              <label className="text-xs font-semibold text-gray-400">
                Editor Font Size — <span className="text-[#4C8DFF] font-mono">{editorFontSize}px</span>
              </label>
              <div className="flex items-center gap-3">
                <input
                  type="range"
                  min={10}
                  max={28}
                  step={1}
                  value={editorFontSize}
                  onChange={(e) => {
                    const val = parseInt(e.target.value, 10);
                    setEditorFontSize(val);
                    localStorage.setItem('devpilot_editor_font_size', String(val));
                    window.dispatchEvent(new CustomEvent('devpilot_editor_settings', { detail: { fontSize: val } }));
                  }}
                  className="accent-[#4C8DFF] w-48 cursor-pointer"
                />
                <span className="text-[10px] text-gray-500 w-6">{editorFontSize}</span>
              </div>
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
                className="bg-black/40 text-xs border border-white/10 hover:border-[#4C8DFF]/40 focus:border-[#4C8DFF]/60 rounded-lg px-3 py-1.5 text-white focus:outline-none transition-all cursor-pointer w-52"
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
                Font Size — <span className="text-[#4C8DFF] font-mono">{termFontSize}px</span>
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
                  className="accent-[#4C8DFF] w-48 cursor-pointer"
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
                  className="bg-black/40 text-xs border border-white/10 hover:border-[#4C8DFF]/40 focus:border-[#4C8DFF]/60 rounded-lg px-3 py-1.5 text-white focus:outline-none transition-all w-28"
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

        {/* Sub-modal Rule Editor Overlay */}
        {activeRuleModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-md">
            <div className="w-[520px] bg-[#14171f] border border-white/10 rounded-xl shadow-2xl overflow-hidden p-6 flex flex-col gap-4">
              <div className="flex items-center justify-between border-b border-white/10 pb-3">
                <h3 className="text-sm font-semibold text-white">
                  {activeRuleModal === 'file' && 'File Access Rules'}
                  {activeRuleModal === 'network' && 'Network Access Rules'}
                  {activeRuleModal === 'terminal' && 'Terminal Command Rules'}
                  {activeRuleModal === 'unsandboxed' && 'Commands Outside Sandbox Rules'}
                  {activeRuleModal === 'mcp' && 'MCP Tool Rules'}
                </h3>
                <button onClick={() => setActiveRuleModal(null)} className="p-1 rounded hover:bg-white/10 text-gray-400 hover:text-white cursor-pointer">
                  <X className="w-4 h-4" />
                </button>
              </div>

              <div className="flex gap-2 items-center">
                <input
                  type="text"
                  value={newRuleInput}
                  onChange={(e) => setNewRuleInput(e.target.value)}
                  placeholder={
                    activeRuleModal === 'file' ? 'e.g. ./src/** or /etc/config' :
                    activeRuleModal === 'network' ? 'e.g. api.openai.com or *.github.com' :
                    activeRuleModal === 'terminal' ? 'e.g. npm install or git commit' :
                    activeRuleModal === 'unsandboxed' ? 'e.g. docker run or systemctl' : 'e.g. sqlite/read_query'
                  }
                  className="flex-1 px-3 py-1.5 bg-[#0d0e14] border border-white/10 rounded-lg text-xs text-white focus:outline-none focus:border-[#4C8DFF] font-mono"
                />
                <select
                  value={newRuleType}
                  onChange={(e) => setNewRuleType(e.target.value)}
                  className="px-2.5 py-1.5 bg-[#0d0e14] border border-white/10 rounded-lg text-xs text-white focus:outline-none cursor-pointer"
                >
                  <option value="allow">Allow</option>
                  <option value="deny">Deny</option>
                </select>
                <button
                  onClick={() => {
                    if (!newRuleInput.trim()) return;
                    const newRule = { id: String(Date.now()), target: newRuleInput.trim(), type: newRuleType };
                    if (activeRuleModal === 'file') {
                      const updated = [...fileAccessRules, newRule];
                      setFileAccessRules(updated);
                      savePreferences(excludeList, autoBackupEnabled, undefined, undefined, undefined, updated);
                    } else if (activeRuleModal === 'network') {
                      const updated = [...networkAccessRules, newRule];
                      setNetworkAccessRules(updated);
                      savePreferences(excludeList, autoBackupEnabled, undefined, undefined, undefined, undefined, updated);
                    } else if (activeRuleModal === 'terminal') {
                      const updated = [...terminalCommandRules, newRule];
                      setTerminalCommandRules(updated);
                      savePreferences(excludeList, autoBackupEnabled, undefined, undefined, undefined, undefined, undefined, updated);
                    } else if (activeRuleModal === 'unsandboxed') {
                      const updated = [...unsandboxedCommandRules, newRule];
                      setUnsandboxedCommandRules(updated);
                      savePreferences(excludeList, autoBackupEnabled, undefined, undefined, undefined, undefined, undefined, undefined, updated);
                    } else if (activeRuleModal === 'mcp') {
                      const updated = [...mcpToolRules, newRule];
                      setMcpToolRules(updated);
                      savePreferences(excludeList, autoBackupEnabled, undefined, undefined, undefined, undefined, undefined, undefined, undefined, updated);
                    }
                    setNewRuleInput('');
                  }}
                  className="px-3 py-1.5 bg-[#3B7AE8] hover:bg-[#4C8DFF] text-white rounded-lg text-xs font-semibold cursor-pointer"
                >
                  Add Rule
                </button>
              </div>

              <div className="max-h-56 overflow-y-auto space-y-2 border border-white/5 rounded-lg p-2 bg-[#0d0e14]">
                {((activeRuleModal === 'file' ? fileAccessRules :
                   activeRuleModal === 'network' ? networkAccessRules :
                   activeRuleModal === 'terminal' ? terminalCommandRules :
                   activeRuleModal === 'unsandboxed' ? unsandboxedCommandRules : mcpToolRules) || []).length === 0 ? (
                  <div className="text-center text-xs text-gray-500 py-4">No custom rules added yet.</div>
                ) : (
                  ((activeRuleModal === 'file' ? fileAccessRules :
                    activeRuleModal === 'network' ? networkAccessRules :
                    activeRuleModal === 'terminal' ? terminalCommandRules :
                    activeRuleModal === 'unsandboxed' ? unsandboxedCommandRules : mcpToolRules) || []).map((r, idx) => (
                    <div key={r.id || idx} className="flex justify-between items-center p-2 bg-white/5 rounded text-xs">
                      <div className="flex items-center gap-2 font-mono text-[11px] text-gray-200">
                        <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold ${r.type === 'allow' ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' : 'bg-red-500/20 text-red-400 border border-red-500/30'}`}>
                          {r.type ? r.type.toUpperCase() : 'ALLOW'}
                        </span>
                        <span>{r.target || String(r)}</span>
                      </div>
                      <button
                        onClick={() => {
                          if (activeRuleModal === 'file') {
                            const updated = fileAccessRules.filter((_, i) => i !== idx);
                            setFileAccessRules(updated);
                            savePreferences(excludeList, autoBackupEnabled, undefined, undefined, undefined, updated);
                          } else if (activeRuleModal === 'network') {
                            const updated = networkAccessRules.filter((_, i) => i !== idx);
                            setNetworkAccessRules(updated);
                            savePreferences(excludeList, autoBackupEnabled, undefined, undefined, undefined, undefined, updated);
                          } else if (activeRuleModal === 'terminal') {
                            const updated = terminalCommandRules.filter((_, i) => i !== idx);
                            setTerminalCommandRules(updated);
                            savePreferences(excludeList, autoBackupEnabled, undefined, undefined, undefined, undefined, undefined, updated);
                          } else if (activeRuleModal === 'unsandboxed') {
                            const updated = unsandboxedCommandRules.filter((_, i) => i !== idx);
                            setUnsandboxedCommandRules(updated);
                            savePreferences(excludeList, autoBackupEnabled, undefined, undefined, undefined, undefined, undefined, undefined, updated);
                          } else if (activeRuleModal === 'mcp') {
                            const updated = mcpToolRules.filter((_, i) => i !== idx);
                            setMcpToolRules(updated);
                            savePreferences(excludeList, autoBackupEnabled, undefined, undefined, undefined, undefined, undefined, undefined, undefined, updated);
                          }
                        }}
                        className="p-1 hover:bg-red-500/20 text-gray-400 hover:text-red-400 rounded transition-colors cursor-pointer"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  ))
                )}
              </div>

              <div className="flex justify-end pt-2 border-t border-white/10">
                <button
                  onClick={() => setActiveRuleModal(null)}
                  className="px-4 py-1.5 bg-[#3B7AE8] hover:bg-[#4C8DFF] text-white text-xs font-semibold rounded-lg cursor-pointer"
                >
                  Done
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );

}