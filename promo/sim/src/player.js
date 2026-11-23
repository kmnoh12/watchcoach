import * as THREE from 'three';

const PLAYER_RADIUS = 0.18;
const WALK_SPEED = 1.25;
const RUN_SPEED = 4.3;

export class PlayerController {
  constructor(rootGroup, animations, colliders, raycastMeshes = []) {
    this.root = rootGroup;
    this.colliders = colliders;
    this.raycastMeshes = raycastMeshes;
    this.inSmallRoom = false;
    this.camDist = 2.55;
    this.pos = new THREE.Vector3(0, 0, 2.5);
    this.yaw = 0; // radians, 0 faces -Z (toward main mirror at y=+5 in Blender -> z=-5 in Three)
    this.pitch = 0;
    this.speed = 0;
    this.firstPerson = false;
    this.lockedAction = false; // true while on equipment / shower / toilet / posing
    this.currentClip = 'stand';
    this.onActionEnd = null;

    this._raycaster = new THREE.Raycaster();
    this._rayDir = new THREE.Vector3();

    this.mixer = new THREE.AnimationMixer(rootGroup);
    this.actions = {};
    for (const clip of animations) {
      const act = this.mixer.clipAction(clip);
      this.actions[clip.name] = act;
    }

    // Locate key bones for 1st-person POV and dynamic incline posture adjustment
    this.headBone = null;
    this.bones = {};
    rootGroup.traverse((obj) => {
      if (obj.isMesh) {
        obj.castShadow = true;
        obj.receiveShadow = true;
        obj.frustumCulled = false; // prevents skinned mesh popping in mirrors
      }
      if (obj.isBone) {
        this.bones[obj.name] = obj;
        if (obj.name === 'head') this.headBone = obj;
      }
    });

    this.treadmillMode = false;
    this._treadmillPhase = 0;
    this._treadmillInclineDeg = 0;
    this._treadmillSpeedKmh = 0;
    this._tmpQuat = new THREE.Quaternion();
    this._axisX = new THREE.Vector3(1, 0, 0);

    if (this.actions.stand) {
      this.actions.stand.play();
    }

    this._tmpVec = new THREE.Vector3();
    this._tmpHead = new THREE.Vector3();
    this._camTarget = new THREE.Vector3();
    this._camPos = new THREE.Vector3();
  }

  setSpawn(pos, yaw = 0) {
    this.pos.set(pos[0], pos[1], pos[2]);
    this.yaw = yaw;
    this.root.position.copy(this.pos);
    this.root.rotation.y = this.yaw + Math.PI;
  }

  playClip(name, { once = false, fade = 0.16, onDone = null } = {}) {
    const next = this.actions[name] || this.actions.stand;
    if (!next) return;
    if (this.currentClip === name && !once) return;

    const prev = this.actions[this.currentClip];
    next.reset();
    next.setLoop(once ? THREE.LoopOnce : THREE.LoopRepeat, once ? 1 : Infinity);
    next.clampWhenFinished = once;
    next.enabled = true;
    next.play();
    if (prev && prev !== next) {
      prev.crossFadeTo(next, fade, false);
    }
    this.currentClip = name;

    if (this._finishListener) {
      this.mixer.removeEventListener('finished', this._finishListener);
      this._finishListener = null;
    }

    if (once) {
      this._finishListener = (e) => {
        if (e.action === next) {
          this.mixer.removeEventListener('finished', this._finishListener);
          this._finishListener = null;
          this.lockedAction = false;
          this.playClip('stand', { fade: 0.15 });
          if (onDone) onDone();
        }
      };
      this.mixer.addEventListener('finished', this._finishListener);
    }
  }

  triggerWatchCheck() {
    if (this.lockedAction) return;
    this.lockedAction = true;
    this.playClip('check_watch', { once: true, fade: 0.14 });
  }

  triggerPosing(clipName) {
    this.lockedAction = true;
    this.playClip(clipName, { once: true, fade: 0.18 });
  }

