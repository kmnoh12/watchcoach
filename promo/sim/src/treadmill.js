import * as THREE from 'three';

const MIN_SPEED_KMH = 0;
const MAX_SPEED_KMH = 16;
const DEFAULT_SPEED_KMH = 4.5;

const MIN_INCLINE_DEG = 0;
const MAX_INCLINE_DEG = 30;
const DEFAULT_INCLINE_DEG = 0;

const DECK_PARTS = [
  'Treadmill deck',
  'Running belt',
  'Treadmill side rail',
  'Motor cover'
];

const CONSOLE_PARTS = [
  'Console upright',
  'Treadmill grip',
  'Pulse contact',
  'Redon console bridge',
  'Redon mounting neck',
  'Runner controls',
  'Safety key',
  'Safety lanyard',
  'Shirt clip'
];

function createBeltTexture() {
  const c = document.createElement('canvas');
  c.width = 256;
  c.height = 512;
  const ctx = c.getContext('2d');

  // Matte dark rubber base
  ctx.fillStyle = '#181a1f';
  ctx.fillRect(0, 0, 256, 512);

  // Repeating horizontal tread ribs so belt motion is unmistakably visible
  for (let y = 0; y < 512; y += 16) {
    ctx.fillStyle = y % 64 === 0 ? '#272b33' : '#1f2229';
    ctx.fillRect(0, y, 256, 4);
  }

  // Subtle side edge wear lines & center alignment stripe
  ctx.fillStyle = 'rgba(255,255,255,0.06)';
  ctx.fillRect(10, 0, 4, 512);
  ctx.fillRect(242, 0, 4, 512);
  ctx.fillStyle = 'rgba(99, 214, 222, 0.16)';
  ctx.fillRect(125, 0, 6, 512);

  const tex = new THREE.CanvasTexture(c);
  tex.wrapS = THREE.RepeatWrapping;
  tex.wrapT = THREE.RepeatWrapping;
  tex.repeat.set(1, 2.5);
  tex.anisotropy = 4;
  return tex;
}

function makeStrutMaterial(color, metalness, roughness) {
  return new THREE.MeshStandardMaterial({ color, metalness, roughness });
}

/**
 * Upgrade a static P_treadmill GLB node into an articulated 0°~30° incline treadmill
 * with a rear-hinged tilting deck, telescoping hydraulic lift struts, widening upright
 * clearance, elevating console/handrails, and a speed-synced scrolling belt.
 */
