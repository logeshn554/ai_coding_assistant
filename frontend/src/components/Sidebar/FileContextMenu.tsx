import React from 'react';
import { ContextMenu } from '../ContextMenu';
import type { ContextMenuEntry } from '../ContextMenu';
import type { FileItem } from './types';
import { useTerminal } from '../../core/terminal/TerminalContext';
import { copyToClipboard } from '../../utils/clipboard';

interface FileContextMenuProps {
  contextMenu: { x: number; y: number; item: FileItem } | null;
  onClose: () => void;
  onStartCreateInFolder: (dirPath: string, type: 'file' | 'folder') => void;
  onStartRename: (item: FileItem) => void;
  onDelete: (item: FileItem) => void;
  selectedCount?: number;
}

export const FileContextMenu: React.FC<FileContextMenuProps> = ({
  contextMenu,
  onClose,
  onStartCreateInFolder,
  onStartRename,
  onDelete,
  selectedCount = 1,
}) => {
  const { setBottomTab, setActiveTerminalCommand } = useTerminal();

  if (!contextMenu) return null;

  const { x, y, item } = contextMenu;
  const targetDir = item.is_dir ? item.path : item.path.split('/').slice(0, -1).join('/');

  const menuItems: ContextMenuEntry[] = [
    {
      label: 'New File',
      onClick: () => onStartCreateInFolder(targetDir, 'file'),
    },
    {
      label: 'New Folder',
      onClick: () => onStartCreateInFolder(targetDir, 'folder'),
    },
    { type: 'divider' },
    {
      label: 'Copy Path',
      onClick: () => copyToClipboard(item.path),
    },
    {
      label: 'Rename',
      onClick: () => onStartRename(item),
    },
    {
      label: 'Open in Integrated Terminal',
      onClick: () => {
        setBottomTab('terminal');
        const cdPath = item.is_dir ? item.path : item.path.split('/').slice(0, -1).join('/');
        if (cdPath) {
          setActiveTerminalCommand(`cd "${cdPath}"`);
        }
      },
    },
    { type: 'divider' },
    {
      label: selectedCount > 1 ? `Delete Selected (${selectedCount})` : 'Delete',
      destructive: true,
      onClick: () => onDelete(item),
    },
  ];

  return <ContextMenu x={x} y={y} items={menuItems} onClose={onClose} />;
};