  enterStation(standPos, yaw, clipName) {
    this.lockedAction = true;
    this.speed = 0;
    this.pos.set(standPos[0], standPos[1], standPos[2]);
    this.yaw = yaw;
    this.root.position.copy(this.pos);
    this.root.rotation.y = this.yaw + Math.PI;
    this.playClip(clipName, { once: false, fade: 0.2 });
  }

  enterTreadmill(standPos, yaw) {
    this.lockedAction = true;
    this.treadmillMode = true;
    this._treadmillPhase = 0;
    this._treadmillInclineDeg = 0;
    this._treadmillSpeedKmh = 0;
    this.speed = 0;
    this.pos.set(standPos[0], standPos[1], standPos[2]);
    this.yaw = yaw;
    this.root.position.copy(this.pos);
    this.root.rotation.y = this.yaw + Math.PI;

    // Activate stand, walk, and run simultaneously for seamless phase-synced blending
    for (const [name, act] of Object.entries(this.actions)) {
      if (name === 'stand' || name === 'walk' || name === 'run') {
        act.enabled = true;
        act.setLoop(THREE.LoopRepeat, Infinity);
        act.play();
        act.setEffectiveWeight(name === 'stand' ? 1 : 0);
        act.setEffectiveTimeScale(name === 'stand' ? 1 : 0);
      } else {
        act.stop();
      }
    }
    this.currentClip = 'walk';
  }

  updateTreadmillLocomotion(speedKmh, inclineDeg, worldPos, dt) {
    this._treadmillSpeedKmh = speedKmh;
    this._treadmillInclineDeg = inclineDeg;
    this.pos.copy(worldPos);
    this.root.position.copy(worldPos);

    const standAct = this.actions.stand;
    const walkAct = this.actions.walk;
    const runAct = this.actions.run;
    if (!standAct || !walkAct || !runAct) return;

    const smoothstep = (e0, e1, x) => {
      const t = THREE.MathUtils.clamp((x - e0) / (e1 - e0), 0, 1);
      return t * t * (3 - 2 * t);
    };

    // Pure speed-driven weights: incline NEVER forces running!
    const moveW = smoothstep(0.15, 1.1, speedKmh);
    const runRatio = smoothstep(5.4, 8.2, speedKmh);
    const walkW = (1 - runRatio) * moveW;
    const runW = runRatio * moveW;
    const standW = 1 - moveW;

    standAct.setEffectiveWeight(standW);
    walkAct.setEffectiveWeight(walkW);
    runAct.setEffectiveWeight(runW);

    // Advance shared gait phase so walk <-> run speed transitions stay 100% foot-synced
    const walkDur = walkAct.getClip().duration || 1.33;
    const runDur = runAct.getClip().duration || 0.92;
    const walkCadence = (0.45 + 0.55 * (speedKmh / 4.5)) / walkDur;
    const runCadence = (0.68 + 0.32 * (speedKmh / 10.5)) / runDur;
    const cadence = THREE.MathUtils.lerp(walkCadence, runCadence, runRatio);

    if (moveW > 0.001) {
      this._treadmillPhase = (this._treadmillPhase + cadence * dt) % 1;
    }

    // Drive walk & run directly from shared phase, while stand breathes normally
    standAct.setEffectiveTimeScale(1);
    walkAct.setEffectiveTimeScale(0);
    runAct.setEffectiveTimeScale(0);
    walkAct.time = this._treadmillPhase * walkDur;
    runAct.time = this._treadmillPhase * runDur;
  }

