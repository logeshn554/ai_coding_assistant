import React, { useEffect, useRef, useCallback } from 'react';

export interface ContextMenuItem {
  label: string;
  icon?: React.ReactNode;
  shortcut?: string;
  onClick: () => void;
  destructive?: boolean;
  disabled?: boolean;
}

export interface ContextMenuDivider {
  type: 'divider';
}

export type ContextMenuEntry = ContextMenuItem | ContextMenuDivider;

interface ContextMenuProps {
  x: number;
  y: number;
  items: ContextMenuEntry[];
  onClose: () => void;
}

function isDivider(entry: ContextMenuEntry): entry is ContextMenuDivider {
  return 'type' in entry && entry.type === 'divider';
}

export const ContextMenu: React.FC<ContextMenuProps> = ({ x, y, items, onClose }) => {
  const menuRef = useRef<HTMLDivElement>(null);

  // Adjust position to keep menu within viewport
  const getAdjustedPosition = useCallback(() => {
    const menu = menuRef.current;
    if (!menu) return { left: x, top: y };

    const rect = menu.getBoundingClientRect();
    const vw = window.innerWidth;
    const vh = window.innerHeight;

    let left = x;
    let top = y;

    if (x + rect.width > vw - 8) {
      left = vw - rect.width - 8;
    }
    if (y + rect.height > vh - 8) {
      top = vh - rect.height - 8;
    }

    return { left: Math.max(4, left), top: Math.max(4, top) };
  }, [x, y]);

  useEffect(() => {
    const menu = menuRef.current;
    if (menu) {
      const { left, top } = getAdjustedPosition();
      menu.style.left = `${left}px`;
      menu.style.top = `${top}px`;
    }
  }, [getAdjustedPosition]);

  // Close on click outside or Escape
  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        onClose();
      }
    };
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    const handleScroll = () => onClose();

    document.addEventListener('mousedown', handleClick);
    document.addEventListener('keydown', handleKey);
    window.addEventListener('scroll', handleScroll, true);

    return () => {
      document.removeEventListener('mousedown', handleClick);
      document.removeEventListener('keydown', handleKey);
      window.removeEventListener('scroll', handleScroll, true);
    };
  }, [onClose]);

  return (
    <div ref={menuRef} className="dp-context-menu" style={{ left: x, top: y }}>
      {items.map((entry, i) => {
        if (isDivider(entry)) {
          return <div key={`d-${i}`} className="dp-context-menu-divider" />;
        }

        const item = entry as ContextMenuItem;
        return (
          <div
            key={i}
            className={`dp-context-menu-item ${item.destructive ? 'destructive' : ''} ${item.disabled ? 'opacity-40 pointer-events-none' : ''}`}
            onClick={() => {
              if (!item.disabled) {
                item.onClick();
                onClose();
              }
            }}
          >
            {item.icon && <span className="w-4 h-4 flex items-center justify-center shrink-0 opacity-70">{item.icon}</span>}
            <span className="flex-1 truncate">{item.label}</span>
            {item.shortcut && <span className="shortcut">{item.shortcut}</span>}
          </div>
        );
      })}
    </div>
  );
};
