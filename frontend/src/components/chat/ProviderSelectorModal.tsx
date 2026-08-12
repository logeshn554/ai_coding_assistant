import React, { useState, useEffect } from 'react';
import { X, Check, Server, Eye, Wrench, Brain, Zap, RefreshCw, Key, ShieldCheck } from 'lucide-react';

export interface ProviderDashboardItem {
  id: string;
  name: string;
  base_url?: string;
  api_format?: string;
  model_name?: string;
  is_active: boolean;
  api_status: string;
  has_key: boolean;
  model_metadata?: {
    context_window?: number;
    max_output_tokens?: number;
    input_price_per_m?: number;
    output_price_per_m?: number;
    vision_supported?: boolean;
    reasoning_supported?: boolean;
    tools_supported?: boolean;
    streaming_supported?: boolean;
  };
  rpm_limit?: number;
  tpm_limit?: number;
  observed_rpm?: number;
  observed_tpm?: number;
  requests_today?: number;
  input_tokens_today?: number;
  output_tokens_today?: number;
}

interface ProviderSelectorModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSelectModel: (modelName: string, providerId?: string) => void;
  activeModelName?: string;
}

export const ProviderSelectorModal: React.FC<ProviderSelectorModalProps> = ({
  isOpen,
  onClose,
  onSelectModel,
  activeModelName = '',
}) => {
  const [providers, setProviders] = useState<ProviderDashboardItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedProviderId, setSelectedProviderId] = useState<string | null>(null);
  const [availableModels, setAvailableModels] = useState<string[]>([]);
  const [fetchingModels, setFetchingModels] = useState(false);
  const [showAddForm, setShowAddForm] = useState(false);

  // New Provider Form State (dynamically entered by user)
  const [newProvName, setNewProvName] = useState('');
  const [newProvKey, setNewProvKey] = useState('');
  const [newProvUrl, setNewProvUrl] = useState('');
  const [newProvModel, setNewProvModel] = useState('');

  const fetchDashboard = async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/providers/dashboard');
      if (res.ok) {
        const data = await res.json();
        setProviders(data.providers || []);
        if (data.active_provider_id) {
          setSelectedProviderId(data.active_provider_id);
        } else if (data.providers && data.providers.length > 0) {
          setSelectedProviderId(data.providers[0].id);
        }
      }
    } catch (err) {
      console.error('Failed to fetch provider dashboard:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      fetchDashboard();
    }
  }, [isOpen]);

  const activeProviderObj = providers.find((p) => p.id === selectedProviderId) || providers[0];

  const handleDiscoverModels = async (prov: ProviderDashboardItem) => {
    setFetchingModels(true);
    try {
      const res = await fetch('/api/models/fetch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          profile_id: prov.id,
          api_key: '',
          base_url: prov.base_url || '',
        }),
      });
      if (res.ok) {
        const data = await res.json();
        setAvailableModels(data.models || []);
      }
    } catch (err) {
      console.error('Failed to discover models:', err);
    } finally {
      setFetchingModels(false);
    }
  };

  const handleSaveProvider = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const res = await fetch('/api/profiles', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: newProvName,
          api_key: newProvKey,
          base_url: newProvUrl,
          model_name: newProvModel,
        }),
      });
      if (res.ok) {
        setShowAddForm(false);
        setNewProvKey('');
        fetchDashboard();
      }
    } catch (err) {
      console.error('Failed to save provider profile:', err);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-xs p-4 animate-[fadeIn_150ms_ease-out]">
      <div className="w-full max-w-3xl bg-[#14161d] border border-white/10 rounded-2xl shadow-2xl overflow-hidden font-sans text-zinc-200 select-none flex flex-col max-h-[85vh]">
        
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-white/10 bg-[#1a1d26]">
          <div className="flex items-center gap-2.5">
            <Server className="w-5 h-5 text-purple-400" />
            <div>
              <span className="font-bold text-sm text-zinc-100 block">AI Providers & Model Selector</span>
              <span className="text-[11px] text-zinc-400">Configure provider profiles & active chat models</span>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowAddForm(!showAddForm)}
              className="px-3 py-1.5 bg-purple-600 hover:bg-purple-500 text-white rounded-xl text-xs font-bold transition-all shadow-sm cursor-pointer"
            >
              {showAddForm ? 'View Providers' : '+ Add Provider'}
            </button>
            <button
              onClick={onClose}
              className="p-1 rounded-lg text-zinc-400 hover:text-white hover:bg-white/10 transition-colors"
            >
              <X className="w-4.5 h-4.5" />
            </button>
          </div>
        </div>

        {/* Content */}
        {showAddForm ? (
          /* Add Provider Form */
          <form onSubmit={handleSaveProvider} className="p-6 space-y-4 text-xs overflow-y-auto">
            <div className="flex items-center gap-2 text-purple-300 font-semibold mb-2">
              <Key className="w-4 h-4" />
              <span>Configure New AI Provider Profile</span>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <label className="text-zinc-400 font-semibold">Provider Name</label>
                <input
                  type="text"
                  value={newProvName}
                  onChange={(e) => setNewProvName(e.target.value)}
                  placeholder="e.g. NVIDIA, OpenRouter, OpenAI"
                  className="w-full px-3 py-2 bg-black/40 border border-white/10 rounded-xl text-white text-xs focus:outline-none focus:border-purple-500"
                  required
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-zinc-400 font-semibold">Default Model ID</label>
                <input
                  type="text"
                  value={newProvModel}
                  onChange={(e) => setNewProvModel(e.target.value)}
                  placeholder="e.g. minimaxai/minimax-m3"
                  className="w-full px-3 py-2 bg-black/40 border border-white/10 rounded-xl text-white text-xs font-mono focus:outline-none focus:border-purple-500"
                  required
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <label className="text-zinc-400 font-semibold">API Base URL</label>
              <input
                type="text"
                value={newProvUrl}
                onChange={(e) => setNewProvUrl(e.target.value)}
                placeholder="e.g. https://integrate.api.nvidia.com/v1"
                className="w-full px-3 py-2 bg-black/40 border border-white/10 rounded-xl text-white text-xs font-mono focus:outline-none focus:border-purple-500"
                required
              />
            </div>

            <div className="space-y-1.5">
              <label className="text-zinc-400 font-semibold">API Key</label>
              <input
                type="password"
                value={newProvKey}
                onChange={(e) => setNewProvKey(e.target.value)}
                placeholder="nvapi-..."
                className="w-full px-3 py-2 bg-black/40 border border-white/10 rounded-xl text-white text-xs font-mono focus:outline-none focus:border-purple-500"
              />
            </div>

            <div className="pt-2 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setShowAddForm(false)}
                className="px-4 py-2 bg-white/5 hover:bg-white/10 border border-white/10 rounded-xl text-xs font-medium text-zinc-300"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="px-5 py-2 bg-purple-600 hover:bg-purple-500 rounded-xl text-xs font-bold text-white shadow-md cursor-pointer"
              >
                Save & Connect Provider
              </button>
            </div>
          </form>
        ) : (
          /* Main Multi-Provider Dashboard & Model Selection Grid */
          <div className="flex-1 flex overflow-hidden">
            {/* Left: Provider List */}
            <div className="w-64 border-r border-white/10 p-3 space-y-2 overflow-y-auto bg-black/20">
              <div className="text-[10px] uppercase font-bold text-zinc-500 tracking-wider px-1">
                Configured Providers
              </div>
              {loading && <div className="text-[11px] text-zinc-500 px-1 italic">Loading dashboard...</div>}

              {providers.map((prov) => {
                const isSel = prov.id === selectedProviderId;
                const isOnline = prov.api_status === 'online';

                return (
                  <div
                    key={prov.id}
                    onClick={() => {
                      setSelectedProviderId(prov.id);
                      handleDiscoverModels(prov);
                    }}
                    className={`p-3 rounded-xl border transition-all cursor-pointer space-y-1 ${
                      isSel
                        ? 'bg-purple-950/40 border-purple-500/40 text-white'
                        : 'bg-white/[0.02] hover:bg-white/[0.05] border-white/5 text-zinc-300'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-xs">{prov.name}</span>
                      <span className={`w-2 h-2 rounded-full ${isOnline ? 'bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.6)]' : 'bg-zinc-600'}`} />
                    </div>

                    <div className="text-[10.5px] text-zinc-400 font-mono truncate">
                      {prov.model_name || 'default'}
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Right: Selected Provider Profile & Discovered Models */}
            {activeProviderObj ? (
              <div className="flex-1 p-5 space-y-5 overflow-y-auto">
                {/* Profile Card */}
                <div className="p-4 rounded-xl border border-white/10 bg-white/[0.02] space-y-3">
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="font-bold text-base text-white">{activeProviderObj.name} Profile</h3>
                      <span className="text-xs text-zinc-400 font-mono">{activeProviderObj.base_url}</span>
                    </div>

                    <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs font-semibold">
                      <ShieldCheck className="w-3.5 h-3.5" />
                      <span>{activeProviderObj.api_status === 'online' ? 'Connected ✓' : 'Configured'}</span>
                    </div>
                  </div>

                  {/* Model Metadata Banner */}
                  {activeProviderObj.model_metadata && (
                    <div className="grid grid-cols-3 gap-2 pt-2 border-t border-white/5 text-[11px] font-mono">
                      <div>
                        <span className="text-zinc-500 block">Context Window</span>
                        <span className="font-bold text-purple-300">
                          {activeProviderObj.model_metadata.context_window
                            ? `${Math.round(activeProviderObj.model_metadata.context_window / 1024)}K tokens`
                            : 'Unavailable'}
                        </span>
                      </div>
                      <div>
                        <span className="text-zinc-500 block">Max Output</span>
                        <span className="font-bold text-purple-300">
                          {activeProviderObj.model_metadata.max_output_tokens
                            ? `${Math.round(activeProviderObj.model_metadata.max_output_tokens / 1024)}K tokens`
                            : 'Unavailable'}
                        </span>
                      </div>
                      <div>
                        <span className="text-zinc-500 block">RPM / TPM Limits</span>
                        <span className="font-semibold text-zinc-400">
                          {activeProviderObj.rpm_limit
                            ? `${activeProviderObj.rpm_limit} RPM`
                            : 'Not provided by provider'}
                        </span>
                      </div>
                    </div>
                  )}

                  {/* Capability Badges */}
                  <div className="flex flex-wrap gap-1.5 pt-1">
                    {activeProviderObj.model_metadata?.vision_supported && (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-blue-500/20 text-blue-300 text-[10px] font-semibold border border-blue-500/30">
                        <Eye className="w-3 h-3" /> Vision
                      </span>
                    )}
                    {activeProviderObj.model_metadata?.tools_supported && (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 text-[10px] font-semibold border border-emerald-500/30">
                        <Wrench className="w-3 h-3" /> Tools
                      </span>
                    )}
                    {activeProviderObj.model_metadata?.reasoning_supported && (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-purple-500/20 text-purple-300 text-[10px] font-semibold border border-purple-500/30">
                        <Brain className="w-3 h-3" /> Reasoning
                      </span>
                    )}
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-zinc-800 text-zinc-300 text-[10px] font-semibold border border-zinc-700">
                      <Zap className="w-3 h-3 text-amber-400" /> Streaming
                    </span>
                  </div>
                </div>

                {/* Model Selection Grid */}
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold uppercase tracking-wider text-zinc-400">
                      Available Models
                    </span>
                    <button
                      onClick={() => handleDiscoverModels(activeProviderObj)}
                      disabled={fetchingModels}
                      className="flex items-center gap-1 text-[11px] font-semibold text-purple-400 hover:text-purple-300 cursor-pointer disabled:opacity-50"
                    >
                      <RefreshCw className={`w-3 h-3 ${fetchingModels ? 'animate-spin' : ''}`} />
                      <span>Auto Discover Models</span>
                    </button>
                  </div>

                  {availableModels.length > 0 ? (
                    <div className="grid grid-cols-2 gap-2">
                      {availableModels.map((mId) => {
                        const isSelected = activeModelName === mId || activeProviderObj.model_name === mId;

                        return (
                          <div
                            key={mId}
                            onClick={() => {
                              onSelectModel(mId, activeProviderObj.id);
                              onClose();
                            }}
                            className={`p-3 rounded-xl border transition-all cursor-pointer flex items-center justify-between gap-2 ${
                              isSelected
                                ? 'bg-purple-950/50 border-purple-500 text-white shadow-sm'
                                : 'bg-white/[0.02] hover:bg-white/[0.06] border-white/5 text-zinc-300'
                            }`}
                          >
                            <span className="font-mono text-xs font-semibold truncate">{mId}</span>
                            {isSelected && <Check className="w-4 h-4 text-purple-400 shrink-0" />}
                          </div>
                        );
                      })}
                    </div>
                  ) : (
                    <div
                      onClick={() => {
                        if (activeProviderObj.model_name) {
                          onSelectModel(activeProviderObj.model_name, activeProviderObj.id);
                          onClose();
                        }
                      }}
                      className="p-3 rounded-xl border border-purple-500/40 bg-purple-950/30 text-white font-mono text-xs cursor-pointer flex items-center justify-between"
                    >
                      <span>{activeProviderObj.model_name || 'No model specified'}</span>
                      <span className="text-[10px] px-2 py-0.5 rounded bg-purple-500/30 text-purple-200">Active Profile Model</span>
                    </div>
                  )}
                </div>

              </div>
            ) : (
              <div className="flex-1 flex items-center justify-center text-xs text-zinc-500">
                No provider selected.
              </div>
            )}
          </div>
        )}

      </div>
    </div>
  );
};
