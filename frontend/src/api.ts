/**
 * Centralised API helper for the DevPilot frontend.
 * All requests go through this module so that we can:
 *   • Attach the session token automatically (if needed)
 *   • Handle HTTP errors in a single place
 *   • Keep the fetch calls DRY across components.
 */

/**
 * Helper to perform a fetch request and throw on non‑2xx responses.
 */
async function request<T>(
  input: RequestInfo,
  init?: RequestInit
): Promise<T> {
  const response = await fetch(input, init);
  if (!response.ok) {
    const errorBody = await response.text();
    throw new Error(`HTTP ${response.status}: ${errorBody}`);
  }
  // Most endpoints return JSON, but some (e.g., static files) may not.
  const contentType = response.headers.get('content-type') || '';
  if (contentType.includes('application/json')) {
    return (await response.json()) as T;
  }
  // Fallback to plain text for non‑JSON responses.
  return (await response.text()) as unknown as T;
}

/** Workspace */
export const getWorkspace = () => request<{ workspace: string }>('/api/workspace');
export const changeWorkspace = (path: string) =>
  request<{ success: boolean; workspace: string }>('/api/workspace/change', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path })
  });

/** Files */
export const listFiles = (path = '') => request<any[]>(`/api/files?path=${encodeURIComponent(path)}`);
export const getFileContent = (path: string) =>
  request<{ content: string }>(`/api/files/content?path=${encodeURIComponent(path)}`);
export const createFile = (path: string, isDir: boolean) =>
  request<{ success: boolean }>('/api/files/create', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path, is_dir: isDir })
  });
export const deleteFile = (path: string) =>
  request<{ success: boolean }>('/api/files/delete', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path })
  });
export const renameFile = (oldPath: string, newPath: string) =>
  request<{ success: boolean }>('/api/files/rename', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ old_path: oldPath, new_path: newPath })
  });

/** Workspace statistics */
export const getWorkspaceStats = () =>
  request<{
    total_files: number;
    total_lines: number;
    languages: Record<string, number>;
    git_commits: number;
  }>('/api/workspace/stats');

/** Search */
export const searchCodebase = (query: string) =>
  request<any[]>(`/api/files/search?query=${encodeURIComponent(query)}`);

/**
 * Exported type for generic API errors.
 */
export class ApiError extends Error {
  public status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}