export function setupInclineTreadmill(rootNode, protectedObjs) {
  rootNode.updateMatrixWorld(true);

  // Protect all dynamic children from static mesh merging
  rootNode.traverse((o) => protectedObjs.add(o));

  const deckPivot = new THREE.Group();
  deckPivot.name = `${rootNode.name}_DeckPivot`;
  // Rear hinge in P_treadmill Three.js local space: Blender (0, +0.94, +0.055) -> Three (0, +0.055, -0.94)
  deckPivot.position.set(0, 0.055, -0.94);
  rootNode.add(deckPivot);

  const consoleGroup = new THREE.Group();
  consoleGroup.name = `${rootNode.name}_ConsoleGroup`;
  rootNode.add(consoleGroup);

  const deckNodes = [];
  const consoleNodes = [];
  let beltMesh = null;

  for (const child of [...rootNode.children]) {
    if (child === deckPivot || child === consoleGroup) continue;
    const orig = child.userData.name || child.name;
    if (DECK_PARTS.some((p) => orig.startsWith(p))) {
      deckNodes.push(child);
      if (orig.startsWith('Running belt')) beltMesh = child;
    } else if (CONSOLE_PARTS.some((p) => orig.startsWith(p))) {
      consoleNodes.push(child);
    }
  }

  for (const n of deckNodes) deckPivot.attach(n);
  for (const n of consoleNodes) consoleGroup.attach(n);

  // Widen uprights slightly outward so the tilting deck passes cleanly between them up to 30°
  for (const n of consoleNodes) {
    const orig = n.userData.name || n.name;
    if (orig.startsWith('Console upright')) {
      const box = new THREE.Box3().setFromObject(n);
      const centerLocal = rootNode.worldToLocal(box.getCenter(new THREE.Vector3()));
      n.position.x += centerLocal.x >= 0 ? 0.075 : -0.075;
    }
  }

  // Scrolling belt texture
  const beltTex = createBeltTexture();
  if (beltMesh && beltMesh.isMesh) {
    const mat = beltMesh.material.clone();
    mat.map = beltTex;
    mat.color.setHex(0xffffff);
    mat.roughness = 0.78;
    mat.metalness = 0.05;
    beltMesh.material = mat;
    // Ensure planar top UVs exist for clean scrolling along deck length (local Z)
    const geo = beltMesh.geometry.clone();
    const pos = geo.attributes.position;
    const uv = new Float32Array(pos.count * 2);
    for (let i = 0; i < pos.count; i++) {
      uv[i * 2] = pos.getX(i) * 1.6 + 0.5;
      uv[i * 2 + 1] = pos.getZ(i) * 0.65 + 0.5;
    }
    geo.setAttribute('uv', new THREE.BufferAttribute(uv, 2));
    beltMesh.geometry = geo;
  }

  // Add realistic dual hydraulic incline lift struts (base frame <-> underside of tilting front deck)
  const housingMat = makeStrutMaterial(0x23272e, 0.45, 0.42);
  const pistonMat = makeStrutMaterial(0xc4cbd4, 0.85, 0.22);
  const bracketMat = makeStrutMaterial(0x191c22, 0.35, 0.55);

  const struts = [];
  const strutX = [-0.31, 0.31];
  const baseZ = 0.70; // front lift mount in Three.js local (+Z is front)
  const baseY = 0.032;
  const deckAnchorLocal = new THREE.Vector3(0, 0.015, 0.94 + baseZ); // relative to deckPivot

  for (const sx of strutX) {
    const outerGeo = new THREE.CylinderGeometry(0.026, 0.028, 1, 10);
    const outer = new THREE.Mesh(outerGeo, housingMat);
    outer.castShadow = true;
    outer.receiveShadow = true;
    rootNode.add(outer);

    const innerGeo = new THREE.CylinderGeometry(0.016, 0.016, 1, 10);
    const inner = new THREE.Mesh(innerGeo, pistonMat);
    inner.castShadow = true;
    rootNode.add(inner);

    const footBracket = new THREE.Mesh(new THREE.BoxGeometry(0.07, 0.045, 0.09), bracketMat);
    footBracket.position.set(sx, baseY, baseZ);
    rootNode.add(footBracket);

    struts.push({
      outer,
      inner,
      basePt: new THREE.Vector3(sx, baseY, baseZ),
      deckPtLocal: new THREE.Vector3(sx, deckAnchorLocal.y, deckAnchorLocal.z)
    });
  }

  // Rear hinge axle visual bar
  const hingeAxle = new THREE.Mesh(new THREE.CylinderGeometry(0.022, 0.022, 0.84, 12), bracketMat);
  hingeAxle.rotation.z = Math.PI / 2;
  hingeAxle.position.set(0, 0.055, -0.94);
  rootNode.add(hingeAxle);

  // Runner standing point in deckPivot local space:
  // At 0°: rootNode local (0, 0.171, -0.12) => deckPivot local (0, 0.116, 0.82)
  const standLocalOnDeck = new THREE.Vector3(0, 0.116, 0.82);

  const state = {
    rootNode,
    deckPivot,
    consoleGroup,
    beltTex,
    struts,
    standLocalOnDeck,
    targetSpeedKmh: DEFAULT_SPEED_KMH,
    currentSpeedKmh: DEFAULT_SPEED_KMH,
    targetInclineDeg: DEFAULT_INCLINE_DEG,
    currentInclineDeg: DEFAULT_INCLINE_DEG,
    beltPhase: 0,
    _tmpTop: new THREE.Vector3(),
    _tmpDir: new THREE.Vector3(),
    _tmpMid: new THREE.Vector3(),
    _upAxis: new THREE.Vector3(0, 1, 0),
    _tmpStandWorld: new THREE.Vector3()
  };

  applyTreadmillGeometry(state);
  return state;
}

