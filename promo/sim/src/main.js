import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js';
import { Reflector } from 'three/examples/jsm/objects/Reflector.js';
import { mergeGeometries } from 'three/examples/jsm/utils/BufferGeometryUtils.js';
import { PlayerController } from './player.js';
import stationClips from '../scripts/exercise_stations.json';
import locomotion from '../../poses/v6_locomotion.json';
import { loadExercise } from './exercises.js';
import { ShowerFX } from './particles.js';

const canvas = document.getElementById('app');
const lockHint = document.getElementById('lock-hint');
const promptPill = document.getElementById('prompt-pill');
const posingBar = document.getElementById('posing-bar');
const fpsBadge = document.getElementById('fps-badge');
const helpOverlay = document.getElementById('help-overlay');

// Renderer tuned for 1440p 100fps on RTX 4060 with AgX/ACESFilmic parity
const renderer = new THREE.WebGLRenderer({
  canvas,
  antialias: true,
  powerPreference: 'high-performance'
});
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.0));
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.35;
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.shadowMap.autoUpdate = false;
renderer.shadowMap.needsUpdate = true;

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x0b0d12);
scene.fog = new THREE.FogExp2(0x0c0e14, 0.008);

const camera = new THREE.PerspectiveCamera(62, window.innerWidth / window.innerHeight, 0.08, 150);

// Soft PMREM environment for realistic gym metal & leather highlights
const pmrem = new THREE.PMREMGenerator(renderer);
scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
scene.environmentIntensity = 0.65;

// Balanced gym lighting: clear visibility + warm ceiling strips + neon accents + posing pin spot
const hemi = new THREE.HemisphereLight(0xeef4ff, 0x262a34, 0.85);
scene.add(hemi);

const sun = new THREE.DirectionalLight(0xfff4e6, 1.35);
sun.position.set(12, 16, 6);
sun.castShadow = true;
sun.shadow.mapSize.set(1024, 1024);
sun.shadow.camera.near = 1;
sun.shadow.camera.far = 45;
sun.shadow.camera.left = -16;
sun.shadow.camera.right = 18;
sun.shadow.camera.top = 18;
sun.shadow.camera.bottom = -16;
sun.shadow.bias = -0.0005;
scene.add(sun);

const zoneLights = [
  { pos: [3.0, 3.3, -2.6], color: 0xffe0bd, intensity: 32, dist: 16 },  // StripArea_Back
  { pos: [3.0, 3.3, 0.24], color: 0xffe0bd, intensity: 32, dist: 16 },  // StripArea_Front
  { pos: [3.0, 3.3, 4.1], color: 0xffe0bd, intensity: 32, dist: 16 },   // StripArea_Locker
  { pos: [0.4, 2.8, -4.6], color: 0x3399ff, intensity: 14, dist: 10 },  // NeonGlow_Blue
  { pos: [-0.2, 2.7, -4.6], color: 0xff3388, intensity: 14, dist: 10 }, // NeonGlow_Pink
  { pos: [-6.8, 2.2, 3.2], color: 0xff4488, intensity: 16, dist: 10 },  // Left wall rose neon
  { pos: [-1.45, 3.1, 8.7], color: 0xffebd6, intensity: 28, dist: 10 }, // Posing room pin spot
  { pos: [9.5, 2.8, 10.5], color: 0xeef6ff, intensity: 22, dist: 12 },  // Men suite
  { pos: [13.7, 2.8, 10.5], color: 0xfff2ee, intensity: 22, dist: 12 }, // Women suite
  { pos: [-9.0, 2.6, -1.5], color: 0xffebd6, intensity: 18, dist: 11 }  // Sangga hallway
];
for (const zl of zoneLights) {
  const pl = new THREE.PointLight(zl.color, zl.intensity, zl.dist, 1.1);
  pl.position.set(zl.pos[0], zl.pos[1], zl.pos[2]);
  scene.add(pl);
}

const showerFX = new ShowerFX(scene);

let manifest = null;
let player = null;
const doors = [];
const mirrors = [];
const suiteMeshes = { men: [], women: [] };
let activeStation = null; // { type: 'equipment'|'shower'|'toilet', item }

