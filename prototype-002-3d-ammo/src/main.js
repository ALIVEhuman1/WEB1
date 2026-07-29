// main.js — 진입점, 씬 초기화, 게임 루프.
import * as THREE from 'three';
import { CONFIG } from './config.js';
import { createArena } from './core/arena.js';
import { CameraRig } from './core/camera.js';
import { Input } from './core/input.js';
import { createPlayer, facePlayer } from './entities/player.js';
import { createEnemy, disposeEnemy } from './entities/enemy.js';
import { BulletManager } from './entities/bullet.js';
import { WeaponController } from './systems/weapons.js';
import { AmmoController } from './systems/ammo.js';
import { applyDamage, applyTickDamage } from './systems/damage.js';
import { WaveController } from './systems/waves.js';
import { VFX } from './systems/vfx.js';
import { HUD } from './ui/hud.js';

// ---- 렌더러 ----
const app = document.getElementById('app');
const renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: 'high-performance' });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.setClearColor(0x0a0c10);
app.appendChild(renderer.domElement);

const scene = new THREE.Scene();
scene.fog = new THREE.Fog(0x0a0c10, 55, 90);

// ---- 카메라 / 아레나 / 플레이어 ----
const rig = new CameraRig(window.innerWidth / window.innerHeight);
const arena = createArena(scene);
const player = createPlayer(scene);

// 대시 잔상용 지오메트리(플레이어 몸통과 동일)
const trailGeo = new THREE.CapsuleGeometry(
  CONFIG.player.radius, CONFIG.player.height - CONFIG.player.radius * 2, 4, 8,
);

const vfx = new VFX(scene, rig.cam, trailGeo);
const input = new Input(renderer.domElement, rig.cam, arena.groundPlane);
const weapon = new WeaponController();
const ammo = new AmmoController();
const bullets = new BulletManager(scene);
const hud = new HUD();

// ---- 게임 상태 ----
let enemies = [];
let kills = 0;
let hitStop = 0;

// 방향광이 플레이어를 따라가게 해서 그림자가 항상 화면 안에 들어오게 한다.
function updateShadowTarget() {
  arena.dirLight.position.set(
    player.pos.x + CONFIG.light.dirPosition.x,
    CONFIG.light.dirPosition.y,
    player.pos.z + CONFIG.light.dirPosition.z,
  );
  arena.dirLight.target.position.set(player.pos.x, 0, player.pos.z);
  arena.dirLight.target.updateMatrixWorld();
}

// ---- 공유 컨텍스트(world): damage/ammo/bullet 이 함께 쓴다 ----
const world = {
  enemies,
  bullets,
  vfx,
  camera: rig,
  requestHitStop(t) { hitStop = Math.max(hitStop, t); },
  onKill(e) { kills += 1; },
  // 기본공격/철갑탄 탄이 적에 명중했을 때
  resolveHit(e, bullet) {
    applyDamage(e, bullet.damage, {
      isSkill: bullet.isSkill,
      knockDir: bullet.dir,
      knockback: bullet.knockback,
      burn: bullet.burn,
    }, world);
  },
  spawnEnemy(type, wave, pos) {
    const e = createEnemy(scene, type, wave, pos);
    enemies.push(e);
  },
  onWaveStart(n) { hud.banner(`WAVE ${n}`, `적 ${CONFIG.waves.countBase + n * CONFIG.waves.countPerWave}마리`); },
};

const waves = new WaveController(world);

// ---- 조준 총구 위치 ----
const muzzle = new THREE.Vector3();
function muzzleOrigin() {
  muzzle.set(
    player.pos.x + player.facing.x * (player.radius + 0.7),
    CONFIG.bullet.y,
    player.pos.z + player.facing.z * (player.radius + 0.7),
  );
  return muzzle;
}

// ---- 입력 처리 ----
const moveVec = new THREE.Vector3();
const _sep = new THREE.Vector3();
const _dir = new THREE.Vector3();

function handleInput(dt) {
  // 총 교체
  if (input.pressed('1')) weapon.switchTo('shotgun');
  if (input.pressed('2')) weapon.switchTo('sniper');
  if (input.pressed('r')) weapon.reload();

  // 대시
  if (input.pressed(' ') && player.dashCd <= 0) startDash();

  // 스킬 (현재 든 총으로 분기)
  if (input.pressed('q')) {
    if (ammo.cast('incendiary', weapon.current, world, muzzleOrigin(), player.facing)) {
      /* 성공 */
    }
  }
  if (input.pressed('e')) {
    ammo.cast('ap', weapon.current, world, muzzleOrigin(), player.facing);
  }

  // 기본공격(좌클릭 홀드 연사)
  if (input.mouseDown) {
    weapon.tryFire(muzzleOrigin(), player.facing, world);
  }
}

