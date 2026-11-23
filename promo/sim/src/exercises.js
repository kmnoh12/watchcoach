// Play the phone viewer's paired, Z-up point cache and equipment transforms in gym coordinates.
import * as THREE from 'three';

const source = '/assets/exercises/';
const cache = new Map();
let common;

async function load(path, binary = false) {
  const response = await fetch(source + path);
  if (!response.ok) throw new Error(`운동 자료를 열 수 없어 (${path}, ${response.status})`);
  return binary ? response.arrayBuffer() : response.json();
}

function mesh(vertices, indices, color) {
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(vertices, 3));
  geometry.setIndex(indices);
  geometry.computeVertexNormals();
  const material = new THREE.MeshStandardMaterial({ color, flatShading: true, roughness: 0.72 });
  return new THREE.Mesh(geometry, material);
}

function basis(points, ids) {
  const [a, b, c] = ids.map((i) => new THREE.Vector3().fromArray(points, i * 3));
  const x = b.sub(a).normalize();
  const z = new THREE.Vector3().crossVectors(x, c.sub(a)).normalize();
  return new THREE.Matrix4().makeBasis(x, z.clone().cross(x), z).setPosition(a);
}

function bracket(times, phase) {
  let j = 1;
  while (j < times.length - 1 && times[j] < phase) j++;
  const i = j - 1;
  return [i, j, THREE.MathUtils.clamp((phase - times[i]) / (times[j] - times[i]), 0, 1)];
}

function decode(buffer, count) {
  const header = new DataView(buffer);
  const frames = header.getUint32(4, true);
  const stride = count * 3;
  if (
    header.getUint32(0, true) !== 0x32504757 ||
    header.getUint32(8, true) !== count ||
    frames < 2 ||
    buffer.byteLength !== 40 + 4 * frames + 2 * frames * stride
  )
    throw new Error('운동 프레임 크기가 달라');
  const min = new Float32Array(buffer, 16, 3),
    scale = new Float32Array(buffer, 28, 3);
  const times = new Float32Array(buffer, 40, frames);
  const values = new Uint16Array(buffer, 40 + 4 * frames);
  for (let i = stride; i < values.length; i++) values[i] += values[i - stride];
  return {
    times,
    update(positions, phase) {
      const [a, b, t] = bracket(times, phase);
      for (let k = 0; k < stride; k++) {
        const first = values[a * stride + k];
        positions[k] = min[k % 3] + scale[k % 3] * (first + t * (values[b * stride + k] - first));
      }
    }
  };
}

// Capture the dressed player's current skeleton pose on the phone body's vertex layout.
// Both assets share V6's bind pose, but the phone stores vertices in Blender Z-up.
function standingPoints(base, skeleton, stationMatrix) {
  const toY = new THREE.Matrix4().makeRotationX(-Math.PI / 2);
  const inverse = stationMatrix.clone().invert();
  const matrices = base.bone_names.map((name) => {
    const index = skeleton.bones.findIndex((b) => b.name === name);
    if (index < 0) throw new Error('V6 관절이 없어: ' + name);
    return inverse
      .clone()
      .multiply(skeleton.bones[index].matrixWorld)
      .multiply(skeleton.boneInverses[index])
      .multiply(toY);
  });
  const result = new Float32Array(base.rest.length);
  const rest = new THREE.Vector3(),
    rotated = new THREE.Vector3(),
    point = new THREE.Vector3();
  for (let i = 0; i < base.vertices; i++) {
    rest.fromArray(base.rest, i * 3);
    point.set(0, 0, 0);
    base.joints[i].forEach((joint, k) => {
      point.addScaledVector(rotated.copy(rest).applyMatrix4(matrices[joint]), base.weights[i][k]);
    });
    point.toArray(result, i * 3);
  }
  return result;
}

function centroid(points) {
  const c = new THREE.Vector3();
  for (let k = 0; k < points.length; k += 3) {
    c.x += points[k];
    c.y += points[k + 1];
    c.z += points[k + 2];
  }
  return c.multiplyScalar(3 / points.length);
}

// Align the heading first so a 180-degree turn doesn't fold the body through itself.
function transition(from, to, headIds) {
  function heading(points) {
    const a = headIds[0] * 3,
      b = headIds[1] * 3;
    return Math.atan2(points[b + 1] - points[a + 1], points[b] - points[a]);
  }
  const angle = heading(to) - heading(from),
    yaw = Math.atan2(Math.sin(angle), Math.cos(angle));
  const start = centroid(from),
    end = centroid(to);
  const ax = Math.cos(yaw),
    ay = Math.sin(yaw);
  return (out, t) => {
    t = t * t * (3 - 2 * t);
    const cs = Math.cos((t - 1) * yaw),
      sn = Math.sin((t - 1) * yaw);
    for (let i = 0; i < out.length; i += 3) {
      const x = from[i] - start.x,
        y = from[i + 1] - start.y;
      const bx = (1 - t) * (ax * x - ay * y) + t * (to[i] - end.x);
      const by = (1 - t) * (ay * x + ax * y) + t * (to[i + 1] - end.y);
      out[i] = cs * bx - sn * by + start.x * (1 - t) + end.x * t;
      out[i + 1] = sn * bx + cs * by + start.y * (1 - t) + end.y * t;
      out[i + 2] = from[i + 2] * (1 - t) + to[i + 2] * t;
    }
  };
}

