import { spawnSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const simRoot = resolve(__dirname, '..');
const scriptPath = resolve(__dirname, 'export_gym.py');

const candidates = process.platform === 'win32'
  ? [
      'C:\\Program Files\\Blender Foundation\\Blender 5.2\\blender.exe',
      'C:\\Program Files\\Blender Foundation\\Blender 5.1\\blender.exe',
      'blender.exe'
    ]
  : ['/Applications/Blender.app/Contents/MacOS/Blender', 'blender'];

const blenderBin = candidates.find((p) => p.includes('\\') || p.includes('/') ? existsSync(p) : true);
if (!blenderBin) {
  console.error('Blender executable not found.');
  process.exit(1);
}

console.log(`[sync-blender] Running: "${blenderBin}" -b --factory-startup -P "${scriptPath}"`);
const res = spawnSync(blenderBin, ['-b', '--factory-startup', '-P', scriptPath], {
  cwd: simRoot,
  stdio: 'inherit'
});

if (res.error) {
  console.error('[sync-blender] Failed to launch Blender:', res.error);
  process.exit(1);
}
process.exit(res.status ?? 0);
