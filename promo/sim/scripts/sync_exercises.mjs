// --from-phone refreshes the portable snapshot after an approved viewer update.
// Normal simulator builds work on machines without a generated Android asset bundle.
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { zipSync, unzipSync, strToU8 } from 'three/addons/libs/fflate.module.js';

const map = JSON.parse(readFileSync(new URL('./exercise_stations.json', import.meta.url)));
const ids = new Set(Object.values(map));
const bundle = new URL('../../../phone/src/main/assets/viewer3d/', import.meta.url);
const assets = new URL('../public/assets/exercises/', import.meta.url);
const archive = new URL('../assets/station_exercises.zip', import.meta.url);
const files = ['human_v5/base.json', 'human_v5/watch.json', 'human_v5/manifest.json'];
for (const id of ids) files.push(`data/${id}.json`, `human_v5/${id}.bin`);

if (process.argv.includes('--from-phone')) {
  const entries = Object.fromEntries(files.map((file) => [file, readFileSync(new URL(file, bundle))]));
  const manifest = JSON.parse(entries['human_v5/manifest.json']);
  const clips = manifest.clips
    .filter((clip) => ids.has(clip.id))
    .map(({ id, playback_range, playback_mode, playback_ms }) => ({
      id,
      playback_range,
      playback_mode,
      playback_ms
    }));
  if (clips.length !== ids.size) throw new Error('운동 목록과 앱 동작을 확인해');
  entries['human_v5/manifest.json'] = strToU8(JSON.stringify({ revision: manifest.revision, clips }));
  mkdirSync(new URL('.', archive), { recursive: true });
  writeFileSync(archive, zipSync(entries, { level: 6, mtime: new Date(2000, 0, 1) }));
}
const entries = unzipSync(readFileSync(archive));
for (const dir of ['human_v5/', 'data/']) mkdirSync(new URL(dir, assets), { recursive: true });
for (const file of files) writeFileSync(new URL(file, assets), entries[file]);
