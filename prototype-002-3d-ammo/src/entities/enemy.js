// enemy.js — 적 2종. 지오메트리/머티리얼을 공유해 100마리+ 를 감당한다.
import * as THREE from 'three';
import { CONFIG } from '../config.js';

// ---- 공유 리소스 (한 번만 생성) ----
const GEO = {
  normal: new THREE.CapsuleGeometry(CONFIG.enemy.normal.radius, 0.7, 4, 10),
  elite: new THREE.CapsuleGeometry(CONFIG.enemy.elite.radius, 1.1, 5, 12),
  halo: new THREE.CylinderGeometry(0.75, 0.75, 0.02, 16),
};
const MAT = {
  normal: new THREE.MeshStandardMaterial({ color: CONFIG.enemy.normal.color, roughness: 0.7 }),
  elite: new THREE.MeshStandardMaterial({ color: CONFIG.enemy.elite.color, roughness: 0.55, metalness: 0.1 }),
  halo: new THREE.MeshBasicMaterial({ color: 0xff6a2a, transparent: true, opacity: 0.55, depthWrite: false }),
};

// ---- 취약 스택 스프라이트 텍스처를 0..max 개까지 미리 굽는다 ----
const STACK_MATS = [];
(function bakeStackSprites() {
  const max = CONFIG.vuln.max;
  const col = '#' + new THREE.Color(CONFIG.vuln.dotColor).getHexString();
  for (let n = 0; n <= max; n++) {
    const w = 128, h = 32;
    const c = document.createElement('canvas');
    c.width = w; c.height = h;
    const ctx = c.getContext('2d');
    const r = 7, gap = 20;
    const totalW = (max - 1) * gap;
    const startX = w / 2 - totalW / 2;
    for (let i = 0; i < max; i++) {
      const x = startX + i * gap, y = h / 2;
      ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2);
      if (i < n) {
        ctx.fillStyle = col;
        ctx.shadowColor = col; ctx.shadowBlur = 10;
        ctx.fill(); ctx.shadowBlur = 0;
      } else {
        ctx.fillStyle = 'rgba(255,255,255,0.18)';
        ctx.fill();
      }
    }
    const tex = new THREE.CanvasTexture(c);
    STACK_MATS[n] = new THREE.SpriteMaterial({ map: tex, transparent: true, depthTest: false, depthWrite: false });
  }
})();

export function createEnemy(scene, type, wave, pos) {
  const cfg = type === 'elite' ? CONFIG.enemy.elite : CONFIG.enemy.normal;
  const mesh = new THREE.Mesh(GEO[type], MAT[type]);
  mesh.castShadow = true;
  mesh.receiveShadow = false;
  const bodyY = cfg.radius + (type === 'elite' ? 0.55 : 0.35);
  mesh.position.set(pos.x, bodyY, pos.z);
  scene.add(mesh);

  // 화상 표시용 할로(바닥 근처, 필요할 때만 보임)
  const halo = new THREE.Mesh(GEO.halo, MAT.halo);
  halo.position.y = -bodyY + 0.03;
  halo.visible = false;
  mesh.add(halo);

  // 취약 스택 스프라이트(머리 위)
  const sprite = new THREE.Sprite(STACK_MATS[0]);
  sprite.scale.set(1.4, 0.35, 1);
  sprite.position.y = bodyY + (type === 'elite' ? 1.35 : 1.05);
  sprite.visible = false;
  mesh.add(sprite);

  const speed = type === 'elite'
    ? cfg.speed
    : cfg.speedMin + Math.random() * (cfg.speedMax - cfg.speedMin);
  const maxHp = cfg.hpBase + wave * cfg.hpPerWave;

  return {
    type,
    mesh, halo, sprite,
    bodyY,
    radius: cfg.radius,
    speed,
    contactDamage: cfg.contactDamage,
    contactCooldown: cfg.contactCooldown,
    contactTimer: 0,
    hp: maxHp,
    maxHp,
    vuln: 0,
    burnTime: 0,
    burnDps: 0,
    knock: new THREE.Vector3(),
    hitFlash: 0,
    alive: true,
    pos: mesh.position, // 참조 별칭 (x,z가 곧 월드 좌표)
  };
}

// 스택 표시 갱신
export function refreshStackSprite(e) {
  const n = Math.min(e.vuln, CONFIG.vuln.max);
  e.sprite.material = STACK_MATS[n];
  e.sprite.visible = n > 0;
}

export function disposeEnemy(scene, e) {
  scene.remove(e.mesh); // 자식(halo, sprite)도 함께 제거됨
}
