// ammo.js — AMMO 정의 = 스킬. 탄종은 "지금 든 총"으로 발사된다.
// 총 2종 × 탄종 2종 = 4가지 패턴. 이 구조를 코드가 그대로 반영한다:
//   AMMO[ammoKey][gunKey](world, origin, direction)
import * as THREE from 'three';
import { CONFIG, DEG } from '../config.js';
import { applyDamage } from './damage.js';

const _tmp = new THREE.Vector3();

// dir(단위벡터)을 y축 기준 deg 회전
function rotY(x, z, deg, out) {
  const r = deg * DEG, c = Math.cos(r), s = Math.sin(r);
  return out.set(x * c - z * s, 0, x * s + z * c);
}

// 점(cx,cz)이 선분 [ox,oz -> +dir*len] 에 대한 제곱거리
function distSqSeg(cx, cz, ox, oz, dx, dz, len) {
  const t = Math.max(0, Math.min(len, (cx - ox) * dx + (cz - oz) * dz));
  const px = ox + dx * t, pz = oz + dz * t;
  const ex = cx - px, ez = cz - pz;
  return ex * ex + ez * ez;
}

// ---------------------------------------------------------------------------
// 소이탄 (Q)
// ---------------------------------------------------------------------------
function incendiaryShotgun(world, origin, dir) {
  const A = CONFIG.ammo.incendiary, sc = A.shotgun;
  const burn = { dps: A.burnDps, duration: A.burnDuration };

  // 지면에 부채꼴 화염 장판(형태를 드러낸다)
  for (let i = 0; i < sc.patchCount; i++) {
    const t = sc.patchCount === 1 ? 0 : i / (sc.patchCount - 1);
    const ang = -sc.spreadDeg + t * sc.spreadDeg * 2;
    rotY(dir.x, dir.z, ang, _tmp);
    const px = origin.x + _tmp.x * sc.range * 0.78;
    const pz = origin.z + _tmp.z * sc.range * 0.78;
    world.vfx.addFire(px, pz, CONFIG.firePatch.radius * 1.35);
  }

  // 부채꼴 범위 내 적 즉발 피해(스킬 → 스택 소모)
  const cosLimit = Math.cos(sc.spreadDeg * DEG);
  for (const e of world.enemies) {
    if (!e.alive) continue;
    const ex = e.pos.x - origin.x, ez = e.pos.z - origin.z;
    const dist = Math.hypot(ex, ez);
    if (dist > sc.range + e.radius) continue;
    const dot = dist < 1e-4 ? 1 : (ex * dir.x + ez * dir.z) / dist;
    if (dot < cosLimit) continue;
    applyDamage(e, sc.directDamage, {
      isSkill: true, knockDir: null, knockback: 0, burn,
    }, world);
  }

  // 비주얼
  for (let i = 0; i < 3; i++) {
    rotY(dir.x, dir.z, (Math.random() * 2 - 1) * sc.spreadDeg, _tmp);
    world.vfx.particles.emit(origin.x + _tmp.x, CONFIG.bullet.y, origin.z + _tmp.z,
      CONFIG.bullet.incendiaryColor, 6, 5, 0.5, 1);
  }
  world.vfx.muzzleFlash(origin.x, CONFIG.bullet.y, origin.z, 1.2);
  world.camera.addShake(CONFIG.shake.fire * 1.6);
}

function incendiarySniper(world, origin, dir) {
  const A = CONFIG.ammo.incendiary, sc = A.sniper;
  const burn = { dps: A.burnDps, duration: A.burnDuration };
  const dx = dir.x, dz = dir.z;

  // 궤적을 따라 일렬 화염 장판
  for (let i = 0; i < sc.patchCount; i++) {
    const t = (i + 0.5) / sc.patchCount;
    world.vfx.addFire(origin.x + dx * sc.range * t, origin.z + dz * sc.range * t, CONFIG.firePatch.radius);
  }

  // 직선(무한 관통) 위의 적 즉발 피해
  for (const e of world.enemies) {
    if (!e.alive) continue;
    const rr = e.radius + sc.lineWidth;
    if (distSqSeg(e.pos.x, e.pos.z, origin.x, origin.z, dx, dz, sc.range) <= rr * rr) {
      applyDamage(e, sc.directDamage, { isSkill: true, knockDir: dir, knockback: 0, burn }, world);
    }
  }

  // 밝은 관통 빔 + 총구 섬광 + 흔들림
  world.vfx.addBeam(origin, dir, sc.range, 0.5, CONFIG.bullet.incendiaryColor, 0.18);
  world.vfx.muzzleFlash(origin.x, CONFIG.bullet.y, origin.z, 1.4);
  world.camera.addShake(CONFIG.shake.fire * 1.8);
}

