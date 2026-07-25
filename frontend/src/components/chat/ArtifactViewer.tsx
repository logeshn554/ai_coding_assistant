import React, { useState, useEffect } from 'react';
import {
  FileText, CheckCircle2, AlertTriangle, AlertCircle, Info, Sparkles,
  ExternalLink, ChevronRight, RefreshCw, Send, ShieldCheck
} from 'lucide-react';

interface Artifact {
  id: string;
  title: string;
  filename: string;
  path: string;
  content: string;
  type: string;
  request_feedback: boolean;
  summary: string;
  updated_at: number;
}

interface ArtifactViewerProps {
  workspacePath?: string;
  onOpenFile?: (path: string) => void;
  onSendMessage?: (msg: string) => void;
}

export const ArtifactViewer: React.FC<ArtifactViewerProps> = ({
  workspacePath,
  onOpenFile,
  onSendMessage
}) => {
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [activeArtifactId, setActiveArtifactId] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [feedbackSubmitted, setFeedbackSubmitted] = useState<boolean>(false);
  const [feedbackText, setFeedbackText] = useState<string>('');
  const [showFeedbackInput, setShowFeedbackInput] = useState<boolean>(false);

  const fetchArtifacts = async () => {
    setLoading(true);
    try {
      const query = workspacePath ? `?workspace_root=${encodeURIComponent(workspacePath)}` : '';
      const res = await fetch(`/api/artifacts${query}`);
      if (res.ok) {
        const data = await res.json();
        setArtifacts(data);
        if (data.length > 0 && !activeArtifactId) {
          setActiveArtifactId(data[0].id);
        }
      }
    } catch (e) {
      console.error('Failed to load artifacts:', e);
    } finally {
      setLoading(false);
    }
  };


  useEffect(() => {
    fetchArtifacts();
    const interval = setInterval(fetchArtifacts, 5000);
    return () => clearInterval(interval);
  }, [workspacePath]);

  const activeArtifact = artifacts.find(a => a.id === activeArtifactId) || artifacts[0];

  const handleApprove = async () => {
    setFeedbackSubmitted(true);
    if (onSendMessage) {
      onSendMessage("The implementation plan is approved. Proceed to execution!");
    }
  };

  const handleRequestChanges = () => {
    if (!feedbackText.trim()) return;
    setFeedbackSubmitted(true);
    if (onSendMessage) {
      onSendMessage(`I'd like the following changes to the implementation plan: ${feedbackText}`);
    }
    setFeedbackText('');
    setShowFeedbackInput(false);
  };

  // Helper to render markdown blocks and alerts
  const renderMarkdownContent = (content: string) => {
    if (!content) return null;

    const lines = content.split('\n');
    const elements: React.ReactNode[] = [];
    let inAlert = false;
    let alertType = 'NOTE';
    let alertLines: string[] = [];

    const flushAlert = (key: number) => {
      if (!inAlert) return;
      
      const alertConfig: Record<string, { bg: string; border: string; icon: any; color: string; label: string }> = {
        NOTE: { bg: 'rgba(59, 130, 246, 0.08)', border: 'rgba(59, 130, 246, 0.4)', icon: Info, color: '#60a5fa', label: 'NOTE' },
        TIP: { bg: 'rgba(16, 185, 129, 0.08)', border: 'rgba(16, 185, 129, 0.4)', icon: Sparkles, color: '#34d399', label: 'TIP' },
        IMPORTANT: { bg: 'rgba(139, 92, 246, 0.12)', border: 'rgba(139, 92, 246, 0.5)', icon: ShieldCheck, color: '#a78bfa', label: 'IMPORTANT' },
        WARNING: { bg: 'rgba(245, 158, 11, 0.1)', border: 'rgba(245, 158, 11, 0.5)', icon: AlertTriangle, color: '#fbbf24', label: 'WARNING' },
        CAUTION: { bg: 'rgba(239, 68, 68, 0.1)', border: 'rgba(239, 68, 68, 0.5)', icon: AlertCircle, color: '#f87171', label: 'CAUTION' },
      };

      const config = alertConfig[alertType] || alertConfig['NOTE'];
      const Icon = config.icon;

      elements.push(
        <div
          key={`alert-${key}`}
          className="my-3 p-3.5 rounded-xl border flex flex-col gap-1.5 transition-all duration-200 shadow-sm"
          style={{ background: config.bg, borderColor: config.border }}
        >
          <div className="flex items-center gap-2 font-semibold text-xs uppercase tracking-wider" style={{ color: config.color }}>
            <Icon className="w-4 h-4 shrink-0" />
            <span>{config.label}</span>
          </div>
          <div className="text-xs leading-relaxed text-[var(--dp-text-primary)]">
            {alertLines.join('\n')}
          </div>
        </div>
      );

      inAlert = false;
      alertLines = [];
    };

    lines.forEach((line, idx) => {
      const alertMatch = line.match(/^>\s*\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]/i);
      if (alertMatch) {
        if (inAlert) flushAlert(idx);
        inAlert = true;
        alertType = alertMatch[1].toUpperCase();
        return;
      }

      if (inAlert) {
        if (line.startsWith('>')) {
          alertLines.push(line.replace(/^>\s?/, ''));
          return;
        } else {
          flushAlert(idx);
        }
      }

      // Headers
      if (line.startsWith('# ')) {
        elements.push(<h1 key={idx} className="text-lg font-bold text-[var(--dp-text-bright)] mt-4 mb-2 pb-1 border-b border-white/10">{line.replace('# ', '')}</h1>);
      } else if (line.startsWith('## ')) {
        elements.push(<h2 key={idx} className="text-sm font-semibold text-[var(--dp-accent-hover)] mt-4 mb-2 flex items-center gap-1.5"><ChevronRight className="w-3.5 h-3.5" />{line.replace('## ', '')}</h2>);
      } else if (line.startsWith('### ')) {
        elements.push(<h3 key={idx} className="text-xs font-semibold text-[var(--dp-text-primary)] mt-3 mb-1.5">{line.replace('### ', '')}</h3>);
      } else if (line.startsWith('#### ')) {
        elements.push(<h4 key={idx} className="text-xs font-medium text-[var(--dp-text-secondary)] mt-2 mb-1">{line.replace('#### ', '')}</h4>);
      } else if (line.startsWith('- ') || line.startsWith('* ')) {
        elements.push(
          <div key={idx} className="flex items-start gap-2 text-xs text-[var(--dp-text-primary)] my-1 pl-2">
            <span className="w-1.5 h-1.5 rounded-full bg-[var(--dp-accent)] shrink-0 mt-1.5" />
            <span>{renderTextWithFileLinks(line.substring(2))}</span>
          </div>
        );
      } else if (line.trim() === '---') {
        elements.push(<hr key={idx} className="my-4 border-white/10" />);
      } else if (line.trim().length > 0) {
        elements.push(
          <p key={idx} className="text-xs leading-relaxed text-[var(--dp-text-primary)] my-1">
            {renderTextWithFileLinks(line)}
          </p>
        );
      }
    });

    if (inAlert) flushAlert(lines.length);

    return elements;
  };

  const renderTextWithFileLinks = (text: string) => {
    // Regex for file:/// links or markdown links [label](file:///...)
    const mdLinkRegex = /\[([^\]]+)\]\((file:\/\/\/[^\)]+)\)/g;
    const parts: React.ReactNode[] = [];
    let lastIndex = 0;
    let match;

    while ((match = mdLinkRegex.exec(text)) !== null) {
      if (match.index > lastIndex) {
        parts.push(text.substring(lastIndex, match.index));
      }

      const label = match[1];
      const uri = match[2];
      const cleanPath = uri.replace('file:///', '');

      parts.push(
        <button
          key={match.index}
          onClick={() => onOpenFile && onOpenFile(cleanPath)}
          className="inline-flex items-center gap-1 text-xs font-mono text-[var(--dp-accent-hover)] hover:underline bg-[var(--dp-accent-dim)] px-1.5 py-0.5 rounded transition-all"
        >
          <ExternalLink className="w-3 h-3" />
          <span>{label}</span>
        </button>
      );

      lastIndex = mdLinkRegex.lastIndex;
    }

    if (lastIndex < text.length) {
      parts.push(text.substring(lastIndex));
    }

    return parts;
  };

  return (
    <div className="flex flex-col h-full bg-[var(--dp-bg-secondary)] border-l border-[var(--dp-border)] select-none">
      {/* Top Bar / Tabs */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-[var(--dp-border)] bg-[var(--dp-bg-tertiary)]">
        <div className="flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-[var(--dp-accent-hover)]" />
          <span className="text-xs font-semibold text-[var(--dp-text-bright)] tracking-wide uppercase">
            Artifacts & Plans
          </span>
        </div>
        <button
          onClick={fetchArtifacts}
          title="Refresh Artifacts"
          className="p-1 rounded hover:bg-white/10 text-[var(--dp-text-muted)] hover:text-white transition-all"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* Artifact Tabs Header */}
      {artifacts.length > 0 && (
        <div className="flex items-center gap-1 px-2 py-1.5 border-b border-[var(--dp-border)] bg-black/20 overflow-x-auto">
          {artifacts.map(art => (
            <button
              key={art.id}
              onClick={() => setActiveArtifactId(art.id)}
              className={`
                flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium transition-all shrink-0 cursor-pointer
                ${activeArtifact?.id === art.id
                  ? 'bg-[var(--dp-accent-dim)] text-[var(--dp-accent-hover)] border border-[var(--dp-border-focus)] shadow-sm'
                  : 'text-[var(--dp-text-secondary)] hover:bg-white/5 hover:text-[var(--dp-text-primary)]'
                }
              `}
            >
              <FileText className="w-3.5 h-3.5" />
              <span>{art.title}</span>
            </button>
          ))}
        </div>
      )}

      {/* Main Content Area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3 font-sans">
        {artifacts.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center text-[var(--dp-text-muted)] p-6">
            <Sparkles className="w-8 h-8 opacity-40 mb-2 text-[var(--dp-accent)]" />
            <p className="text-xs font-medium">No active artifacts in this session.</p>
            <p className="text-[11px] opacity-70 mt-1">Switch to Plan Mode or trigger a Slash Command to generate interactive plans.</p>
          </div>
        ) : activeArtifact ? (
          <div>
            {/* Feedback Banner if requested */}
            {activeArtifact.request_feedback && !feedbackSubmitted && (
              <div className="mb-4 p-3.5 rounded-xl bg-[var(--dp-accent-dim)] border border-[var(--dp-accent)]/30 flex flex-col gap-2.5 shadow-md">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 text-xs font-semibold text-[var(--dp-accent-hover)]">
                    <Sparkles className="w-4 h-4 animate-pulse" />
                    <span>User Review & Approval Required</span>
                  </div>
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-[var(--dp-accent)]/20 text-[var(--dp-accent-hover)]">
                    Action Needed
                  </span>
                </div>
                <p className="text-xs text-[var(--dp-text-primary)] leading-relaxed">
                  Review the implementation plan below. Click <strong>Proceed</strong> to begin execution, or request specific modifications.
                </p>

                {showFeedbackInput ? (
                  <div className="flex flex-col gap-2 mt-1">
                    <textarea
                      value={feedbackText}
                      onChange={e => setFeedbackText(e.target.value)}
                      placeholder="Describe the changes you'd like to make..."
                      className="w-full h-16 p-2 rounded-lg bg-black/40 border border-white/10 text-xs text-white focus:outline-none focus:border-[var(--dp-accent)]"
                    />
                    <div className="flex items-center justify-end gap-2">
                      <button
                        onClick={() => setShowFeedbackInput(false)}
                        className="px-2.5 py-1 text-xs rounded text-[var(--dp-text-muted)] hover:text-white"
                      >
                        Cancel
                      </button>
                      <button
                        onClick={handleRequestChanges}
                        className="flex items-center gap-1 px-3 py-1 text-xs font-medium rounded-lg bg-[var(--dp-accent)] text-white hover:bg-[var(--dp-accent-hover)]"
                      >
                        <Send className="w-3 h-3" />
                        <span>Send Feedback</span>
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="flex items-center gap-2 mt-1">
                    <button
                      onClick={handleApprove}
                      className="flex-1 flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold text-white bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-400 hover:to-teal-500 shadow-md transition-all cursor-pointer"
                    >
                      <CheckCircle2 className="w-4 h-4" />
                      <span>Proceed with Plan</span>
                    </button>
                    <button
                      onClick={() => setShowFeedbackInput(true)}
                      className="px-3 py-1.5 rounded-lg text-xs font-medium text-[var(--dp-text-primary)] bg-white/5 hover:bg-white/10 border border-white/10 transition-all cursor-pointer"
                    >
                      Modify Plan
                    </button>
                  </div>
                )}
              </div>
            )}

            {feedbackSubmitted && (
              <div className="mb-4 p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/30 flex items-center gap-2 text-xs text-emerald-400">
                <CheckCircle2 className="w-4 h-4 shrink-0" />
                <span>Feedback submitted! The Antigravity Agent is executing your plan.</span>
              </div>
            )}

            {/* Artifact Content */}
            <div className="prose prose-invert max-w-none">
              {renderMarkdownContent(activeArtifact.content)}
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
};
