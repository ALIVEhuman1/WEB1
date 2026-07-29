// hud.js — DOM 오버레이. Three.js 안에 그리지 않는다(프로토타입엔 이게 빠르다).
// 핵심: 총을 바꾸면 스킬 설명이 같이 바뀌는 걸 눈으로 봐야 조합 구조가 이해된다.
import { CONFIG } from '../config.js';
import { AMMO_DESC } from '../systems/ammo.js';

const $ = (id) => document.getElementById(id);

export class HUD {
  constructor() {
    this.el = {
      hpFill: $('hp-fill'), hpText: $('hp-text'),
      gun1: $('gun-1'), gun2: $('gun-2'),
      mag: $('mag'), reload: $('reload-text'),
      qCharges: $('q-charges'), qDesc: $('q-desc'),
      eCharges: $('e-charges'), eDesc: $('e-desc'),
      waveNum: $('wave-num'), waveSub: $('wave-sub'), killNum: $('kill-num'),
      dashFill: $('dash-fill'),
      banner: $('banner'),
    };
    this._magCells = 0;
    this._curGun = null;
    this._bannerTimer = 0;
    this._buildCharges(this.el.qCharges, CONFIG.ammo.incendiary.maxCharges);
    this._buildCharges(this.el.eCharges, CONFIG.ammo.ap.maxCharges);
  }

  _buildCharges(container, n) {
    container.innerHTML = '';
    for (let i = 0; i < n; i++) {
      const d = document.createElement('span');
      d.className = 'charge';
      container.appendChild(d);
    }
  }

  _buildMag(n) {
    this.el.mag.innerHTML = '';
    for (let i = 0; i < n; i++) {
      const d = document.createElement('span');
      d.className = 'cell';
      this.el.mag.appendChild(d);
    }
    this._magCells = n;
  }

  banner(text, small = '') {
    this.el.banner.innerHTML = text + (small ? `<span class="small">${small}</span>` : '');
    this.el.banner.classList.add('show');
    this._bannerTimer = 1.6;
  }

  update(dt, state) {
    // 체력
    const hpPct = Math.max(0, state.hp / state.maxHp) * 100;
    this.el.hpFill.style.width = hpPct + '%';
    this.el.hpText.textContent = `${Math.max(0, Math.ceil(state.hp))} / ${state.maxHp}`;

    // 총 강조
    this.el.gun1.classList.toggle('active', state.gun === 'shotgun');
    this.el.gun2.classList.toggle('active', state.gun === 'sniper');

    // 탄창 칸
    const magSize = CONFIG.guns[state.gun].magSize;
    if (this._curGun !== state.gun || this._magCells !== magSize) {
      this._buildMag(magSize);
      this._curGun = state.gun;
    }
    const cells = this.el.mag.children;
    for (let i = 0; i < cells.length; i++) {
      cells[i].classList.toggle('loaded', i < state.mag);
    }
    this.el.reload.textContent = state.reloading ? '재장전 중…' : '';

    // 스킬 충전 + 설명(현재 총 기준으로 바뀐다)
    this._paintCharges(this.el.qCharges, state.qCharges, state.qFrac);
    this._paintCharges(this.el.eCharges, state.eCharges, state.eFrac);
    this.el.qDesc.innerHTML = AMMO_DESC.incendiary[state.gun];
    this.el.eDesc.innerHTML = AMMO_DESC.ap[state.gun];

    // 웨이브 / 처치
    this.el.waveNum.textContent = state.wave;
    this.el.waveSub.textContent = `남은 적 ${state.remaining}`;
    this.el.killNum.textContent = state.kills;

    // 대시 쿨다운
    const dashPct = state.dashReady ? 100 : (1 - state.dashCdFrac) * 100;
    this.el.dashFill.style.width = dashPct + '%';
    this.el.dashFill.classList.toggle('ready', state.dashReady);
    this.el.dashFill.classList.toggle('cooling', !state.dashReady);

    // 배너 페이드
    if (this._bannerTimer > 0) {
      this._bannerTimer -= dt;
      if (this._bannerTimer <= 0) this.el.banner.classList.remove('show');
    }
  }

  _paintCharges(container, count, frac) {
    const cells = container.children;
    for (let i = 0; i < cells.length; i++) {
      const on = i < count;
      cells[i].classList.toggle('on', on);
      // 다음 충전 중인 칸을 부분적으로 밝힘
      if (!on && i === count) {
        cells[i].style.opacity = (0.3 + frac * 0.7).toFixed(2);
      } else {
        cells[i].style.opacity = on ? '1' : '0.3';
      }
    }
  }
}