function startDash() {
  player.dashTime = CONFIG.dash.duration;
  player.invuln = CONFIG.dash.duration;
  player.dashCd = CONFIG.dash.cooldown;
  player.trailTimer = 0;
  // 이동 입력 방향, 없으면 조준 방향
  input.moveVector(moveVec);
  if (moveVec.lengthSq() > 1e-4) player.dashDir.copy(moveVec).normalize();
  else player.dashDir.copy(player.facing);
  rig.addShake(CONFIG.shake.dashTrail);
}

// ---- 플레이어 이동 ----
function updatePlayer(dt) {
  facePlayer(player, input.aimPoint);

  let speed = CONFIG.player.moveSpeed;
  if (player.dashTime > 0) {
    speed *= CONFIG.dash.speedMult;
    player.pos.x += player.dashDir.x * speed * dt;
    player.pos.z += player.dashDir.z * speed * dt;
    player.dashTime -= dt;
    // 잔상
    player.trailTimer -= dt;
    if (player.trailTimer <= 0) {
      vfx.addTrail(player.pos.x, player.pos.z, player.group.rotation.y, CONFIG.player.color);
      player.trailTimer = CONFIG.dash.trailInterval;
    }
  } else {
    input.moveVector(moveVec);
    player.pos.x += moveVec.x * speed * dt;
    player.pos.z += moveVec.z * speed * dt;
  }

  // 경계 clamp
  const lim = CONFIG.arena.half - player.radius - 0.5;
  player.pos.x = Math.max(-lim, Math.min(lim, player.pos.x));
  player.pos.z = Math.max(-lim, Math.min(lim, player.pos.z));

  if (player.dashCd > 0) player.dashCd -= dt;
  if (player.invuln > 0) player.invuln -= dt;
  if (player.hurtCooldown > 0) player.hurtCooldown -= dt;
}

// ---- 적 업데이트 ----
function updateEnemies(dt) {
  const n = enemies.length;
  for (let i = 0; i < n; i++) {
    const e = enemies[i];
    if (!e.alive) continue;

    // 화상 DoT
    if (e.burnTime > 0) {
      applyTickDamage(e, e.burnDps * dt, world);
      e.burnTime -= dt;
      e.halo.visible = true;
      if (!e.alive) continue;
    } else if (e.halo.visible) {
      e.halo.visible = false;
    }

    // 넉백 적용 & 감쇠
    if (e.knock.lengthSq() > 1e-4) {
      e.pos.x += e.knock.x * dt;
      e.pos.z += e.knock.z * dt;
      const d = Math.max(0, 1 - CONFIG.enemy.knockDecay * dt);
      e.knock.multiplyScalar(d);
    }

    // 플레이어를 향해 직진
    _dir.set(player.pos.x - e.pos.x, 0, player.pos.z - e.pos.z);
    const distToP = _dir.length();
    if (distToP > 1e-3) {
      _dir.multiplyScalar(1 / distToP);
      e.pos.x += _dir.x * e.speed * dt;
      e.pos.z += _dir.z * e.speed * dt;
    }

    // 접촉 피해
    if (e.contactTimer > 0) e.contactTimer -= dt;
    const hitR = e.radius + player.radius;
    if (distToP < hitR && e.contactTimer <= 0) {
      e.contactTimer = e.contactCooldown;
      if (player.invuln <= 0 && player.hurtCooldown <= 0) hurtPlayer(e.contactDamage);
    }

    // 피격 스케일 펀치
    if (e.hitFlash > 0) {
      e.hitFlash -= dt;
      const s = 1 + Math.max(0, e.hitFlash) * 2.2;
      e.mesh.scale.setScalar(s);
    } else if (e.mesh.scale.x !== 1) {
      e.mesh.scale.setScalar(1);
    }

    // 경계 clamp
    const lim = CONFIG.arena.half - e.radius;
    e.pos.x = Math.max(-lim, Math.min(lim, e.pos.x));
    e.pos.z = Math.max(-lim, Math.min(lim, e.pos.z));
  }

  // 적끼리 겹침 방지(간단한 분리)
  for (let i = 0; i < n; i++) {
    const a = enemies[i];
    if (!a.alive) continue;
    for (let j = i + 1; j < n; j++) {
      const b = enemies[j];
      if (!b.alive) continue;
      const dx = b.pos.x - a.pos.x, dz = b.pos.z - a.pos.z;
      const min = a.radius + b.radius;
      const d2 = dx * dx + dz * dz;
      if (d2 > 1e-6 && d2 < min * min) {
        const d = Math.sqrt(d2);
        const push = (min - d) * 0.5 * CONFIG.enemy.separation;
        const nx = dx / d, nz = dz / d;
        a.pos.x -= nx * push; a.pos.z -= nz * push;
        b.pos.x += nx * push; b.pos.z += nz * push;
      }
    }
  }

  // 죽은 적 정리
  if (enemies.some((e) => !e.alive)) {
    const keep = [];
    for (const e of enemies) {
      if (e.alive) keep.push(e);
      else disposeEnemy(scene, e);
    }
    enemies.length = 0;
    for (const e of keep) enemies.push(e);
  }
}

