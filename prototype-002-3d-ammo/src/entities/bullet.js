// bullet.js — 이동하는 발사체(기본공격 펠릿/탄, 철갑탄 슬러그).
// 소이탄의 부채꼴/직선은 즉발 판정이라 여기서 다루지 않는다(ammo.js 참고).
// 스윕 판정(선분-원)으로 빠른 탄이 작은 적을 관통해 지나치는 터널링을 막는다.
import * as THREE from 'three';
import { CONFIG } from '../config.js';

// 공유 지오메트리(트레이서 = 가는 실린더를 눕혀서 사용)
const TRACER_GEO = new THREE.CylinderGeometry(1, 1, 1, 6);
TRACER_GEO.rotateX(Math.PI / 2); // +Z 방향으로 눕힘

const _a = new THREE.Vector3();
const _b = new THREE.Vector3();
const _ab = new THREE.Vector3();
const _ap = new THREE.Vector3();

// 점(원 중심)이 선분 [start, start+dir*len] 에 얼마나 가까운지 제곱거리로 반환
function distSqToSegment(cx, cz, sx, sz, dx, dz, len) {
  // 선분 파라미터 t 를 [0,len] 로 clamp
  const t = Math.max(0, Math.min(len, (cx - sx) * dx + (cz - sz) * dz));
  const px = sx + dx * t, pz = sz + dz * t;
  const ex = cx - px, ez = cz - pz;
  return ex * ex + ez * ez;
}

export class BulletManager {
  constructor(scene) {
    this.scene = scene;
    this.bullets = [];
  }

  // opts: { color, radius, damage, range, pierce, speed, knockback, isSkill, burn }
  spawn(origin, dir, opts) {
    const mat = new THREE.MeshBasicMaterial({ color: opts.color });
    const mesh = new THREE.Mesh(TRACER_GEO, mat);
    const len = opts.tracerLen ?? CONFIG.bullet.tracerLen;
    mesh.scale.set(opts.radius, opts.radius, len);
    mesh.position.copy(origin);
    mesh.position.y = CONFIG.bullet.y;
    this.scene.add(mesh);

    const d = _a.copy(dir); d.y = 0; d.normalize();
    // 트레이서가 진행 방향을 향하도록
    mesh.quaternion.setFromUnitVectors(new THREE.Vector3(0, 0, 1), d);

    this.bullets.push({
      mesh, mat,
      pos: new THREE.Vector3(origin.x, CONFIG.bullet.y, origin.z),
      dir: new THREE.Vector3(d.x, 0, d.z),
      speed: opts.speed,
      damage: opts.damage,
      range: opts.range,
      traveled: 0,
      pierce: opts.pierce ?? 0,
      knockback: opts.knockback ?? 0,
      isSkill: !!opts.isSkill,
      burn: opts.burn ?? null,
      radius: opts.radius,
      hitSet: new Set(),
      dead: false,
    });
  }

  // world: { enemies, resolveHit(enemy, bullet) }
  update(dt, world) {
    const enemies = world.enemies;
    for (const b of this.bullets) {
      if (b.dead) continue;
      const step = b.speed * dt;
      const sx = b.pos.x, sz = b.pos.z;
      const dx = b.dir.x, dz = b.dir.z;

      // 이번 프레임 이동 선분에 대해 모든 적을 스윕 판정
      for (const e of enemies) {
        if (!e.alive || b.hitSet.has(e)) continue;
        const rr = e.radius + b.radius;
        const dsq = distSqToSegment(e.pos.x, e.pos.z, sx, sz, dx, dz, step);
        if (dsq <= rr * rr) {
          b.hitSet.add(e);
          world.resolveHit(e, b);
          if (b.pierce <= 0) { b.dead = true; break; }
          b.pierce -= 1;
        }
      }
      if (b.dead) continue;

      // 이동
      b.pos.x += dx * step;
      b.pos.z += dz * step;
      b.mesh.position.set(b.pos.x, CONFIG.bullet.y, b.pos.z);
      b.traveled += step;

      // 사거리/경계 소멸
      if (b.traveled >= b.range || Math.abs(b.pos.x) > CONFIG.arena.half || Math.abs(b.pos.z) > CONFIG.arena.half) {
        b.dead = true;
      }
    }

    // 죽은 탄 정리
    if (this.bullets.length) {
      const keep = [];
      for (const b of this.bullets) {
        if (b.dead) { this.scene.remove(b.mesh); b.mat.dispose(); }
        else keep.push(b);
      }
      this.bullets = keep;
    }
  }
}
