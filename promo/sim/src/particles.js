import * as THREE from 'three';

function createSoftCircleTexture() {
  const c = document.createElement('canvas');
  c.width = 64;
  c.height = 64;
  const ctx = c.getContext('2d');
  const g = ctx.createRadialGradient(32, 32, 2, 32, 32, 30);
  g.addColorStop(0, 'rgba(255,255,255,0.9)');
  g.addColorStop(0.5, 'rgba(220,240,255,0.45)');
  g.addColorStop(1, 'rgba(220,240,255,0)');
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, 64, 64);
  const tex = new THREE.CanvasTexture(c);
  return tex;
}

export class ShowerFX {
  constructor(scene) {
    this.scene = scene;
    this.active = false;
    this.origin = new THREE.Vector3();

    const tex = createSoftCircleTexture();

    // Water droplets
    this.dropCount = 160;
    this.dropPos = new Float32Array(this.dropCount * 3);
    this.dropVel = new Float32Array(this.dropCount);
    const dropGeo = new THREE.BufferGeometry();
    dropGeo.setAttribute('position', new THREE.BufferAttribute(this.dropPos, 3));
    const dropMat = new THREE.PointsMaterial({
      size: 0.045,
      map: tex,
      transparent: true,
      opacity: 0.75,
      depthWrite: false,
      color: 0xd8f0ff
    });
    this.drops = new THREE.Points(dropGeo, dropMat);
    this.drops.visible = false;
    this.drops.frustumCulled = false;
    scene.add(this.drops);

    // Rising steam
    this.steamCount = 45;
    this.steamPos = new Float32Array(this.steamCount * 3);
    this.steamAge = new Float32Array(this.steamCount);
    const steamGeo = new THREE.BufferGeometry();
    steamGeo.setAttribute('position', new THREE.BufferAttribute(this.steamPos, 3));
    const steamMat = new THREE.PointsMaterial({
      size: 0.42,
      map: tex,
      transparent: true,
      opacity: 0.16,
      depthWrite: false,
      color: 0xeef5ff
    });
    this.steam = new THREE.Points(steamGeo, steamMat);
    this.steam.visible = false;
    this.steam.frustumCulled = false;
    scene.add(this.steam);
  }

  start(headPos) {
    this.origin.set(headPos[0], headPos[1], headPos[2]);
    this.active = true;
    this.drops.visible = true;
    this.steam.visible = true;
    for (let i = 0; i < this.dropCount; i++) {
      this._resetDrop(i, Math.random() * 2.0);
    }
    for (let i = 0; i < this.steamCount; i++) {
      this._resetSteam(i, Math.random());
    }
  }

  stop() {
    this.active = false;
    this.drops.visible = false;
    this.steam.visible = false;
  }

  _resetDrop(i, yOffset = 0) {
    const a = Math.random() * Math.PI * 2;
    const r = Math.random() * 0.16;
    this.dropPos[i * 3] = this.origin.x + Math.cos(a) * r;
    this.dropPos[i * 3 + 1] = this.origin.y - yOffset;
    this.dropPos[i * 3 + 2] = this.origin.z + Math.sin(a) * r;
    this.dropVel[i] = 3.2 + Math.random() * 1.4;
  }

  _resetSteam(i, age = 0) {
    this.steamPos[i * 3] = this.origin.x + (Math.random() - 0.5) * 0.6;
    this.steamPos[i * 3 + 1] = 0.25 + age * 1.8;
    this.steamPos[i * 3 + 2] = this.origin.z + (Math.random() - 0.5) * 0.6;
    this.steamAge[i] = age;
  }

  update(dt) {
    if (!this.active) return;
    for (let i = 0; i < this.dropCount; i++) {
      this.dropPos[i * 3 + 1] -= this.dropVel[i] * dt;
      if (this.dropPos[i * 3 + 1] < 0.02) {
        this._resetDrop(i, 0);
      }
    }
    this.drops.geometry.attributes.position.needsUpdate = true;

    for (let i = 0; i < this.steamCount; i++) {
      this.steamAge[i] += dt * 0.35;
      this.steamPos[i * 3 + 1] += dt * 0.45;
      this.steamPos[i * 3] += Math.sin(this.steamAge[i] * 4 + i) * dt * 0.08;
      if (this.steamAge[i] > 1.0) {
        this._resetSteam(i, 0);
      }
    }
    this.steam.geometry.attributes.position.needsUpdate = true;
  }
}
