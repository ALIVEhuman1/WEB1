// waves.js — 웨이브 스폰. 6 + wave*3 마리를 가장자리에서 순차 스폰.
// 전멸하면 nextWaveDelay 후 다음 웨이브.
import * as THREE from 'three';
import { CONFIG } from '../config.js';

const _p = new THREE.Vector3();

function edgeSpawnPoint() {
  const half = CONFIG.arena.half - CONFIG.enemy.spawnMargin;
  const along = (Math.random() * 2 - 1) * half;
  switch (Math.floor(Math.random() * 4)) {
    case 0: _p.set(along, 0, -half); break; // 위
    case 1: _p.set(along, 0, half); break;  // 아래
    case 2: _p.set(-half, 0, along); break; // 좌
    default: _p.set(half, 0, along); break; // 우
  }
  return _p;
}

export class WaveController {
  constructor(world) {
    this.world = world; // { enemies, spawnEnemy(type, wave, pos), onWaveStart(n) }
    this.wave = 0;
    this.state = 'intermission';
    this.timer = CONFIG.waves.nextWaveDelay;
    this.toSpawn = 0;
    this.spawnTimer = 0;
  }

  eliteChance() {
    const e = CONFIG.enemy.elite;
    return Math.min(e.chanceMax, e.chanceBase + this.wave * e.chancePerWave);
  }

  startWave() {
    this.wave += 1;
    this.toSpawn = CONFIG.waves.countBase + this.wave * CONFIG.waves.countPerWave;
    this.spawnTimer = 0;
    this.state = 'spawning';
    this.world.onWaveStart(this.wave);
  }

  update(dt) {
    if (this.state === 'intermission') {
      this.timer -= dt;
      if (this.timer <= 0) this.startWave();
      return;
    }

    if (this.state === 'spawning') {
      this.spawnTimer -= dt;
      while (this.toSpawn > 0 && this.spawnTimer <= 0) {
        const type = Math.random() < this.eliteChance() ? 'elite' : 'normal';
        this.world.spawnEnemy(type, this.wave, edgeSpawnPoint());
        this.toSpawn -= 1;
        this.spawnTimer += CONFIG.waves.spawnInterval;
      }
      if (this.toSpawn <= 0) this.state = 'active';
      return;
    }

    // active: 전멸 감지
    if (this.state === 'active' && this.world.enemies.length === 0) {
      this.state = 'intermission';
      this.timer = CONFIG.waves.nextWaveDelay;
    }
  }

  get remaining() {
    return this.toSpawn + this.world.enemies.length;
  }
}
