// vfx.js — 파티클, 화염 장판, 데미지 숫자, 총구 섬광.
// "시각적 피드백을 아끼지 말 것." 특히 스택 폭발 순간.
import * as THREE from 'three';
import { CONFIG } from '../config.js';

// ---------------------------------------------------------------------------
// 파티클: 단일 THREE.Points 버퍼에 풀링. AdditiveBlending으로 색을 어둡게 페이드.
// ---------------------------------------------------------------------------
class ParticlePool {
  constructor(scene, capacity = 2400) {
    this.cap = capacity;
    this.positions = new Float32Array(capacity * 3);
    this.colors = new Float32Array(capacity * 3);
    this.vel = new Float32Array(capacity * 3);
    this.life = new Float32Array(capacity);
    this.maxLife = new Float32Array(capacity);
    this.baseCol = new Float32Array(capacity * 3);
    this.head = 0;

    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(this.positions, 3));
    geo.setAttribute('color', new THREE.BufferAttribute(this.colors, 3));
    const mat = new THREE.PointsMaterial({
      size: 0.28, vertexColors: true, transparent: true,
      blending: THREE.AdditiveBlending, depthWrite: false,
    });
    this.points = new THREE.Points(geo, mat);
    this.points.frustumCulled = false;
    scene.add(this.points);
    // 초기엔 전부 화면 밖 + 검정
    for (let i = 0; i < capacity; i++) this.positions[i * 3 + 1] = -999;
  }

  emit(x, y, z, color, count, speed, life, spreadUp = 1) {
    const c = new THREE.Color(color);
    for (let i = 0; i < count; i++) {
      const idx = this.head; this.head = (this.head + 1) % this.cap;
      const p3 = idx * 3;
      this.positions[p3] = x; this.positions[p3 + 1] = y; this.positions[p3 + 2] = z;
      const ang = Math.random() * Math.PI * 2;
      const sp = speed * (0.4 + Math.random() * 0.8);
      this.vel[p3] = Math.cos(ang) * sp;
      this.vel[p3 + 1] = (Math.random() * 0.8 + 0.2) * sp * spreadUp;
      this.vel[p3 + 2] = Math.sin(ang) * sp;
      this.baseCol[p3] = c.r; this.baseCol[p3 + 1] = c.g; this.baseCol[p3 + 2] = c.b;
      this.colors[p3] = c.r; this.colors[p3 + 1] = c.g; this.colors[p3 + 2] = c.b;
      const lf = life * (0.7 + Math.random() * 0.6);
      this.life[idx] = lf; this.maxLife[idx] = lf;
    }
  }

  update(dt) {
    const g = 9.0;
    for (let i = 0; i < this.cap; i++) {
      if (this.life[i] <= 0) continue;
      const p3 = i * 3;
      this.life[i] -= dt;
      if (this.life[i] <= 0) {
        this.positions[p3 + 1] = -999;
        this.colors[p3] = this.colors[p3 + 1] = this.colors[p3 + 2] = 0;
        continue;
      }
      this.vel[p3 + 1] -= g * dt;
      this.positions[p3] += this.vel[p3] * dt;
      this.positions[p3 + 1] += this.vel[p3 + 1] * dt;
      this.positions[p3 + 2] += this.vel[p3 + 2] * dt;
      if (this.positions[p3 + 1] < 0.05) { // 바닥 튕김 약간
        this.positions[p3 + 1] = 0.05; this.vel[p3 + 1] *= -0.3; this.vel[p3] *= 0.6; this.vel[p3 + 2] *= 0.6;
      }
      const t = this.life[i] / this.maxLife[i];
      this.colors[p3] = this.baseCol[p3] * t;
      this.colors[p3 + 1] = this.baseCol[p3 + 1] * t;
      this.colors[p3 + 2] = this.baseCol[p3 + 2] * t;
    }
    this.points.geometry.attributes.position.needsUpdate = true;
    this.points.geometry.attributes.color.needsUpdate = true;
  }
}

// ---------------------------------------------------------------------------
// 화염 장판: 지면에 그려 스킬 형태를 드러낸다(검증 항목 3).
// ---------------------------------------------------------------------------
const PATCH_GEO = new THREE.CircleGeometry(1, 20);
PATCH_GEO.rotateX(-Math.PI / 2);

class FireField {
  constructor(scene) {
    this.scene = scene;
    this.patches = [];
  }

