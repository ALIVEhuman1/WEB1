// input.js — 키보드/마우스 상태 + y=0 평면 레이캐스트 조준.
import * as THREE from 'three';

export class Input {
  constructor(domElement, camera, groundPlane) {
    this.dom = domElement;
    this.camera = camera;
    this.groundPlane = groundPlane;

    this.keys = new Set();        // 현재 눌린 키(소문자 코드 아님, key값 소문자)
    this.pressedThisFrame = new Set(); // 이번 프레임에 새로 눌린 키(엣지)
    this.mouseDown = false;
    this.ndc = new THREE.Vector2(0, 0);
    this.raycaster = new THREE.Raycaster();
    this.aimPoint = new THREE.Vector3(); // y=0 평면상의 조준 지점
    this._hit = new THREE.Vector3();

    this._onKeyDown = (e) => {
      const k = e.key.toLowerCase();
      if (!this.keys.has(k)) this.pressedThisFrame.add(k);
      this.keys.add(k);
      // 스페이스/방향키 스크롤 방지
      if ([' ', 'arrowup', 'arrowdown', 'arrowleft', 'arrowright'].includes(k)) e.preventDefault();
    };
    this._onKeyUp = (e) => { this.keys.delete(e.key.toLowerCase()); };
    this._onMouseMove = (e) => {
      const r = this.dom.getBoundingClientRect();
      this.ndc.x = ((e.clientX - r.left) / r.width) * 2 - 1;
      this.ndc.y = -((e.clientY - r.top) / r.height) * 2 + 1;
    };
    this._onMouseDown = (e) => { if (e.button === 0) this.mouseDown = true; };
    this._onMouseUp = (e) => { if (e.button === 0) this.mouseDown = false; };
    this._onContext = (e) => e.preventDefault();
    this._onBlur = () => { this.keys.clear(); this.mouseDown = false; };

    window.addEventListener('keydown', this._onKeyDown);
    window.addEventListener('keyup', this._onKeyUp);
    this.dom.addEventListener('mousemove', this._onMouseMove);
    this.dom.addEventListener('mousedown', this._onMouseDown);
    window.addEventListener('mouseup', this._onMouseUp);
    this.dom.addEventListener('contextmenu', this._onContext);
    window.addEventListener('blur', this._onBlur);
  }

  // 매 프레임 시작에서 조준 지점 갱신
  updateAim() {
    this.raycaster.setFromCamera(this.ndc, this.camera);
    const hit = this.raycaster.ray.intersectPlane(this.groundPlane, this._hit);
    if (hit) this.aimPoint.copy(hit);
    return this.aimPoint;
  }

  // WASD를 월드 방향 벡터로 (화면 위 = -Z)
  moveVector(out) {
    let x = 0, z = 0;
    if (this.keys.has('w')) z -= 1;
    if (this.keys.has('s')) z += 1;
    if (this.keys.has('a')) x -= 1;
    if (this.keys.has('d')) x += 1;
    out.set(x, 0, z);
    if (out.lengthSq() > 1) out.normalize();
    return out;
  }

  pressed(k) { return this.pressedThisFrame.has(k); }
  held(k) { return this.keys.has(k); }

  // 프레임 끝에서 호출 — 엣지 트리거 초기화
  endFrame() { this.pressedThisFrame.clear(); }

  dispose() {
    window.removeEventListener('keydown', this._onKeyDown);
    window.removeEventListener('keyup', this._onKeyUp);
    this.dom.removeEventListener('mousemove', this._onMouseMove);
    this.dom.removeEventListener('mousedown', this._onMouseDown);
    window.removeEventListener('mouseup', this._onMouseUp);
    this.dom.removeEventListener('contextmenu', this._onContext);
    window.removeEventListener('blur', this._onBlur);
  }
}
