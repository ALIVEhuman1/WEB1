// arena.js — 바닥, 벽, 조명, 그림자. 탑다운 3D에서 거리감의 기반이다.
import * as THREE from 'three';
import { CONFIG } from '../config.js';

// 바닥에 미세한 그리드를 넣어 이동감을 살린다(단색 금지).
function makeFloorTexture() {
  const s = 512;
  const c = document.createElement('canvas');
  c.width = c.height = s;
  const ctx = c.getContext('2d');
  // 베이스 + 약한 노이즈
  ctx.fillStyle = '#15181e';
  ctx.fillRect(0, 0, s, s);
  const img = ctx.getImageData(0, 0, s, s);
  for (let i = 0; i < img.data.length; i += 4) {
    const n = (Math.random() - 0.5) * 14;
    img.data[i] += n; img.data[i + 1] += n; img.data[i + 2] += n;
  }
  ctx.putImageData(img, 0, 0);
  // 그리드 라인
  ctx.strokeStyle = 'rgba(120,140,170,0.14)';
  ctx.lineWidth = 2;
  const step = s / 8;
  for (let i = 0; i <= 8; i++) {
    ctx.beginPath(); ctx.moveTo(i * step, 0); ctx.lineTo(i * step, s); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(0, i * step); ctx.lineTo(s, i * step); ctx.stroke();
  }
  const tex = new THREE.CanvasTexture(c);
  tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
  tex.repeat.set(CONFIG.arena.size / 4, CONFIG.arena.size / 4);
  tex.anisotropy = 4;
  return tex;
}

export function createArena(scene) {
  const { size, wallHeight } = CONFIG.arena;

  // 바닥
  const floorGeo = new THREE.PlaneGeometry(size, size);
  const floorMat = new THREE.MeshStandardMaterial({
    map: makeFloorTexture(), roughness: 0.95, metalness: 0.0,
  });
  const floor = new THREE.Mesh(floorGeo, floorMat);
  floor.rotation.x = -Math.PI / 2;
  floor.receiveShadow = true;
  scene.add(floor);

  // 벽(낮은 테두리)
  const wallMat = new THREE.MeshStandardMaterial({ color: 0x2b3140, roughness: 0.8 });
  const wallGeo = new THREE.BoxGeometry(size + 1, wallHeight, 1);
  const walls = [
    [0, 0, -size / 2], [0, 0, size / 2],
  ];
  for (const [x, , z] of walls) {
    const w = new THREE.Mesh(wallGeo, wallMat);
    w.position.set(x, wallHeight / 2, z);
    w.castShadow = true; w.receiveShadow = true;
    scene.add(w);
  }
  const wallGeoV = new THREE.BoxGeometry(1, wallHeight, size + 1);
  for (const sx of [-size / 2, size / 2]) {
    const w = new THREE.Mesh(wallGeoV, wallMat);
    w.position.set(sx, wallHeight / 2, 0);
    w.castShadow = true; w.receiveShadow = true;
    scene.add(w);
  }

  // ---- 조명 ----
  const ambient = new THREE.AmbientLight(CONFIG.light.ambient, CONFIG.light.ambientIntensity);
  scene.add(ambient);

  const hemi = new THREE.HemisphereLight(
    CONFIG.light.hemiSky, CONFIG.light.hemiGround, CONFIG.light.hemiIntensity,
  );
  scene.add(hemi);

  // DirectionalLight + shadow map — 탑다운 3D에서 생략 불가.
  const dir = new THREE.DirectionalLight(CONFIG.light.dirColor, CONFIG.light.dirIntensity);
  dir.position.set(CONFIG.light.dirPosition.x, CONFIG.light.dirPosition.y, CONFIG.light.dirPosition.z);
  dir.castShadow = true;
  dir.shadow.mapSize.set(CONFIG.light.shadowMapSize, CONFIG.light.shadowMapSize);
  const sc = CONFIG.light.shadowCam;
  dir.shadow.camera.left = -sc; dir.shadow.camera.right = sc;
  dir.shadow.camera.top = sc; dir.shadow.camera.bottom = -sc;
  dir.shadow.camera.near = 1; dir.shadow.camera.far = 120;
  dir.shadow.bias = -0.0004;
  scene.add(dir);
  scene.add(dir.target);

  // y=0 평면(조준 레이캐스트 대상). floor mesh를 그대로 써도 되지만
  // 명시적 평면을 반환해 input이 arena 내부 구조에 의존하지 않게 한다.
  const groundPlane = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);

  return { floor, dirLight: dir, groundPlane };
}
