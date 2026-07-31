// player.js — 이동, 조준 지향, 대시(무적 + 잔상).
// 주인공은 프리미티브(박스/캡슐/구)로 만든 간단한 사람 형태.
// +Z 를 정면으로 두고 만든다(group.rotation.y = 조준 yaw 로 통째 회전).
import * as THREE from 'three';
import { CONFIG } from '../config.js';

function mat(color, rough = 0.6, metal = 0.05) {
  return new THREE.MeshStandardMaterial({ color, roughness: rough, metalness: metal });
}

export function createPlayer(scene) {
  const p = CONFIG.player;
  const C = p.parts;
  const group = new THREE.Group();

  const bodyMat = mat(C.body);
  const legMat = mat(C.legs, 0.7);
  const headMat = mat(C.head, 0.55);
  const gunMat = mat(C.gun, 0.4, 0.3);

  const add = (mesh, x, y, z) => {
    mesh.position.set(x, y, z);
    mesh.castShadow = true;
    group.add(mesh);
    return mesh;
  };

  // 다리 2개
  const legGeo = new THREE.CapsuleGeometry(0.11, 0.5, 3, 8);
  add(new THREE.Mesh(legGeo, legMat), -0.14, 0.38, 0);
  add(new THREE.Mesh(legGeo, legMat), 0.14, 0.38, 0);

  // 골반 → 몸통
  add(new THREE.Mesh(new THREE.BoxGeometry(0.42, 0.2, 0.28), legMat), 0, 0.74, 0);
  const torso = add(new THREE.Mesh(new THREE.CapsuleGeometry(0.24, 0.32, 4, 10), bodyMat), 0, 1.06, 0.02);

  // 어깨 라인
  add(new THREE.Mesh(new THREE.BoxGeometry(0.62, 0.16, 0.26), bodyMat), 0, 1.28, 0);

  // 목 + 머리
  add(new THREE.Mesh(new THREE.CylinderGeometry(0.08, 0.09, 0.1, 8), headMat), 0, 1.4, 0);
  add(new THREE.Mesh(new THREE.SphereGeometry(0.2, 16, 14), headMat), 0, 1.58, 0.01);
  // 시선/정면 표시(작은 챙)
  add(new THREE.Mesh(new THREE.BoxGeometry(0.26, 0.06, 0.14), gunMat), 0, 1.58, 0.16);

  // 팔 2개 — 총을 앞으로 든 자세(정면 +Z)
  const armGeo = new THREE.CapsuleGeometry(0.075, 0.34, 3, 8);
  const leftArm = new THREE.Mesh(armGeo, bodyMat);
  leftArm.position.set(-0.3, 1.16, 0.16);
  leftArm.rotation.x = -1.15; // 앞으로 뻗음
  leftArm.castShadow = true; group.add(leftArm);
  const rightArm = new THREE.Mesh(armGeo, bodyMat);
  rightArm.position.set(0.24, 1.16, 0.18);
  rightArm.rotation.x = -1.15;
  rightArm.castShadow = true; group.add(rightArm);

  // 손에 든 총(정면으로 뻗은 막대) — 조준 방향 표시 겸용
  const gun = new THREE.Mesh(new THREE.BoxGeometry(0.14, 0.16, 0.7), gunMat);
  gun.position.set(0.05, 1.12, 0.55);
  gun.castShadow = true; group.add(gun);
  // 총열 끝
  add(new THREE.Mesh(new THREE.BoxGeometry(0.08, 0.08, 0.28), gunMat), 0.05, 1.12, 0.95);

  group.position.set(0, 0, 0);
  scene.add(group);

  return {
    group, body: torso,
    pos: group.position,
    hp: p.maxHp,
    maxHp: p.maxHp,
    radius: p.radius,
    // 대시 상태
    dashTime: 0,
    dashCd: 0,
    invuln: 0,
    dashDir: new THREE.Vector3(),
    trailTimer: 0,
    facing: new THREE.Vector3(0, 0, 1),
    hurtCooldown: 0,
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