const keys = new Set();
let helpOpen = false;
let fpsOpen = false;
let framesCount = 0;
let fpsTimer = 0;

let started = false;
let lastMouseX = null;
let lastMouseY = null;

// Pointer lock with seamless free-look fallback (works in both normal Chrome and embedded tabs without holding mouse button)
function engageLook() {
  started = true;
  lockHint.classList.add('gone');
  lastMouseX = null;
  lastMouseY = null;
  try {
    const p = canvas.requestPointerLock?.();
    if (p && typeof p.catch === 'function') p.catch(() => {});
  } catch (_) {}
}

lockHint.addEventListener('click', engageLook);
canvas.addEventListener('click', () => {
  if (!helpOpen) engageLook();
});

document.addEventListener('pointerlockchange', () => {
  if (document.pointerLockElement === canvas) {
    started = true;
    lockHint.classList.add('gone');
  }
});

document.addEventListener('mousemove', (e) => {
  if (!player || helpOpen) return;
  const locked = document.pointerLockElement === canvas;
  if (!locked && !started) return;

  let dx = 0;
  let dy = 0;
  if (locked) {
    dx = e.movementX;
    dy = e.movementY;
  } else {
    if (lastMouseX !== null) {
      dx = e.clientX - lastMouseX;
      dy = e.clientY - lastMouseY;
    }
    lastMouseX = e.clientX;
    lastMouseY = e.clientY;
  }

  const sens = 0.0024;
  player.yaw -= dx * sens;
  player.pitch = Math.max(-1.25, Math.min(1.25, player.pitch - dy * sens));
});

window.addEventListener('resize', () => {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
});