  add(x, z, radius = CONFIG.firePatch.radius, life = CONFIG.firePatch.life) {
    const mat = new THREE.MeshBasicMaterial({
      color: CONFIG.firePatch.color, transparent: true, opacity: 0.7,
      blending: THREE.AdditiveBlending, depthWrite: false,
    });
    const mesh = new THREE.Mesh(PATCH_GEO, mat);
    mesh.position.set(x, 0.03, z);
    mesh.scale.setScalar(radius);
    this.scene.add(mesh);
    this.patches.push({ mesh, mat, x, z, radius, life, maxLife: life, dps: CONFIG.firePatch.dps });
  }

  update(dt) {
    if (!this.patches.length) return;
    const keep = [];
    for (const p of this.patches) {
      p.life -= dt;
      if (p.life <= 0) { this.scene.remove(p.mesh); p.mat.dispose(); continue; }
      const t = p.life / p.maxLife;
      // 깜빡이는 불꽃 느낌
      p.mat.opacity = (0.35 + 0.45 * t) * (0.8 + Math.random() * 0.2);
      p.mesh.scale.setScalar(p.radius * (0.9 + 0.15 * Math.sin(p.life * 18)));
      keep.push(p);
    }
    this.patches = keep;
  }
}

// ---------------------------------------------------------------------------
// 데미지 숫자: 빌보드 스프라이트 풀(각자 캔버스 텍스처를 재사용).
// ---------------------------------------------------------------------------
class DamageNumbers {
  constructor(scene, camera, pool = 48) {
    this.scene = scene;
    this.camera = camera;
    this.items = [];
    this.free = [];
    for (let i = 0; i < pool; i++) {
      const canvas = document.createElement('canvas');
      canvas.width = 256; canvas.height = 128;
      const tex = new THREE.CanvasTexture(canvas);
      const mat = new THREE.SpriteMaterial({ map: tex, transparent: true, depthTest: false, depthWrite: false });
      const sprite = new THREE.Sprite(mat);
      sprite.visible = false;
      scene.add(sprite);
      this.free.push({ canvas, ctx: canvas.getContext('2d'), tex, mat, sprite, life: 0 });
    }
  }

  spawn(x, y, z, value, { big = false, color = '#ffffff' } = {}) {
    const it = this.free.pop();
    if (!it) return;
    const { ctx, canvas } = it;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.font = `800 ${big ? 92 : 60}px "Segoe UI", sans-serif`;
    ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.lineWidth = big ? 10 : 7; ctx.strokeStyle = 'rgba(0,0,0,0.85)';
    ctx.fillStyle = color;
    ctx.shadowColor = color; ctx.shadowBlur = big ? 24 : 0;
    const txt = String(Math.round(value));
    ctx.strokeText(txt, 128, 64);
    ctx.fillText(txt, 128, 64);
    it.tex.needsUpdate = true;
    const s = big ? 2.4 : 1.4;
    it.sprite.scale.set(s * 2, s, 1);
    it.sprite.position.set(x + (Math.random() - 0.5) * 0.6, y, z + (Math.random() - 0.5) * 0.6);
    it.sprite.visible = true;
    it.life = CONFIG.vfx.damageNumberLife;
    it.maxLife = it.life;
    it.big = big;
    this.items.push(it);
  }

  update(dt) {
    if (!this.items.length) return;
    const keep = [];
    for (const it of this.items) {
      it.life -= dt;
      if (it.life <= 0) { it.sprite.visible = false; this.free.push(it); continue; }
      const t = it.life / it.maxLife;
      it.sprite.position.y += CONFIG.vfx.damageNumberRise * dt;
      it.mat.opacity = Math.min(1, t * 2);
      keep.push(it);
    }
    this.items = keep;
  }
}

// ---------------------------------------------------------------------------
// 총구 섬광: PointLight 풀을 40ms 켰다 끈다.
// ---------------------------------------------------------------------------
class MuzzleFlash {
  constructor(scene, count = 4) {
    this.lights = [];
    for (let i = 0; i < count; i++) {
      const l = new THREE.PointLight(CONFIG.vfx.muzzleFlashColor, 0, CONFIG.vfx.muzzleFlashRange, 2);
      l.visible = false;
      scene.add(l);
      this.lights.push({ light: l, timer: 0 });
    }
    this.rr = 0;
  }

  flash(x, y, z, intensity = 1) {
    const item = this.lights[this.rr]; this.rr = (this.rr + 1) % this.lights.length;
    item.light.position.set(x, y, z);
    item.light.intensity = 6 * intensity;
    item.light.visible = true;
    item.timer = CONFIG.vfx.muzzleFlashTime;
  }