// ---------------------------------------------------------------------------
// 철갑탄 (E)
// ---------------------------------------------------------------------------
function apShotgun(world, origin, dir) {
  const sc = CONFIG.ammo.ap.shotgun;
  for (let i = 0; i < sc.slugs; i++) {
    const spread = sc.slugs === 1 ? 0 : (-sc.spreadDeg + (i / (sc.slugs - 1)) * sc.spreadDeg * 2);
    rotY(dir.x, dir.z, spread, _tmp);
    world.bullets.spawn(origin, _tmp, {
      color: CONFIG.bullet.apColor,
      radius: CONFIG.bullet.skillRadius,
      tracerLen: 2.2,
      damage: sc.damage,
      range: CONFIG.guns.shotgun.range * 2.2, // 슬러그는 산탄총보다 멀리
      pierce: sc.pierce,
      speed: sc.bulletSpeed,
      knockback: sc.knockback,
      isSkill: true,
    });
  }
  world.vfx.muzzleFlash(origin.x, CONFIG.bullet.y, origin.z, 1.3);
  world.camera.addShake(CONFIG.shake.fire * 2.0);
}

function apSniper(world, origin, dir) {
  const sc = CONFIG.ammo.ap.sniper;
  world.bullets.spawn(origin, dir, {
    color: CONFIG.bullet.apColor,
    radius: CONFIG.bullet.skillRadius * 1.3,
    tracerLen: 3.2,
    damage: sc.damage,
    range: sc.range,
    pierce: sc.pierce,
    speed: sc.bulletSpeed,
    knockback: sc.knockback,
    isSkill: true,
  });
  world.vfx.addBeam(origin, dir, sc.range, 0.35, CONFIG.bullet.apColor, 0.12);
  world.vfx.muzzleFlash(origin.x, CONFIG.bullet.y, origin.z, 1.5);
  world.camera.addShake(CONFIG.shake.fire * 2.2);
}

// ---------------------------------------------------------------------------
// 스킬 디스패치 테이블 — 설계 핵심 구조를 그대로 반영
// ---------------------------------------------------------------------------
export const AMMO = {
  incendiary: { shotgun: incendiaryShotgun, sniper: incendiarySniper },
  ap: { shotgun: apShotgun, sniper: apSniper },
};

// HUD 한 줄 설명(현재 총 기준으로 스킬이 어떻게 나가는지)
export const AMMO_DESC = {
  incendiary: {
    shotgun: '전방 <b>부채꼴 화염</b> · 화상 도트 + 지면 장판',
    sniper: '<b>직선 관통 발화탄</b> · 궤적에 일렬 화염 장판',
  },
  ap: {
    shotgun: '<b>슬러그 3발</b> 관통 · 강한 넉백 (46×3)',
    sniper: '<b>초장거리 단발</b> 관통 · 150 피해 + 강넉백',
  },
};

// ---------------------------------------------------------------------------
// 충전/재충전 관리
// ---------------------------------------------------------------------------
export class AmmoController {
  constructor() {
    this.charges = {
      incendiary: CONFIG.ammo.incendiary.maxCharges,
      ap: CONFIG.ammo.ap.maxCharges,
    };
    this.rechargeTimer = { incendiary: 0, ap: 0 };
  }

  update(dt) {
    for (const key of ['incendiary', 'ap']) {
      const max = CONFIG.ammo[key].maxCharges;
      if (this.charges[key] < max) {
        this.rechargeTimer[key] += dt;
        if (this.rechargeTimer[key] >= CONFIG.ammo[key].rechargeTime) {
          this.rechargeTimer[key] -= CONFIG.ammo[key].rechargeTime;
          this.charges[key] += 1;
          if (this.charges[key] >= max) this.rechargeTimer[key] = 0;
        }
      }
    }
  }

  rechargeFraction(key) {
    const max = CONFIG.ammo[key].maxCharges;
    if (this.charges[key] >= max) return 1;
    return this.rechargeTimer[key] / CONFIG.ammo[key].rechargeTime;
  }

  // 시전. 성공 시 true.
  cast(ammoKey, gunKey, world, origin, dir) {
    if (this.charges[ammoKey] <= 0) return false;
    this.charges[ammoKey] -= 1;
    AMMO[ammoKey][gunKey](world, origin, dir);
    return true;
  }
}