// Load manifest + world + player
async function init() {
  const res = await fetch('/assets/gym_manifest.json');
  manifest = await res.json();

  const loader = new GLTFLoader();
  const [worldGltf, playerGltf] = await Promise.all([
    loader.loadAsync('/assets/gym_world.glb'),
    loader.loadAsync('/assets/player_v6.glb')
  ]);

  const worldRoot = worldGltf.scene;
  worldRoot.updateMatrixWorld(true);

  // Identify protected nodes (doors, mirrors) that must NOT be merged
  const protectedObjs = new Set();
  for (const mm of manifest.mirrors) {
    const o = worldRoot.getObjectByName(mm.node);
    if (o) protectedObjs.add(o);
  }
  for (const dm of manifest.doors) {
    for (const h of dm.hinges) {
      const hn = worldRoot.getObjectByName(h.node);
      if (hn) hn.traverse((c) => protectedObjs.add(c));
    }
  }

  const stationForMesh = new Map();
  const byOriginalName = new Map();
  worldRoot.traverse((o) => byOriginalName.set(o.userData.name || o.name, o));
  const climber = byOriginalName.get('Rotating stair climber');
  if (climber) {
    const origin = climber.getWorldPosition(new THREE.Vector3());
    const stand = climber.localToWorld(new THREE.Vector3(0, 0.68, -0.11));
    const carriers = climber.children.filter((o) => (o.userData.name || o.name).startsWith('Step carrier'));
    carriers.sort((a, b) => (a.userData.name || a.name).localeCompare(b.userData.name || b.name));
    if (carriers.length !== 7) throw new Error('계단 발판 7개가 필요해');
    carriers.forEach((o) => o.traverse((c) => protectedObjs.add(c)));
    manifest.equipment.push({
      id: 'stairs',
      label: '천국의계단',
      clip: 'stair_ascent',
      pos: origin.toArray(),
      standPos: stand.toArray(),
      yaw: climber.rotation.y - Math.PI,
      radius: 1.5,
      carriers,
      path: carriers.map((o) => o.position.clone())
    });
  }
  for (const eq of manifest.equipment) {
    const node = byOriginalName.get(eq.id);
    if (!node) continue;
    if (eq.id.startsWith('P_treadmill')) {
      eq.standPos = node.localToWorld(new THREE.Vector3(0, 0.171, -0.12)).toArray();
      eq.yaw -= Math.PI;
      eq.clip = 'walk';
    }
    if (!stationClips[eq.id]) continue;
    eq.original = [];
    eq.stationMatrix = node.matrixWorld.clone().multiply(new THREE.Matrix4().makeRotationX(-Math.PI / 2));
    node.traverse((o) => stationForMesh.set(o, eq));
  }

  // Suite lookup
  const suiteNameByObj = new Map();
  for (const sname of ['men', 'women']) {
    const sdata = manifest.suites?.[sname];
    if (!sdata) continue;
    for (const oname of sdata.objects) suiteNameByObj.set(oname, sname);
  }

  // Merge static meshes by (suite, material) to cut draw calls from 6000+ down to ~100 for 100fps
  const mergeGroups = new Map();
  const toDetach = [];
  worldRoot.traverse((obj) => {
    if (!obj.isMesh || protectedObjs.has(obj) || Array.isArray(obj.material)) {
      if (obj.isMesh) {
        obj.receiveShadow = true;
        if (!obj.material?.transparent) obj.castShadow = true;
      }
      return;
    }
    const stag = suiteNameByObj.get(obj.name) || 'world';
    const mat = obj.material;
    const station = stationForMesh.get(obj);
    const key = `${stag}::${station?.id || ''}::${mat.uuid}`;
    if (!mergeGroups.has(key)) mergeGroups.set(key, { stag, station, mat, geos: [] });
    const g = obj.geometry.index ? obj.geometry.toNonIndexed() : obj.geometry.clone();
    g.applyMatrix4(obj.matrixWorld);
    // Keep only position, normal, uv for clean merging
    for (const attr of Object.keys(g.attributes)) {
      if (attr !== 'position' && attr !== 'normal' && attr !== 'uv') {
        g.deleteAttribute(attr);
      }
    }
    if (!g.attributes.uv) {
      const count = g.attributes.position.count;
      g.setAttribute('uv', new THREE.BufferAttribute(new Float32Array(count * 2), 2));
    }
    mergeGroups.get(key).geos.push(g);
    toDetach.push(obj);
  });

  for (const obj of toDetach) {
    if (obj.parent) obj.parent.remove(obj);
  }

  const mergedGroup = new THREE.Group();
  for (const { stag, station, mat, geos } of mergeGroups.values()) {
    if (!geos.length) continue;
    const mergedGeo = geos.length === 1 ? geos[0] : mergeGeometries(geos, false);
    if (!mergedGeo) continue;
    const mesh = new THREE.Mesh(mergedGeo, mat);
    mesh.receiveShadow = true;
    if (!mat.transparent) mesh.castShadow = true;
    mergedGroup.add(mesh);
    if (station) station.original.push(mesh);
    if (stag === 'men' || stag === 'women') {
      suiteMeshes[stag].push(mesh);
    }
  }
  scene.add(worldRoot);
  scene.add(mergedGroup);

  // Setup doors
  for (const dm of manifest.doors) {
    const hingeObjs = [];
    for (const h of dm.hinges) {
      const node = worldRoot.getObjectByName(h.node);
      if (node) {
        hingeObjs.push({
          node,
          baseRotY: node.rotation.y,
          openAngle: h.openAngle
        });
      }
    }
    const isInitiallyOpen = Math.abs(dm.initialRotZ || 0) > 0.2;
    doors.push({
      ...dm,
      hingeObjs,
      isOpen: isInitiallyOpen,
      t: isInitiallyOpen ? 1 : 0,
      box: {
        min: [dm.pos[0] - 0.55, 0, dm.pos[2] - 0.55],
        max: [dm.pos[0] + 0.55, 2.2, dm.pos[2] + 0.55]
      }
    });
  }

  // Setup high-resolution real-time Reflector mirrors
  for (const mm of manifest.mirrors) {
    const orig = worldRoot.getObjectByName(mm.node);
    const n = new THREE.Vector3(mm.normal[0], mm.normal[1], mm.normal[2]).normalize();
    // Plane width & height from size
    const isXAligned = Math.abs(n.x) > 0.5;
    const width = isXAligned ? mm.size[2] : mm.size[0];
    const height = mm.size[1];
    const geo = new THREE.PlaneGeometry(Math.max(0.4, width), Math.max(0.4, height));
    const isMainMirror = mm.id === 'main_mirror';
    const reflector = new Reflector(geo, {
      clipBias: 0.002,
      textureWidth: isMainMirror ? 2048 : 1024,
      textureHeight: isMainMirror ? 1024 : 1024,
      color: 0xc4ccd4
    });
    reflector.position.set(mm.pos[0], mm.pos[1], mm.pos[2]);
    // Offset cleanly in front of mirror glass & frame backing to prevent z-fighting
    reflector.position.addScaledVector(n, (mm.halfThickness || 0.015) + 0.024);
    reflector.lookAt(reflector.position.x + n.x, reflector.position.y + n.y, reflector.position.z + n.z);
    if (orig) orig.visible = false;
    scene.add(reflector);
    mirrors.push({
      ...mm,
      reflector,
      normalVec: n,
      posVec: reflector.position.clone()
    });
  }

  // Build posing bar chips
  posingBar.innerHTML = manifest.posingClips
    .map((p) => {
      const short = p.label.split(' (')[0];
      return `<span class="pose-chip" data-key="${p.key}"><kbd>${p.key}</kbd>${short}</span>`;
    })
    .join('');

  // Setup Player V6 (pass opaque world meshes for real 3D camera wall-pull-in raycasting)
  const raycastMeshes = [];
  mergedGroup.traverse((m) => {
    if (m.isMesh && !m.material?.transparent) raycastMeshes.push(m);
  });
  const playerRoot = playerGltf.scene;
  // The unassigned body primitive uses glTF's plain white fallback.
  playerRoot.traverse((obj) => {
    if (obj.isSkinnedMesh && !obj.material.name) {
      obj.material.color.setHex(0x63d6de);
      obj.material.metalness = 0;
      obj.material.roughness = 0.72;
    }
  });
  scene.add(playerRoot);
  const movement = locomotion.clips.map((data) => THREE.AnimationClip.parse(data));
  const replaced = new Set(movement.map((clip) => clip.name));
  const clips = playerGltf.animations.filter((clip) => !replaced.has(clip.name)).concat(movement);
  player = new PlayerController(playerRoot, clips, manifest.colliders, raycastMeshes);
  player.setSpawn(manifest.spawn.pos, manifest.spawn.yaw);

  // Pre-compile shaders & warm up all high-res mirrors once at load
  for (const m of mirrors) m.reflector.visible = true;
  renderer.compile(scene, camera);
  renderer.render(scene, camera);

  requestAnimationFrame(animate);
}

