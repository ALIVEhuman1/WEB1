// weapons.js — GUNS 정의 = 기본공격. 총마다 손맛이 달라야 한다.
// 기본공격 명중 시마다 취약 스택 +1 (실제 스택 처리는 damage.js).
import * as THREE from 'three';
import { CONFIG } from '../config.js';

const _dir = new THREE.Vector3();

// dir 을 y축 기준 deg 만큼 회전한 새 방향을 out 에 쓴다.
function rotateY(out, x, z, deg) {
  const r = deg * Math.PI / 180;
  const c = Math.cos(r), s = Math.sin(r);
  out.set(x * c - z * s, 0, x * s + z * c);
  return out;
}

export class WeaponController {
  constructor() {
    this.guns = CONFIG.guns;
    this.current = 'shotgun';
    this.mag = { shotgun: CONFIG.guns.shotgun.magSize, sniper: CONFIG.guns.sniper.magSize };
    this.fireTimer = 0;
    this.reloadTimer = 0;
    this.reloading = false;
  }

  get gun() { return this.guns[this.current]; }

  switchTo(key) {
    if (key === this.current || !this.guns[key]) return;
    this.current = key;
    // 총 교체 시 진행 중이던 재장전은 취소(무기별 탄창은 각자 유지)
    this.reloading = false;
    this.reloadTimer = 0;
    this.fireTimer = Math.max(this.fireTimer, 0.12); // 교체 딜레이 약간
  }

  reload() {
    const g = this.gun;
    if (this.reloading || this.mag[this.current] >= g.magSize) return;
    this.reloading = true;
    this.reloadTimer = g.reload;
  }

  update(dt) {
    if (this.fireTimer > 0) this.fireTimer -= dt;
    if (this.reloading) {
      this.reloadTimer -= dt;
      if (this.reloadTimer <= 0) {
        this.mag[this.current] = this.gun.magSize;
        this.reloading = false;
      }
    }
  }

  canFire() {
    return !this.reloading && this.fireTimer <= 0 && this.mag[this.current] > 0;
  }

  // origin, dir: 월드 기준. world: { bullets, vfx, camera }
  tryFire(origin, dir, world) {
    if (!this.canFire()) {
      // 탄창 비었으면 자동 재장전
      if (!this.reloading && this.mag[this.current] <= 0) this.reload();
      return false;
    }
    const g = this.gun;
    this.mag[this.current] -= 1;
    this.fireTimer = g.fireInterval;

    const dx = dir.x, dz = dir.z;
    for (let i = 0; i < g.pellets; i++) {
      const spread = g.spreadDeg ? (Math.random() * 2 - 1) * g.spreadDeg : 0;
      rotateY(_dir, dx, dz, spread);
      world.bullets.spawn(origin, _dir, {
        color: CONFIG.bullet.basicColor,
        radius: CONFIG.bullet.basicRadius,
        tracerLen: CONFIG.bullet.tracerLen,
        damage: g.damage,
        range: g.range,
        pierce: g.pierce,
        speed: g.bulletSpeed,
        isSkill: false,      // 기본공격 → 스택 적립
      });
    }

    // 총구 섬광 + 흔들림
    world.vfx.muzzleFlash(origin.x, CONFIG.bullet.y, origin.z, g.muzzleFlash);
    world.camera.addShake(CONFIG.shake.fire * g.shakeMult);

    if (this.mag[this.current] <= 0) this.reload();
    return true;
  }
}