export function applyTreadmillGeometry(tm) {
  const rad = THREE.MathUtils.degToRad(tm.currentInclineDeg);
  // Negative X rotation lifts +Z (front of treadmill) upward along +Y
  tm.deckPivot.rotation.x = -rad;
  tm.deckPivot.updateMatrix();
  tm.deckPivot.updateMatrixWorld(true);

  // Elevate console/handrails smoothly so they stay ergonomic & clear of the front deck
  tm.consoleGroup.position.y = Math.sin(rad) * 0.62;

  // Update telescoping lift struts between base frame and underside of front deck
  for (const s of tm.struts) {
    tm._tmpTop.copy(s.deckPtLocal).applyMatrix4(tm.deckPivot.matrix);
    tm._tmpDir.subVectors(tm._tmpTop, s.basePt);
    const len = Math.max(0.05, tm._tmpDir.length());
    const dirNorm = tm._tmpDir.clone().divideScalar(len);

    // Lower housing cylinder (fixed 58% of length from base)
    const lowerLen = Math.min(len * 0.62, 0.52);
    s.outer.position.copy(s.basePt).addScaledVector(dirNorm, lowerLen * 0.5);
    s.outer.scale.set(1, lowerLen, 1);
    s.outer.quaternion.setFromUnitVectors(tm._upAxis, dirNorm);

    // Upper chrome piston rod (spans from base to deck anchor)
    s.inner.position.copy(s.basePt).addScaledVector(dirNorm, len * 0.5);
    s.inner.scale.set(1, len, 1);
    s.inner.quaternion.setFromUnitVectors(tm._upAxis, dirNorm);
  }
}

export function getTreadmillRunnerWorldPos(tm, outVec) {
  tm.deckPivot.updateMatrixWorld(true);
  outVec.copy(tm.standLocalOnDeck);
  tm.deckPivot.localToWorld(outVec);
  // Slight downward seat offset on steep incline since knees bend slightly more
  const k = tm.currentInclineDeg / MAX_INCLINE_DEG;
  outVec.y -= 0.022 * k;
  return outVec;
}

export function updateTreadmillSession(tm, keys, dt) {
  // Independent Axis 1: Speed (W/S or ArrowUp/ArrowDown) — NEVER touches incline!
  let speedInput = 0;
  if (keys.has('KeyW') || keys.has('ArrowUp')) speedInput += 1;
  if (keys.has('KeyS') || keys.has('ArrowDown')) speedInput -= 1;
  if (speedInput !== 0) {
    tm.targetSpeedKmh = THREE.MathUtils.clamp(
      tm.targetSpeedKmh + speedInput * 4.5 * dt,
      MIN_SPEED_KMH,
      MAX_SPEED_KMH
    );
  }

  // Independent Axis 2: Incline (D/A or ArrowRight/ArrowLeft) — NEVER touches speed!
  let inclineInput = 0;
  if (keys.has('KeyD') || keys.has('ArrowRight')) inclineInput += 1;
  if (keys.has('KeyA') || keys.has('ArrowLeft')) inclineInput -= 1;
  if (inclineInput !== 0) {
    tm.targetInclineDeg = THREE.MathUtils.clamp(
      tm.targetInclineDeg + inclineInput * 14.0 * dt,
      MIN_INCLINE_DEG,
      MAX_INCLINE_DEG
    );
  }

  // Smooth physical acceleration / motor lift
  const maxSpeedStep = 6.0 * dt;
  tm.currentSpeedKmh += THREE.MathUtils.clamp(
    tm.targetSpeedKmh - tm.currentSpeedKmh,
    -maxSpeedStep,
    maxSpeedStep
  );

  const maxInclineStep = 14.0 * dt;
  tm.currentInclineDeg += THREE.MathUtils.clamp(
    tm.targetInclineDeg - tm.currentInclineDeg,
    -maxInclineStep,
    maxInclineStep
  );

  // Scroll belt proportionally to real speed (m/s)
  const speedMs = tm.currentSpeedKmh / 3.6;
  tm.beltTex.offset.y = (tm.beltTex.offset.y - speedMs * dt * 0.62) % 1;

  applyTreadmillGeometry(tm);
}

export function resetTreadmillOnEnter(tm) {
  // Start in a calm flat walk (4.5 km/h, 0°) so user can independently adjust speed or incline
  tm.targetSpeedKmh = DEFAULT_SPEED_KMH;
  tm.currentSpeedKmh = DEFAULT_SPEED_KMH;
  tm.targetInclineDeg = DEFAULT_INCLINE_DEG;
  tm.currentInclineDeg = DEFAULT_INCLINE_DEG;
  applyTreadmillGeometry(tm);
}

export function getSpeedModeLabel(speedKmh) {
  if (speedKmh < 0.25) return '정지';
  if (speedKmh < 5.5) return '걷기';
  if (speedKmh < 8.2) return '조깅';
  return '달리기';
}

export { MIN_SPEED_KMH, MAX_SPEED_KMH, MIN_INCLINE_DEG, MAX_INCLINE_DEG };