  _applyInclinePosture() {
    if (!this.treadmillMode || this._treadmillInclineDeg <= 0.05) return;

    const k = THREE.MathUtils.clamp(this._treadmillInclineDeg / 30, 0, 1);
    const rad = THREE.MathUtils.degToRad(this._treadmillInclineDeg);
    const moveFactor = THREE.MathUtils.clamp(this._treadmillSpeedKmh / 4.5, 0, 1);

    const pitchBone = (name, angleRad) => {
      const b = this.bones[name];
      if (!b || Math.abs(angleRad) < 1e-5) return;
      this._tmpQuat.setFromAxisAngle(this._axisX, angleRad);
      b.quaternion.multiply(this._tmpQuat);
    };

    // Natural uphill forward torso lean (+X leans forward), counter-pitched head (-X looks ahead)
    const leanScale = 0.65 + 0.35 * moveFactor;
    pitchBone('spine_01', 0.10 * k * leanScale);
    pitchBone('spine_02', 0.11 * k * leanScale);
    pitchBone('spine_03', 0.09 * k * leanScale);
    pitchBone('neck_01', -0.10 * k * leanScale);
    pitchBone('head', -0.12 * k * leanScale);

    // Uphill lower-body drive: deeper knee/hip flexion + ankle dorsiflexion matching deck slope
    const kneeFlex = (0.10 + 0.14 * moveFactor) * k;
    pitchBone('thigh_l', -kneeFlex * 0.85);
    pitchBone('thigh_r', -kneeFlex * 0.85);
    pitchBone('calf_l', kneeFlex * 1.05);
    pitchBone('calf_r', kneeFlex * 1.05);

    // Dorsiflex ankles to align soles smoothly with the inclined deck surface
    const anklePitch = -rad * 0.48;
    pitchBone('foot_l', anklePitch);
    pitchBone('foot_r', anklePitch);
  }

  exitStation() {
    this.lockedAction = false;
    if (this.treadmillMode) {
      this.treadmillMode = false;
      this._treadmillInclineDeg = 0;
      this._treadmillSpeedKmh = 0;
      for (const name of ['stand', 'walk', 'run']) {
        const act = this.actions[name];
        if (!act) continue;
        act.setEffectiveTimeScale(1);
        act.setEffectiveWeight(name === 'stand' ? 1 : 0);
        if (name !== 'stand') act.stop();
      }
      this.currentClip = 'stand';
    }
    this.playClip('stand', { fade: 0.2 });
  }

  _collidesAt(x, z, activeDoors) {
    const r = PLAYER_RADIUS;
    // If standing inside an open doorway zone, allow passing through the cut wall AABB
    let inOpenDoorway = false;
    for (let i = 0; i < activeDoors.length; i++) {
      const d = activeDoors[i];
      if (!d.isOpen) continue;
      if (Math.abs(x - d.pos[0]) < 0.75 && Math.abs(z - d.pos[2]) < 0.75) {
        inOpenDoorway = true;
        break;
      }
    }

    if (!inOpenDoorway) {
      for (let i = 0; i < this.colliders.length; i++) {
        const c = this.colliders[i];
        if (c.disabled) continue;
        if (
          x + r > c.min[0] &&
          x - r < c.max[0] &&
          z + r > c.min[2] &&
          z - r < c.max[2]
        ) {
          return true;
        }
      }
    }
    // Check closed doors as solid barriers
    for (let i = 0; i < activeDoors.length; i++) {
      const d = activeDoors[i];
      if (d.isOpen || !d.box) continue;
      if (
        x + r > d.box.min[0] &&
        x - r < d.box.max[0] &&
        z + r > d.box.min[2] &&
        z - r < d.box.max[2]
      ) {
        return true;
      }
    }
    return false;
  }

