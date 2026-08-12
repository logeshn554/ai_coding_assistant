import React, { useState } from 'react';
import { ShieldAlert, Check, X, AlertTriangle } from 'lucide-react';

interface ApprovalCardProps {
  payload: {
    tool_name?: string;
    command?: string;
    risk?: string;
    reason?: string;
  };
  onApprove: (scope: 'once' | 'session') => void;
  onReject: (reason: string) => void;
}

export const ApprovalCard: React.FC<ApprovalCardProps> = ({ payload, onApprove, onReject }) => {
  const [rejectReason, setRejectReason] = useState('');
  const [showRejectInput, setShowRejectInput] = useState(false);

  const isCritical = payload.risk === 'CRITICAL' || payload.risk === 'HIGH';

  return (
    <div className={`approval-card p-3 my-2 rounded-lg border text-xs shadow-md ${isCritical ? 'bg-error/10 border-error' : 'bg-warning/10 border-warning'}`}>
      <div className="flex items-center gap-2 font-semibold text-sm mb-1">
        {isCritical ? <ShieldAlert className="w-5 h-5 text-error" /> : <AlertTriangle className="w-5 h-5 text-warning" />}
        <span>{isCritical ? '🚨 Destructive Operation Approval' : '⚠ Permission Required'}</span>
      </div>

      <div className="space-y-1 my-2 text-base-content/80">
        <div><span className="font-semibold">Action:</span> {payload.tool_name || 'Execute Command'}</div>
        {payload.command && (
          <div className="font-mono bg-base-300 p-1.5 rounded text-[11px] overflow-x-auto my-1">
            {payload.command}
          </div>
        )}
        <div><span className="font-semibold">Risk Level:</span> <span className="badge badge-xs badge-outline font-bold">{payload.risk || 'MEDIUM'}</span></div>
        <div><span className="font-semibold">Reason:</span> {payload.reason || 'Operation requires policy authorization'}</div>
      </div>

      {showRejectInput ? (
        <div className="mt-2 space-y-2">
          <input
            type="text"
            placeholder="Reason for rejection (e.g. Do not modify package.json)"
            className="input input-xs input-bordered w-full"
            value={rejectReason}
            onChange={(e) => setRejectReason(e.target.value)}
          />
          <div className="flex gap-2 justify-end">
            <button onClick={() => setShowRejectInput(false)} className="btn btn-xs btn-ghost">Cancel</button>
            <button onClick={() => onReject(rejectReason)} className="btn btn-xs btn-error">Confirm Reject</button>
          </div>
        </div>
      ) : (
        <div className="flex flex-wrap gap-2 mt-3 pt-2 border-t border-base-300">
          <button onClick={() => onApprove('once')} className="btn btn-xs btn-primary gap-1">
            <Check className="w-3.5 h-3.5" /> Approve Once
          </button>
          <button onClick={() => onApprove('session')} className="btn btn-xs btn-outline btn-primary">
            Allow for Session
          </button>
          <button onClick={() => setShowRejectInput(true)} className="btn btn-xs btn-ghost text-error gap-1">
            <X className="w-3.5 h-3.5" /> Reject
          </button>
        </div>
      )}
    </div>
  );
};