// ---- 화염 장판 지속 피해 ----
function tickFirePatches(dt) {
  const patches = vfx.fire.patches;
  if (!patches.length || !enemies.length) return;
  for (const p of patches) {
    const r = p.radius + 0.0;
    for (const e of enemies) {
      if (!e.alive) continue;
      const dx = e.pos.x - p.x, dz = e.pos.z - p.z;
      if (dx * dx + dz * dz <= r * r) {
        applyTickDamage(e, p.dps * dt, world);
      }
    }
  }
}

// ---- 플레이어 피격 ----
function hurtPlayer(amount) {
  player.hp -= amount;
  player.hurtCooldown = CONFIG.player.hurtInvuln;
  rig.addShake(CONFIG.shake.hurt);
  vfx.damageNumber(player.pos.x, 2.0, player.pos.z, amount, { color: '#ff4d5e' });
  if (player.hp <= 0) resetGame();
}

function resetGame() {
  hud.banner('게임 오버', `처치 ${kills} · WAVE ${waves.wave} 에서 재시작`);
  for (const e of enemies) disposeEnemy(scene, e);
  enemies.length = 0;
  player.hp = player.maxHp;
  player.pos.set(0, 0, 0);
  kills = 0;
  weapon.mag.shotgun = CONFIG.guns.shotgun.magSize;
  weapon.mag.sniper = CONFIG.guns.sniper.magSize;
  ammo.charges.incendiary = CONFIG.ammo.incendiary.maxCharges;
  ammo.charges.ap = CONFIG.ammo.ap.maxCharges;
  waves.wave = 0;
  waves.state = 'intermission';
  waves.timer = CONFIG.waves.nextWaveDelay;
}

// ---- HUD 상태 취합 ----
function pushHud(dt) {
  hud.update(dt, {
    hp: player.hp, maxHp: player.maxHp,
    gun: weapon.current,
    mag: weapon.mag[weapon.current],
    reloading: weapon.reloading,
    qCharges: ammo.charges.incendiary, qFrac: ammo.rechargeFraction('incendiary'),
    eCharges: ammo.charges.ap, eFrac: ammo.rechargeFraction('ap'),
    wave: waves.wave, remaining: waves.remaining, kills,
    dashReady: player.dashCd <= 0,
    dashCdFrac: Math.max(0, player.dashCd / CONFIG.dash.cooldown),
  });
}

// ---- 루프 ----
const clock = new THREE.Clock();
function frame() {
  const rdt = Math.min(clock.getDelta(), 0.05);

  // 히트스톱: 시뮬레이션을 잠깐 얼려 타격감을 만든다. 카메라 흔들림은 계속.
  const frozen = hitStop > 0;
  if (frozen) hitStop -= rdt;
  const dt = frozen ? 0 : rdt;

  input.updateAim();

  if (!frozen) {
    handleInput(dt);
    weapon.update(dt);
    ammo.update(dt);
    updatePlayer(dt);
    updateEnemies(dt);
    bullets.update(dt, world);
    tickFirePatches(dt);
    waves.update(dt);
  }

  vfx.update(dt);
  updateShadowTarget();
  rig.update(rdt, player.pos, input.aimPoint);
  pushHud(rdt);

  input.endFrame();
  renderer.render(scene, rig.cam);
  requestAnimationFrame(frame);
}

// ---- 리사이즈 ----
window.addEventListener('resize', () => {
  renderer.setSize(window.innerWidth, window.innerHeight);
  rig.onResize(window.innerWidth / window.innerHeight);
});

hud.banner('프로토타입 002', '탄종 조합 테스트 · 좌클릭으로 시작');
frame();
