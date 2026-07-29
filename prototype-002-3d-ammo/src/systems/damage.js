// damage.js — 피해 적용, 취약 스택 처리, 사망. 게임의 핵심 리듬이 여기 있다.
//   기본공격 명중 → 스택 +1 (최대 5)
//   스킬 명중     → 스택 전부 소모, 스택당 피해 +25%  (가장 기분 좋은 순간)
import * as THREE from 'three';
import { CONFIG } from '../config.js';
import { refreshStackSprite } from '../entities/enemy.js';

const _kn = new THREE.Vector3();

// 기본공격이 명중했을 때 취약 스택을 쌓는다("판 까는 시간").
function addVulnStack(e) {
  if (e.vuln < CONFIG.vuln.max) {
    e.vuln += 1;
    refreshStackSprite(e);
  }
}

// enemy 에 피해를 준다.
// opts: { isSkill, knockDir(Vector3|null), knockback, burn:{dps,duration}|null, world }
export function applyDamage(e, baseAmount, opts, ctx) {
  if (!e.alive) return;
  const { vfx } = ctx;

  let dmg = baseAmount;
  let popped = false;
  let poppedStacks = 0;

  if (opts.isSkill) {
    // 스킬 명중 → 스택 소모 & 배율
    if (e.vuln > 0) {
      poppedStacks = e.vuln;
      dmg *= 1 + CONFIG.vuln.dmgPerStack * e.vuln;
      e.vuln = 0;
      refreshStackSprite(e);
      popped = true;
    }
  } else {
    addVulnStack(e);
  }

  e.hp -= dmg;

  // 넉백
  if (opts.knockback && opts.knockDir) {
    _kn.copy(opts.knockDir); _kn.y = 0;
    if (_kn.lengthSq() > 1e-5) {
      _kn.normalize().multiplyScalar(opts.knockback);
      e.knock.add(_kn);
    }
  }

  // 화상 DoT
  if (opts.burn) {
    e.burnTime = Math.max(e.burnTime, opts.burn.duration);
    e.burnDps = Math.max(e.burnDps, opts.burn.dps);
  }

  // 피격 플래시(스케일 펀치)
  e.hitFlash = 0.08;

  // ---- 피드백 ----
  const hx = e.pos.x, hy = e.bodyY + 0.6, hz = e.pos.z;
  if (popped) {
    // 스택 폭발: 큰 숫자 + 색 파티클 폭발 + 화면 흔들림 + 히트스톱
    vfx.damageNumber(hx, hy + 0.4, hz, dmg, { big: true, color: '#ffd24a' });
    vfx.popBurst(hx, hy, hz, e.type === 'elite' ? CONFIG.enemy.elite.color : CONFIG.enemy.normal.color);
    ctx.camera.addShake(CONFIG.shake.stackPop * (0.7 + poppedStacks * 0.12));
    ctx.requestHitStop(CONFIG.vfx.hitStop);
  } else {
    vfx.damageNumber(hx, hy, hz, dmg, { big: false, color: opts.isSkill ? '#ff9a52' : '#ffffff' });
    vfx.hitBurst(hx, e.bodyY, hz, opts.isSkill ? 0xff7a3c : 0xfff2b0);
  }

  if (e.hp <= 0) killEnemy(e, ctx);
}

// 화염 장판 등 지속 피해(스택과 무관, 폭발 없음)
export function applyTickDamage(e, amount, ctx) {
  if (!e.alive) return;
  e.hp -= amount;
  if (e.hp <= 0) killEnemy(e, ctx);
}

export function killEnemy(e, ctx) {
  if (!e.alive) return;
  e.alive = false;
  ctx.vfx.popBurst(e.pos.x, e.bodyY + 0.4, e.pos.z,
    e.type === 'elite' ? CONFIG.enemy.elite.color : CONFIG.enemy.normal.color);
  ctx.camera.addShake(CONFIG.shake.kill);
  ctx.onKill(e);
}