// Interaction helpers
function isInsideSuite(pos, suiteName) {
  const b = manifest?.suites?.[suiteName]?.bounds;
  if (!b) return false;
  return (
    pos.x >= b.min[0] - 0.3 && pos.x <= b.max[0] + 0.3 &&
    pos.z >= b.min[2] - 0.3 && pos.z <= b.max[2] + 0.3
  );
}

function findNearestInteractable() {
  if (!player || !manifest) return null;
  const px = player.pos.x;
  const pz = player.pos.z;

  // Check equipment
  let best = null;
  let bestDist = Infinity;

  for (const eq of manifest.equipment) {
    const d = Math.hypot(px - eq.pos[0], pz - eq.pos[2]);
    if (d < eq.radius && d < bestDist) {
      bestDist = d;
      best = { type: 'equipment', item: eq, label: `<kbd>E</kbd> ${eq.label}` };
    }
  }

  // Check showers
  for (const sh of manifest.showers) {
    const d = Math.hypot(px - sh.standPos[0], pz - sh.standPos[2]);
    if (d < 1.1 && d < bestDist) {
      bestDist = d;
      best = { type: 'shower', item: sh, label: `<kbd>E</kbd> 샤워하기` };
    }
  }

  // Check toilets / urinals
  for (const tl of manifest.toilets) {
    const d = Math.hypot(px - tl.standPos[0], pz - tl.standPos[2]);
    if (d < 1.0 && d < bestDist) {
      bestDist = d;
      best = { type: 'toilet', item: tl, label: `<kbd>E</kbd> 화장실 이용` };
    }
  }

  // Check doors
  for (const door of doors) {
    const d = Math.hypot(px - door.pos[0], pz - door.pos[2]);
    if (d < 1.55 && d < bestDist) {
      bestDist = d;
      const actionText = door.isOpen ? '닫기' : '열기';
      best = { type: 'door', item: door, label: `<kbd>E</kbd> ${door.label} ${actionText}` };
    }
  }

  return best;
}

