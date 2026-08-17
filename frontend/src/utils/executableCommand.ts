export async function getExecutableCommandForFile(filePath: string): Promise<string> {
  if (!filePath) {
    return localStorage.getItem('loopix_project_run_command') || 'npm run dev';
  }

  const stored = localStorage.getItem(`loopix_file_cmd_${filePath}`);
  if (stored) return stored;

  const normalized = filePath.replace(/\\/g, '/');

  try {
    const res = await fetch('/api/workspace/detect-file-command', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ file_path: normalized }),
    });

    if (res.ok) {
      const data = await res.json();
      if (data.command) {
        localStorage.setItem(`loopix_file_cmd_${filePath}`, data.command);
        return data.command;
      }
    }
  } catch (err) {
    console.warn('Failed to query LLM for command detection:', err);
  }

  const fallbackCmd = `"${normalized}"`;
  localStorage.setItem(`loopix_file_cmd_${filePath}`, fallbackCmd);
  return fallbackCmd;
}

export function saveExecutableCommandForFile(filePath: string, command: string): void {
  if (!filePath || !command) return;
  localStorage.setItem(`loopix_file_cmd_${filePath}`, command.trim());
}

