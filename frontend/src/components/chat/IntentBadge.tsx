import React from 'react';
import { Bug, FolderPlus, RefreshCw, FileText, FastForward, Search, ShieldCheck, Sparkles } from 'lucide-react';

interface IntentBadgeProps {
  intent: string | null;
}

export const IntentBadge: React.FC<IntentBadgeProps> = ({ intent }) => {
  if (!intent) return null;

  const config: Record<string, { label: string; icon: any; bg: string; color: string; border: string }> = {
    NEW_PROJECT: {
      label: 'New Project',
      icon: FolderPlus,
      bg: 'rgba(168, 85, 247, 0.1)',
      color: '#A855F7',
      border: '1px solid rgba(168, 85, 247, 0.25)',
    },
    IMPLEMENT_SPEC: {
      label: 'Build Spec',
      icon: FileText,
      bg: 'rgba(59, 130, 246, 0.1)',
      color: '#3B82F6',
      border: '1px solid rgba(59, 130, 246, 0.25)',
    },
    BUG_FIX: {
      label: 'Bug Fix',
      icon: Bug,
      bg: 'rgba(239, 68, 68, 0.1)',
      color: '#EF4444',
      border: '1px solid rgba(239, 68, 68, 0.25)',
    },
    REFACTOR: {
      label: 'Refactor',
      icon: RefreshCw,
      bg: 'rgba(245, 158, 11, 0.1)',
      color: '#F59E0B',
      border: '1px solid rgba(245, 158, 11, 0.25)',
    },
    EXPLAIN: {
      label: 'Explain',
      icon: FileText,
      bg: 'rgba(16, 185, 129, 0.1)',
      color: '#10B981',
      border: '1px solid rgba(16, 185, 129, 0.25)',
    },
    CONTINUE: {
      label: 'Resume',
      icon: FastForward,
      bg: 'rgba(236, 72, 153, 0.1)',
      color: '#EC4899',
      border: '1px solid rgba(236, 72, 153, 0.25)',
    },
    SEARCH: {
      label: 'Search',
      icon: Search,
      bg: 'rgba(6, 182, 212, 0.1)',
      color: '#06B6D4',
      border: '1px solid rgba(6, 182, 212, 0.25)',
    },
    REVIEW: {
      label: 'Review',
      icon: ShieldCheck,
      bg: 'rgba(99, 102, 241, 0.1)',
      color: '#6366F1',
      border: '1px solid rgba(99, 102, 241, 0.25)',
    },
    GENERAL: {
      label: 'General',
      icon: Sparkles,
      bg: 'rgba(107, 114, 128, 0.1)',
      color: '#9CA3AF',
      border: '1px solid rgba(107, 114, 128, 0.25)',
    },
  };

  const item = config[intent] || config.GENERAL;
  const Icon = item.icon;

  return (
    <span
      className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold select-none shadow-sm transition-all duration-300 hover:scale-105"
      style={{
        background: item.bg,
        color: item.color,
        border: item.border,
      }}
    >
      <Icon className="w-3.5 h-3.5" />
      {item.label}
    </span>
  );
};