async function build(id, playerRoot) {
  common ??= Promise.all(['base', 'watch', 'manifest'].map((key) => load('human_v5/' + key + '.json'))).catch(
    (e) => {
      common = null;
      throw e;
    }
  );
  const [[base, watch, manifest], machine, buffer] = await Promise.all([
    common,
    load('data/' + id + '.json'),
    load('human_v5/' + id + '.bin', true)
  ]);
  const meta = manifest.clips.find((c) => c.id === id);
  const skin = decode(buffer, base.vertices);
  const root = new THREE.Group();
  const body = mesh(base.rest, base.triangles, 0x63d6de);
  body.frustumCulled = false;
  root.add(body);
  const wrist = new THREE.Group(),
    hat = new THREE.Group();
  for (const p of watch.parts) wrist.add(mesh(p.verts, p.tris, new THREE.Color(...p.color)));
  // Head-only primitives retain the cap and headphones from the dressed player.
  let skeleton;
  playerRoot.traverse((o) => {
    if (o.isSkinnedMesh) skeleton = o.skeleton;
    if (!o.isSkinnedMesh || !o.skeleton || !o.material.name || o.material.name.startsWith('Watch_')) return;
    const joint = o.geometry.attributes.skinIndex,
      weights = o.geometry.attributes.skinWeight;
    for (let i = 0; i < joint.count; i++) {
      if (weights.getX(i) < 0.999 || o.skeleton.bones[joint.getX(i)].name !== 'head') return;
    }
    const piece = new THREE.Mesh(o.geometry, o.material);
    piece.applyMatrix4(o.bindMatrix);
    piece.rotation.x += Math.PI / 2;
    hat.add(piece);
  });
  const headIds = [53, 428, 236]; // widely separated rigid head vertices of the 1,401-vertex body
  const restHead = basis(base.rest, headIds).invert(),
    restWrist = basis(base.rest, watch.anchors).invert();
  root.add(wrist, hat);
  wrist.matrixAutoUpdate = hat.matrixAutoUpdate = false;
  const moving = [];
  for (const part of machine.objects) {
    const obj = mesh(part.verts, part.tris, new THREE.Color(...part.color));
    root.add(obj);
    const steps = part.m.map((values) => {
      const m = new THREE.Matrix4().fromArray(values);
      const p = new THREE.Vector3(),
        q = new THREE.Quaternion(),
        s = new THREE.Vector3();
      m.decompose(p, q, s);
      return { p, q, s };
    });
    obj.position.copy(steps[0].p);
    obj.quaternion.copy(steps[0].q);
    obj.scale.copy(steps[0].s);
    if (steps.length > 1) moving.push({ obj, steps });
  }
  const head = new THREE.Vector3();
  const duration = (meta.playback_ms || 2600) / 1000;
  let startPoints,
    blend,
    leaving = false,
    lastPhase = 0;
  const transitionSeconds = 0.68;
  return {
    root,
    head,
    enter() {
      playerRoot.updateMatrixWorld(true);
      startPoints = standingPoints(base, skeleton, root.matrixWorld);
      const seated = new Float32Array(startPoints.length);
      skin.update(seated, meta.playback_range?.[0] || 0);
      blend = transition(startPoints, seated, headIds);
      leaving = false;
    },
    leave() {
      blend = transition(body.geometry.attributes.position.array.slice(), startPoints, headIds);
      leaving = true;
    },
    update(seconds) {
      const time = (Math.max(0, seconds - transitionSeconds) / duration) % 1;
      const u = 2 * Math.min(time, 1 - time);
      const eased = u < 0.5 ? 2 * u * u : 1 - 2 * (1 - u) ** 2;
      const [lo, hi] = meta.playback_range || [0, 1];
      const phase = leaving ? lastPhase : lo + (hi - lo) * (meta.playback_mode === 'cycle' ? time : eased);
      const attr = body.geometry.attributes.position;
      lastPhase = phase;
      if (leaving || seconds < transitionSeconds) blend(attr.array, Math.min(1, seconds / transitionSeconds));
      else skin.update(attr.array, phase);
      attr.needsUpdate = true;
      wrist.matrix.copy(basis(attr.array, watch.anchors)).multiply(restWrist);
      hat.matrix.copy(basis(attr.array, headIds)).multiply(restHead);
      wrist.matrixWorldNeedsUpdate = hat.matrixWorldNeedsUpdate = true;
      head
        .fromArray(attr.array, headIds[0] * 3)
        .lerp(new THREE.Vector3().fromArray(attr.array, headIds[1] * 3), 0.5);
      root.localToWorld(head);
      for (const { obj, steps } of moving) {
        const f = phase * (steps.length - 1);
        const [a, b, t] =
          steps.length === machine.acts.length
            ? bracket(machine.acts, phase)
            : [Math.floor(f), Math.ceil(f), f % 1];
        obj.position.lerpVectors(steps[a].p, steps[b].p, t);
        obj.quaternion.slerpQuaternions(steps[a].q, steps[b].q, t);
        obj.scale.lerpVectors(steps[a].s, steps[b].s, t);
      }
      return leaving && seconds >= transitionSeconds;
    }
  };
}

export function loadExercise(id, playerRoot) {
  if (!cache.has(id))
    cache.set(
      id,
      build(id, playerRoot).catch((e) => {
        cache.delete(id);
        throw e;
      })
    );
  return cache.get(id);
}
