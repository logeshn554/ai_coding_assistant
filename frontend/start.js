import fs from 'fs';
import path from 'path';
import { spawn } from 'child_process';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const rootDir = path.resolve(__dirname, '..');

const winPy = path.join(rootDir, 'venv', 'Scripts', 'python.exe');
const unixPy = path.join(rootDir, 'venv', 'bin', 'python');

let py = 'python';
if (fs.existsSync(winPy)) {
  py = winPy;
} else if (fs.existsSync(unixPy)) {
  py = unixPy;
}

const launcher = path.join(rootDir, 'backend', 'launcher.py');
const proc = spawn(py, [launcher], { cwd: rootDir, stdio: 'inherit' });
proc.on('exit', (code) => process.exit(code || 0));
