export function getExecutableCommandForFile(filePath: string): string {
  if (!filePath) {
    return localStorage.getItem('devpilot_project_run_command') || 'npm run dev';
  }

  const stored = localStorage.getItem(`devpilot_file_cmd_${filePath}`);
  if (stored) return stored;

  const normalized = filePath.replace(/\\/g, '/');
  const filename = normalized.split('/').pop() || filePath;
  const ext = filename.split('.').pop()?.toLowerCase() || '';

  let defaultCmd = `python "${filename}"`;
  switch (ext) {
    case 'py':
      defaultCmd = `python "${filename}"`;
      break;
    case 'js':
    case 'cjs':
    case 'mjs':
      defaultCmd = `node "${filename}"`;
      break;
    case 'ts':
    case 'tsx':
    case 'jsx':
      defaultCmd = `npx ts-node "${filename}"`;
      break;
    case 'go':
      defaultCmd = `go run "${filename}"`;
      break;
    case 'rs':
      defaultCmd = `cargo run`;
      break;
    case 'c':
      defaultCmd = `gcc "${filename}" -o app && ./app`;
      break;
    case 'cpp':
      defaultCmd = `g++ "${filename}" -o app && ./app`;
      break;
    case 'java':
      defaultCmd = `java "${filename}"`;
      break;
    case 'sh':
      defaultCmd = `bash "${filename}"`;
      break;
    case 'ps1':
      defaultCmd = `powershell -File "${filename}"`;
      break;
    case 'json':
      if (filename === 'package.json') defaultCmd = 'npm run dev';
      break;
    case 'toml':
      if (filename === 'Cargo.toml') defaultCmd = 'cargo run';
      if (filename === 'pyproject.toml') defaultCmd = 'python -m pytest';
      break;
  }

  localStorage.setItem(`devpilot_file_cmd_${filePath}`, defaultCmd);
  return defaultCmd;
}

export function saveExecutableCommandForFile(filePath: string, command: string): void {
  if (!filePath || !command) return;
  localStorage.setItem(`devpilot_file_cmd_${filePath}`, command.trim());
}