  update(dt) {
    for (const it of this.lights) {
      if (it.timer > 0) {
        it.timer -= dt;
        if (it.timer <= 0) { it.light.visible = false; it.light.intensity = 0; }
      }
    }
  }
}

// ---------------------------------------------------------------------------
// 대시 잔상: 반투명 캡슐 스냅샷을 남기고 페이드.
// ---------------------------------------------------------------------------
class TrailPool {
  constructor(scene, geo) {
    this.scene = scene;
    this.geo = geo;
    this.items = [];
  }
  add(x, z, yaw, color = 0x6fd0ff) {
    const mat = new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.45, depthWrite: false });
    const m = new THREE.Mesh(this.geo, mat);
    m.position.set(x, CONFIG.player.height / 2, z);
    m.rotation.y = yaw;
    this.scene.add(m);
    this.items.push({ m, mat, life: CONFIG.dash.trailLife, maxLife: CONFIG.dash.trailLife });
  }
  update(dt) {
    if (!this.items.length) return;
    const keep = [];
    for (const it of this.items) {
      it.life -= dt;
      if (it.life <= 0) { this.scene.remove(it.m); it.mat.dispose(); continue; }
      it.mat.opacity = 0.45 * (it.life / it.maxLife);
      keep.push(it);
    }
    this.items = keep;
  }
}

// ---------------------------------------------------------------------------
// 관통 빔: 직선 스킬이 "직선"임을 강조하는 밝은 메시(짧게 밝았다 사라짐).
// ---------------------------------------------------------------------------
const BEAM_GEO = new THREE.BoxGeometry(1, 1, 1);

class BeamPool {
  constructor(scene) {
    this.scene = scene;
    this.items = [];
  }
  add(origin, dir, length, width, color, life = 0.16) {
    const mat = new THREE.MeshBasicMaterial({
      color, transparent: true, opacity: 0.9,
      blending: THREE.AdditiveBlending, depthWrite: false,
    });
    const m = new THREE.Mesh(BEAM_GEO, mat);
    const d = new THREE.Vector3(dir.x, 0, dir.z).normalize();
    m.scale.set(width, width, length);
    m.position.set(origin.x + d.x * length / 2, CONFIG.bullet.y, origin.z + d.z * length / 2);
    m.quaternion.setFromUnitVectors(new THREE.Vector3(0, 0, 1), d);
    this.scene.add(m);
    this.items.push({ m, mat, life, maxLife: life });
  }
  update(dt) {
    if (!this.items.length) return;
    const keep = [];
    for (const it of this.items) {
      it.life -= dt;
      if (it.life <= 0) { this.scene.remove(it.m); it.mat.dispose(); continue; }
      const t = it.life / it.maxLife;
      it.mat.opacity = 0.9 * t;
      it.m.scale.x = it.m.scale.y = (0.2 + 0.8 * t) * (it._w || 1);
      keep.push(it);
    }
    this.items = keep;
  }
}

// ---------------------------------------------------------------------------
export class VFX {
  constructor(scene, camera, playerGeoForTrail) {
    this.particles = new ParticlePool(scene);
    this.fire = new FireField(scene);
    this.numbers = new DamageNumbers(scene, camera);
    this.muzzle = new MuzzleFlash(scene);
    this.trail = new TrailPool(scene, playerGeoForTrail);
    this.beam = new BeamPool(scene);
  }

  update(dt) {
    this.particles.update(dt);
    this.fire.update(dt);
    this.numbers.update(dt);
    this.muzzle.update(dt);
    this.trail.update(dt);
    this.beam.update(dt);
  }

  addBeam(origin, dir, length, width, color, life) { this.beam.add(origin, dir, length, width, color, life); }

  // 편의 래퍼
  hitBurst(x, y, z, color) {
    this.particles.emit(x, y, z, color, CONFIG.vfx.hitParticles, 4, CONFIG.vfx.particleLife, 0.6);
  }
  popBurst(x, y, z, color) {
    this.particles.emit(x, y, z, color, CONFIG.vfx.popParticles, 8, CONFIG.vfx.particleLife * 1.3, 1.1);
    this.particles.emit(x, y, z, 0xffe08a, 10, 6, CONFIG.vfx.particleLife, 1.2);
  }
  addFire(x, z, radius, life) { this.fire.add(x, z, radius, life); }
  damageNumber(x, y, z, v, opts) { this.numbers.spawn(x, y, z, v, opts); }
  muzzleFlash(x, y, z, i) { this.muzzle.flash(x, y, z, i); }
  addTrail(x, z, yaw, color) { this.trail.add(x, z, yaw, color); }
}
