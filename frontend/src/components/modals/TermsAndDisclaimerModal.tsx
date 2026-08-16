import { useState, useEffect } from 'react';
import { ShieldAlert, AlertTriangle, Check, Coins, Key, Terminal, X } from 'lucide-react';

interface TermsAndDisclaimerModalProps {
  isOpen?: boolean;
  onClose?: () => void;
}

export default function TermsAndDisclaimerModal({ isOpen: externalIsOpen, onClose }: TermsAndDisclaimerModalProps = {}) {
  const [internalIsOpen, setInternalIsOpen] = useState<boolean>(() => {
    return localStorage.getItem('devpilot_terms_accepted') !== 'true';
  });
  const [hasAgreed, setHasAgreed] = useState<boolean>(false);

  useEffect(() => {
    const handleOpenTerms = () => setInternalIsOpen(true);
    window.addEventListener('devpilot-open-terms', handleOpenTerms);
    return () => window.removeEventListener('devpilot-open-terms', handleOpenTerms);
  }, []);

  const isOpen = externalIsOpen !== undefined ? externalIsOpen : internalIsOpen;

  if (!isOpen) return null;

  const handleAccept = () => {
    localStorage.setItem('devpilot_terms_accepted', 'true');
    setInternalIsOpen(false);
    if (onClose) onClose();
  };

  const isMandatoryFirstLaunch = localStorage.getItem('devpilot_terms_accepted') !== 'true';

  return (
    <div className="fixed inset-0 z-[9999] bg-black/80 backdrop-blur-md flex items-center justify-center p-4 font-sans select-none animate-[fadeIn_200ms_ease-out]">
      <div className="bg-[#141620] border border-[#2A3146] rounded-2xl w-full max-w-xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        
        {/* Header */}
        <div className="px-6 py-4 bg-[#181B28] border-b border-[#2A3146] flex items-center justify-between shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-amber-500/10 border border-amber-500/30 flex items-center justify-center text-amber-400">
              <ShieldAlert className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-white tracking-wide">Loopix — Beta Notice & Terms</h2>
              <p className="text-[11px] text-zinc-400">Please review before using the AI coding assistant</p>
            </div>
          </div>
          {!isMandatoryFirstLaunch && (
            <button
              onClick={() => {
                setInternalIsOpen(false);
                if (onClose) onClose();
              }}
              className="p-1 rounded-lg hover:bg-white/10 text-zinc-400 hover:text-white cursor-pointer"
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>

        {/* Scrollable Terms Content */}
        <div className="p-6 overflow-y-auto space-y-4 text-xs text-zinc-300 leading-relaxed font-normal divide-y divide-white/5">
          
          {/* Section 1: Beta Disclaimer */}
          <div className="space-y-2">
            <div className="flex items-center gap-2 font-bold text-amber-400">
              <AlertTriangle className="w-4 h-4 shrink-0" />
              <span>1. Public Beta Disclaimer</span>
            </div>
            <p className="text-zinc-400">
              Loopix is currently provided as a <strong>Public Beta</strong> release. Features, autonomous agent behaviors, and code generation capabilities are under active development and may experience intermittent behavior, rate limits, or unexpected output. Loopix is provided on an &ldquo;AS IS&rdquo; and &ldquo;AS AVAILABLE&rdquo; basis without warranties of any kind.
            </p>
          </div>

          {/* Section 2: Token Consumption & Credit Liability */}
          <div className="pt-4 space-y-2">
            <div className="flex items-center gap-2 font-bold text-[#4C8DFF]">
              <Coins className="w-4 h-4 shrink-0" />
              <span>2. API Key, Token Consumption & Credit Liability</span>
            </div>
            <p className="text-zinc-400">
              Loopix connects directly to third-party LLM providers (including OpenAI, Anthropic, DeepSeek, Groq, NVIDIA, Ollama, etc.) using the API credentials configured by you:
            </p>
            <ul className="list-disc list-inside space-y-1 text-zinc-400 pl-1">
              <li>Autonomous agent workflows, deep workspace scans, multi-turn coding sessions, and automated debugging loops can consume significant tokens and provider credits.</li>
              <li><strong>You are solely responsible</strong> for all costs, billing, rate limits, and token usage incurred on your third-party API accounts.</li>
              <li>Loopix authors and maintainers bear <strong>zero financial liability</strong> for consumed tokens, charges, or lost credits.</li>
            </ul>
          </div>

          {/* Section 3: Code Execution & Safety */}
          <div className="pt-4 space-y-2">
            <div className="flex items-center gap-2 font-bold text-purple-400">
              <Terminal className="w-4 h-4 shrink-0" />
              <span>3. Code Review & Production Safety</span>
            </div>
            <p className="text-zinc-400">
              Always review and verify all AI-generated code, file edits, and suggested terminal commands before applying or executing them in production environments. You assume full responsibility for any modifications made to your workspace.
            </p>
          </div>

          {/* Section 4: Privacy & Key Storage */}
          <div className="pt-4 space-y-2">
            <div className="flex items-center gap-2 font-bold text-emerald-400">
              <Key className="w-4 h-4 shrink-0" />
              <span>4. Privacy & Secret Containment</span>
            </div>
            <p className="text-zinc-400">
              Your API keys and source code are processed locally on your machine and stored securely in your local OS keyring or local configuration. Loopix does not transmit your proprietary source code or credentials to any third-party servers other than your configured LLM endpoints.
            </p>
          </div>

        </div>

        {/* Footer / Acceptance */}
        <div className="px-6 py-4 bg-[#181B28] border-t border-[#2A3146] space-y-3 shrink-0">
          
          <label className="flex items-start gap-2.5 cursor-pointer text-xs text-zinc-300">
            <input
              type="checkbox"
              checked={hasAgreed}
              onChange={e => setHasAgreed(e.target.checked)}
              className="mt-0.5 w-4 h-4 rounded border-[#2A3146] bg-black/40 text-[#4C8DFF] focus:ring-0 focus:outline-none cursor-pointer accent-[#4C8DFF]"
            />
            <span>
              I understand that Loopix is in <strong>Beta</strong>, and I accept full responsibility for my API keys, token consumption, and code changes.
            </span>
          </label>

          <button
            onClick={handleAccept}
            disabled={!hasAgreed}
            className="w-full py-2.5 bg-[#4C8DFF] hover:bg-[#6AA3FF] disabled:opacity-40 disabled:hover:bg-[#4C8DFF] text-white font-bold rounded-xl text-xs flex items-center justify-center gap-2 transition-all cursor-pointer shadow-lg shadow-[#4C8DFF]/20"
          >
            <Check className="w-4 h-4" />
            Accept Terms & Launch Loopix
          </button>
        </div>

      </div>
    </div>
  );
}
