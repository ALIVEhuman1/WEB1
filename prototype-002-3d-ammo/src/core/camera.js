// camera.js — 고정 각도 탑다운 추적 + 이벤트 기반 흔들림.
// 회전 없음. 항상 같은 각도를 유지한다.
import * as THREE from 'three';
import { CONFIG } from '../config.js';

export class CameraRig {
  constructor(aspect) {
    const c = CONFIG.camera;
    this.cam = new THREE.PerspectiveCamera(c.fov, aspect, c.near, c.far);
    this.offset = new THREE.Vector3(c.offset.x, c.offset.y, c.offset.z);

    this.focus = new THREE.Vector3();   // 현재 추적 지점(lerp됨)
    this.aimShift = new THREE.Vector3(); // 마우스 방향으로 끌린 양
    this.shake = 0;                      // 남은 흔들림 강도
    this._shakeVec = new THREE.Vector3();
  }

  // 이벤트가 흔들림을 "누적"이 아니라 "최댓값"으로 세팅 — 스택 폭발이 항상 우선.
  addShake(amount) {
    this.shake = Math.max(this.shake, amount);
  }

  update(dt, playerPos, aimPoint) {
    const c = CONFIG.camera;

    // 추적 지점 lerp
    this.focus.lerp(playerPos, c.followLerp);

    // 마우스 조준 방향으로 카메라를 살짝 끌어당김(최대 aimPull)
    const desired = this._shakeVec.copy(aimPoint).sub(playerPos);
    desired.y = 0;
    if (desired.lengthSq() > 1e-4) {
      desired.normalize().multiplyScalar(
        Math.min(c.aimPull, aimPoint.distanceTo(playerPos) * 0.25),
      );
    } else {
      desired.set(0, 0, 0);
    }
    this.aimShift.lerp(desired, c.aimPullLerp);

    // 최종 위치 = focus + offset + aimShift + shake
    const px = this.focus.x + this.offset.x + this.aimShift.x;
    const py = this.focus.y + this.offset.y;
    const pz = this.focus.z + this.offset.z + this.aimShift.z;

    // 흔들림 감쇠 & 적용
    let sx = 0, sy = 0, sz = 0;
    if (this.shake > 0.0001) {
      const s = Math.min(this.shake, CONFIG.shake.maxOffset);
      sx = (Math.random() * 2 - 1) * s;
      sy = (Math.random() * 2 - 1) * s * 0.5;
      sz = (Math.random() * 2 - 1) * s;
      this.shake -= CONFIG.shake.decay * this.shake * dt;
      if (this.shake < 0.0005) this.shake = 0;
    }

    this.cam.position.set(px + sx, py + sy, pz + sz);
    this.cam.lookAt(
      this.focus.x + this.aimShift.x + sx,
      0,
      this.focus.z + this.aimShift.z + sz,
    );
  }

  onResize(aspect) {
    this.cam.aspect = aspect;
    this.cam.updateProjectionMatrix();
  }
}