function exitActiveStation(finish = false) {
  if (!activeStation || !player) return;
  if (activeStation.type === 'shower') {
    showerFX.stop();
  }
  if (activeStation.exercise) {
    if (!finish) {
      if (!activeStation.leaving) {
        activeStation.leaving = true;
        activeStation.elapsed = 0;
        activeStation.exercise.leave();
      }
      return;
    }
    scene.remove(activeStation.exercise.root);
    activeStation.item.original.forEach((o) => (o.visible = true));
    player.root.visible = true;
    player.exerciseHead = null;
  }
  if (activeStation.item.carriers)
    activeStation.item.carriers.forEach((o, i) => o.position.copy(activeStation.item.path[i]));
  if (activeStation.entry) player.pos.copy(activeStation.entry);
  activeStation = null;
  player.exitStation();
}

window.addEventListener('keydown', async (e) => {
  keys.add(e.code);
  if (started && e.code.startsWith('Arrow')) e.preventDefault();
  if (e.repeat) return;

  if (e.code === 'KeyH') {
    helpOpen = !helpOpen;
    helpOverlay.classList.toggle('hidden', !helpOpen);
    if (helpOpen && document.pointerLockElement === canvas) {
      document.exitPointerLock();
    }
    return;
  }

  if (e.code === 'F3') {
    e.preventDefault();
    fpsOpen = !fpsOpen;
    fpsBadge.classList.toggle('hidden', !fpsOpen);
    return;
  }

  if (!player) return;

  if (e.code === 'KeyV') {
    player.firstPerson = !player.firstPerson;
    return;
  }

  if (e.code === 'KeyQ') {
    if (!activeStation) player.triggerWatchCheck();
    return;
  }

  if (e.code === 'Escape' && activeStation) {
    exitActiveStation();
    return;
  }

  if (e.code === 'KeyE') {
    if (activeStation) {
      exitActiveStation();
      return;
    }
    const target = findNearestInteractable();
    if (!target) return;
    if (target.type === 'door') {
      target.item.isOpen = !target.item.isOpen;
    } else if (target.type === 'equipment') {
      activeStation = target;
      target.entry = player.pos.clone();
      const eq = target.item,
        id = stationClips[eq.id];
      if (id) {
        player.lockedAction = true;
        player.playClip('stand');
        try {
          const exercise = await loadExercise(id, player.root);
          if (activeStation !== target) return;
          target.exercise = exercise;
          target.elapsed = 0;
          exercise.root.matrix.copy(eq.stationMatrix);
          exercise.root.matrixAutoUpdate = false;
          scene.add(exercise.root);
          exercise.root.updateMatrixWorld(true);
          exercise.enter();
          exercise.update(0);
          eq.original.forEach((o) => (o.visible = false));
          player.root.visible = false;
          player.exerciseHead = exercise.head;
        } catch (err) {
          if (activeStation === target) exitActiveStation(true);
          console.error(eq.label, err);
        }
      } else {
        target.elapsed = 0;
        player.enterStation(eq.standPos, eq.yaw, eq.clip);
      }
    } else if (target.type === 'shower') {
      activeStation = target;
      player.enterStation(target.item.standPos, target.item.yaw, 'shower_wash');
      showerFX.start(target.item.headPos);
    } else if (target.type === 'toilet') {
      activeStation = target;
      player.enterStation(target.item.standPos, target.item.yaw, 'toilet_use');
    }
    return;
  }

  // Posing 1~8 inside Posing Room
  if (e.code.startsWith('Digit') && !activeStation && isInsideSuite(player.pos, 'posing')) {
    const num = Number(e.code.replace('Digit', ''));
    const pspec = manifest.posingClips.find((p) => p.key === num);
    if (pspec) {
      player.triggerPosing(pspec.clip);
      posingBar.querySelectorAll('.pose-chip').forEach((el) => {
        el.classList.toggle('active', Number(el.dataset.key) === num);
      });
    }
  }
});

