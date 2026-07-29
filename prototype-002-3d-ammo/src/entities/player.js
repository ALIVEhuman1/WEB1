// player.js — 이동, 조준 지향, 대시(무적 + 잔상).
import * as THREE from 'three';
import { CONFIG } from '../config.js';

export function createPlayer(scene) {
  const p = CONFIG.player;
  const group = new THREE.Group();

  // 몸통(캡슐)
  const body = new THREE.Mesh(
    new THREE.CapsuleGeometry(p.radius, p.height - p.radius * 2, 4, 12),
    new THREE.MeshStandardMaterial({ color: p.color, roughness: 0.5, metalness: 0.1 }),
  );
  body.position.y = p.height / 2;
  body.castShadow = true;
  group.add(body);

  // 조준 방향 표시(총구 방향으로 뻗은 짧은 막대)
  const barrel = new THREE.Mesh(
    new THREE.BoxGeometry(0.18, 0.18, 0.9),
    new THREE.MeshStandardMaterial({ color: 0xffffff, roughness: 0.4 }),
  );
  barrel.position.set(0, p.height * 0.55, 0.55);
  barrel.castShadow = true;
  const aimPivot = new THREE.Group();
  aimPivot.add(barrel);
  aimPivot.position.y = 0;
  group.add(aimPivot);

  group.position.set(0, 0, 0);
  scene.add(group);

  return {
    group, body, aimPivot,
    pos: group.position,
    hp: p.maxHp,
    maxHp: p.maxHp,
    radius: p.radius,
    // 대시 상태
    dashTime: 0,       // 남은 대시 지속
    dashCd: 0,         // 남은 쿨다운
    invuln: 0,         // 남은 무적(대시/피격)
    dashDir: new THREE.Vector3(),
    trailTimer: 0,
    facing: new THREE.Vector3(0, 0, 1),
    hurtCooldown: 0,   // 접촉 피해 도트 방지
  };
}

// 조준 지점을 바라보도록 회전
export function facePlayer(player, aimPoint) {
  const dx = aimPoint.x - player.pos.x;
  const dz = aimPoint.z - player.pos.z;
  if (dx * dx + dz * dz > 1e-5) {
    const yaw = Math.atan2(dx, dz);
    player.group.rotation.y = yaw;
    player.facing.set(Math.sin(yaw), 0, Math.cos(yaw));
  }
}