  update(dt, keys, camera, activeDoors) {
    if (!this.lockedAction) {
      let fwd = 0;
      let strafe = 0;
      if (keys.has('KeyW') || keys.has('ArrowUp')) fwd += 1;
      if (keys.has('KeyS') || keys.has('ArrowDown')) fwd -= 1;
      if (keys.has('KeyA') || keys.has('ArrowLeft')) strafe -= 1;
      if (keys.has('KeyD') || keys.has('ArrowRight')) strafe += 1;

      const moving = fwd !== 0 || strafe !== 0;
      const running = moving && (keys.has('ShiftLeft') || keys.has('ShiftRight'));

      let alignment = 1;
      if (moving) {
        // Heading is relative to the camera. The model's forward axis is local +Z.
        const heading = this.yaw + Math.atan2(strafe, -fwd);
        const delta = Math.atan2(
          Math.sin(heading - this.root.rotation.y),
          Math.cos(heading - this.root.rotation.y)
        );
        const turn = THREE.MathUtils.clamp(delta, -dt * 8, dt * 8);
        this.root.rotation.y += turn;
        alignment = Math.max(0, Math.cos(delta - turn));
      }
      const targetSpeed = moving ? (running ? RUN_SPEED : WALK_SPEED) * alignment : 0;
      this.speed += THREE.MathUtils.clamp(targetSpeed - this.speed, -18 * dt, 12 * dt);
      const stride = this.speed * dt * alignment;
      const dx = Math.sin(this.root.rotation.y) * stride,
        dz = Math.cos(this.root.rotation.y) * stride;
      const oldX = this.pos.x,
        oldZ = this.pos.z;
      if (stride > 0) {
        const wasInside = this._collidesAt(oldX, oldZ, activeDoors);
        if (wasInside || !this._collidesAt(oldX + dx, oldZ, activeDoors)) this.pos.x += dx;
        if (wasInside || !this._collidesAt(this.pos.x, oldZ + dz, activeDoors)) this.pos.z += dz;
      }
      if (Math.hypot(this.pos.x - oldX, this.pos.z - oldZ) > 0.00001 || (moving && alignment < 0.97)) {
        this.playClip(this.speed > 2.1 ? 'run' : 'walk', { fade: 0.15 });
      } else {
        if (this.firstPerson && !moving) this.root.rotation.y = this.yaw + Math.PI;
        this.playClip('stand', { fade: 0.18 });
      }

      this.root.position.copy(this.pos);
    }

    this.mixer.update(dt);
    this._applyInclinePosture();
    this.root.updateMatrixWorld(true);

    // Camera placement
    if (this.firstPerson) {
      if (this.exerciseHead) {
        this._tmpHead.copy(this.exerciseHead);
      } else if (this.headBone) {
        this.headBone.getWorldPosition(this._tmpHead);
      } else {
        this._tmpHead.set(this.pos.x, this.pos.y + 1.63, this.pos.z);
      }
      // Offset slightly forward of face/cap brim so mesh never clips near plane, while full body reflects in mirrors
      const forwardX = -Math.sin(this.yaw) * 0.15;
      const forwardZ = -Math.cos(this.yaw) * 0.15;
      camera.position.set(
        this._tmpHead.x + forwardX,
        this._tmpHead.y + 0.05,
        this._tmpHead.z + forwardZ
      );
      camera.rotation.order = 'YXZ';
      camera.rotation.y = this.yaw;
      camera.rotation.x = this.pitch;
      camera.rotation.z = 0;
    } else {
      // 3rd-person follow cam: closer shoulder-cam inside small rooms, full-body outside
      const targetDist = this.inSmallRoom ? 1.45 : 2.55;
      this.camDist += (targetDist - this.camDist) * Math.min(1, dt * 8);
      const shoulderHeight = this.inSmallRoom ? 1.48 : 1.52;
      this._camTarget.set(this.pos.x, this.pos.y + shoulderHeight, this.pos.z);

      if (this.exerciseHead) this._camTarget.copy(this.exerciseHead).y -= 0.2;

      const cosP = Math.cos(this.pitch);
      const dirX = Math.sin(this.yaw) * cosP;
      const dirY = -Math.sin(this.pitch);
      const dirZ = Math.cos(this.yaw) * cosP;

      let bestDist = this.camDist;
      if (this.raycastMeshes.length > 0) {
        this._rayDir.set(dirX, dirY, dirZ).normalize();
        this._raycaster.set(this._camTarget, this._rayDir);
        this._raycaster.near = 0.1;
        this._raycaster.far = this.camDist;
        const hits = this._raycaster.intersectObjects(this.raycastMeshes, false);
        const obstacle = hits.find((hit) => hit.object.visible);
        if (obstacle) {
          bestDist = Math.max(0.35, obstacle.distance - 0.16);
        }
      }

      this._camPos.set(
        this._camTarget.x + dirX * bestDist,
        Math.max(0.25, this._camTarget.y + dirY * bestDist),
        this._camTarget.z + dirZ * bestDist
      );
      camera.position.lerp(this._camPos, Math.min(1, dt * 20));
      camera.lookAt(this._camTarget);
    }
  }
}