window.addEventListener('keyup', (e) => {
  keys.delete(e.code);
});

let prevTime = performance.now();
const _toPlayer = new THREE.Vector3();

function animate(now) {
  requestAnimationFrame(animate);
  const dt = Math.min(0.05, (now - prevTime) / 1000);
  prevTime = now;

  // FPS counter (only updated if toggled on)
  if (fpsOpen) {
    framesCount++;
    fpsTimer += dt;
    if (fpsTimer >= 0.4) {
      fpsBadge.textContent = `${Math.round(framesCount / fpsTimer)} FPS`;
      framesCount = 0;
      fpsTimer = 0;
    }
  }

  // Update doors
  for (const d of doors) {
    const target = d.isOpen ? 1 : 0;
    d.t += (target - d.t) * Math.min(1, dt * 8);
    for (const h of d.hingeObjs) {
      h.node.rotation.y = h.baseRotY + h.openAngle * d.t;
    }
  }

  // Cull closed Men/Women locker suites when player is outside
  for (const sname of ['men', 'women']) {
    const door = doors.find((d) => d.suite === sname);
    const inside = isInsideSuite(player.pos, sname);
    const visible = inside || (door && door.t > 0.03);
    const list = suiteMeshes[sname];
    for (let i = 0; i < list.length; i++) {
      list[i].visible = visible;
    }
  }

  // Room-aware mirror visibility: main_mirror ALWAYS on in main gym, posing mirrors ALWAYS on in posing room
  const inMen = isInsideSuite(player.pos, 'men');
  const inWomen = isInsideSuite(player.pos, 'women');
  const inPosing = isInsideSuite(player.pos, 'posing');
  const inMainGym = !inMen && !inWomen && !inPosing;
  player.inSmallRoom = inMen || inWomen || inPosing;

  for (const m of mirrors) {
    if (m.id === 'main_mirror') {
      m.reflector.visible = inMainGym;
    } else if (m.id.startsWith('posing_')) {
      m.reflector.visible = inPosing;
    } else {
      _toPlayer.subVectors(player.pos, m.posVec);
      m.reflector.visible = inMainGym && _toPlayer.length() < 12.0;
    }
  }

  if (activeStation?.exercise) {
    activeStation.elapsed += dt;
    if (activeStation.exercise.update(activeStation.elapsed)) exitActiveStation(true);
  } else if (activeStation?.item.id.startsWith('P_treadmill')) {
    player.playClip(keys.has('ShiftLeft') || keys.has('ShiftRight') ? 'run' : 'walk');
  }
  player.update(dt, keys, camera, doors);
  if (activeStation?.item.carriers) {
    const { carriers, path } = activeStation.item;
    const clip = player.actions.stair_ascent;
    activeStation.elapsed += dt;
    const cycles = (2 * activeStation.elapsed) / clip.getClip().duration;
    carriers.forEach((o, i) => {
      const f = THREE.MathUtils.euclideanModulo(i - cycles, path.length);
      const j = Math.floor(f);
      o.position.lerpVectors(path[j], path[(j + 1) % path.length], f - j);
    });
  }
  showerFX.update(dt);

  // Minimal HUD prompts
  const showPosingBar = inPosing && !activeStation;
  posingBar.classList.toggle('hidden', !showPosingBar);

  if (activeStation) {
    promptPill.innerHTML = `<kbd>E</kbd> / <kbd>ESC</kbd> 종료`;
    promptPill.classList.remove('hidden');
  } else {
    const nearest = findNearestInteractable();
    if (nearest) {
      promptPill.innerHTML = nearest.label;
      promptPill.classList.remove('hidden');
    } else if (showPosingBar) {
      promptPill.innerHTML = `<kbd>1~8</kbd> 포징 선택`;
      promptPill.classList.remove('hidden');
    } else {
      promptPill.classList.add('hidden');
    }
  }

  renderer.render(scene, camera);
}

init().catch((err) => {
  console.error('[WatchCoach Sim] Init error:', err);
});
