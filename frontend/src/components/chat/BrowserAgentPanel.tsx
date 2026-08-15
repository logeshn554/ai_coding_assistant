import React, { useState } from 'react';
import { Globe, Camera, Terminal, Network, ShieldCheck, Play, Loader2, AlertCircle } from 'lucide-react';

export interface BrowserAgentPanelProps {
  initialUrl?: string;
  onInspectCompleted?: (data: any) => void;
}

export const BrowserAgentPanel: React.FC<BrowserAgentPanelProps> = ({
  initialUrl = 'http://localhost:5173',
  onInspectCompleted
}) => {
  const [targetUrl, setTargetUrl] = useState(initialUrl);
  const [isLoading, setIsLoading] = useState(false);
  const [activeTab, setActiveTab] = useState<'preview' | 'console' | 'network' | 'dom'>('preview');
  const [captureData, setCaptureData] = useState<any>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handleRunInspect = async () => {
    setIsLoading(true);
    setErrorMsg(null);
    try {
      const res = await fetch('/api/inspect', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: targetUrl })
      });
      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || `Inspect request failed with status ${res.status}`);
      }
      const data = await res.json();
      setCaptureData(data);
      if (onInspectCompleted) {
        onInspectCompleted(data);
      }
    } catch (err: any) {
      setErrorMsg(err.message || 'Browser inspection failed');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="browser-agent-panel bg-base-200 border border-base-300 rounded-lg p-3 space-y-3 font-sans text-xs">
      <div className="flex items-center justify-between pb-2 border-b border-base-300">
        <div className="flex items-center gap-2 font-semibold text-sm">
          <Globe className="w-4 h-4 text-primary" />
          <span>Playwright Browser Agent</span>
        </div>
        <span className="badge badge-sm badge-outline flex items-center gap-1">
          <ShieldCheck className="w-3 h-3 text-success" /> Localhost Sandbox Guarded
        </span>
      </div>

      <div className="flex items-center gap-2">
        <div className="relative flex-1">
          <input
            type="text"
            value={targetUrl}
            onChange={(e) => setTargetUrl(e.target.value)}
            placeholder="http://localhost:5173"
            className="input input-sm input-bordered w-full font-mono text-xs pr-8"
          />
        </div>
        <button
          onClick={handleRunInspect}
          disabled={isLoading}
          className="btn btn-sm btn-primary flex items-center gap-1.5"
        >
          {isLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5" />}
          <span>{isLoading ? 'Inspecting...' : 'Inspect Web App'}</span>
        </button>
      </div>

      {errorMsg && (
        <div className="alert alert-error text-xs py-2 px-3 flex items-center gap-2 rounded">
          <AlertCircle className="w-4 h-4" />
          <span>{errorMsg}</span>
        </div>
      )}

      {captureData && (
        <div className="bg-base-100 rounded border border-base-300 overflow-hidden">
          <div className="flex border-b border-base-300 bg-base-200/50">
            <button
              onClick={() => setActiveTab('preview')}
              className={`px-3 py-1.5 flex items-center gap-1 border-b-2 font-medium ${
                activeTab === 'preview' ? 'border-primary text-primary' : 'border-transparent text-base-content/70'
              }`}
            >
              <Camera className="w-3.5 h-3.5" /> Screenshot
            </button>
            <button
              onClick={() => setActiveTab('console')}
              className={`px-3 py-1.5 flex items-center gap-1 border-b-2 font-medium ${
                activeTab === 'console' ? 'border-primary text-primary' : 'border-transparent text-base-content/70'
              }`}
            >
              <Terminal className="w-3.5 h-3.5" /> Console ({captureData.capture?.console_logs?.length || 0})
            </button>
            <button
              onClick={() => setActiveTab('network')}
              className={`px-3 py-1.5 flex items-center gap-1 border-b-2 font-medium ${
                activeTab === 'network' ? 'border-primary text-primary' : 'border-transparent text-base-content/70'
              }`}
            >
              <Network className="w-3.5 h-3.5" /> Network ({captureData.capture?.network_requests?.length || 0})
            </button>
          </div>

          <div className="p-3 max-h-80 overflow-y-auto">
            {activeTab === 'preview' && (
              <div>
                {captureData.capture?.screenshot_base64 ? (
                  <img
                    src={`data:image/png;base64,${captureData.capture.screenshot_base64}`}
                    alt="Dev Server Preview"
                    className="max-w-full h-auto rounded border border-base-300 shadow-sm"
                  />
                ) : (
                  <div className="text-base-content/50 italic py-4 text-center">No visual screenshot captured.</div>
                )}
              </div>
            )}

            {activeTab === 'console' && (
              <div className="font-mono text-[11px] space-y-1">
                {(captureData.capture?.console_logs || []).map((log: any, idx: number) => (
                  <div key={idx} className="p-1 rounded bg-base-200 flex items-start gap-2">
                    <span className={`badge badge-xs uppercase ${log.type === 'error' ? 'badge-error' : 'badge-neutral'}`}>
                      {log.type || 'log'}
                    </span>
                    <span className="break-all">{log.text}</span>
                  </div>
                ))}
              </div>
            )}

            {activeTab === 'network' && (
              <div className="font-mono text-[11px] space-y-1">
                {(captureData.capture?.network_requests || []).map((req: any, idx: number) => (
                  <div key={idx} className="p-1 rounded bg-base-200 flex justify-between items-center text-[11px]">
                    <span className="truncate max-w-[260px]">{req.url}</span>
                    <span className={`badge badge-xs ${req.status >= 400 ? 'badge-error' : 'badge-success'}`}>
                      {req.status || '200'}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
