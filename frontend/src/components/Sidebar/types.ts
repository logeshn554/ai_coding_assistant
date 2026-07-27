export interface FileItem {
  name: string;
  path: string;
  is_dir: boolean;
  size?: number;
}

export interface WorkspaceStatsData {
  total_files: number;
  total_lines: number;
  languages: Record<string, number>;
  git_commits: number;
}

export interface SidebarProps {
  onSelectFile: (path: string) => void;
  selectedFilePath: string | null;
  refreshTrigger: number;
  workspacePath: string;
  onOpenFolder: () => void;
  gitChanges?: Record<string, string>;
}
