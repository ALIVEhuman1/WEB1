// ============================================================================
// config.js — 모든 튜닝 값이 여기 한 곳에 모인다.
// 다른 파일에는 숫자 리터럴을 박지 않는다. 기획 반복 속도가 여기서 결정된다.
// 거리 단위는 전부 Three.js world unit, 시간은 별도 표기 없으면 초(sec).
// ============================================================================

export const CONFIG = {
  // ---- 아레나 / 스케일 ----
  arena: {
    size: 60,            // 60 x 60 평면
    wallHeight: 1.2,
    half: 30,            // size/2, 이동 경계 계산용 (플레이어 반경만큼 안쪽으로 clamp)
  },

  // ---- 카메라 (디아블로식 고정 각도 탑다운) ----
  camera: {
    fov: 45,
    offset: { x: 0, y: 26, z: 16 }, // 내려다보는 각도 약 58°
    followLerp: 0.12,               // 플레이어 추적 부드러움
    aimPull: 3,                     // 마우스 방향으로 카메라가 끌려가는 최대 거리
    aimPullLerp: 0.08,
    near: 0.1,
    far: 400,
  },

  // ---- 카메라 흔들림 (이벤트별 강도가 다르다) ----
  shake: {
    fire: 0.05,        // 발사 시
    kill: 0.10,        // 처치 시
    stackPop: 0.32,    // 취약 스택 폭발 시 (가장 강함)
    dashTrail: 0.04,
    hurt: 0.18,        // 피격 시
    decay: 7.5,        // 초당 감쇠율
    maxOffset: 0.9,    // 흔들림 최대 이동량 clamp
  },

  // ---- 조명 / 그림자 ----
  light: {
    ambient: 0x3a4152,
    ambientIntensity: 0.85,
    dirColor: 0xfff2df,
    dirIntensity: 1.35,
    dirPosition: { x: 14, y: 34, z: 10 },
    shadowMapSize: 2048,
    shadowCam: 42,     // 그림자 직교 카메라 반경
    hemiSky: 0x9fb8ff,
    hemiGround: 0x2a2118,
    hemiIntensity: 0.35,
  },

  // ---- 플레이어 ----
  player: {
    radius: 0.5,
    height: 1.8,
    moveSpeed: 9,          // units/sec
    maxHp: 100,
    color: 0x6fd0ff,       // 몸통/팔 색
    hurtInvuln: 0.5,       // 피격 후 무적 시간(접촉 도트 방지)
    contactKnockResist: 1,
    // 간단한 사람 형태 모델 색상
    parts: {
      body: 0x6fd0ff,
      legs: 0x35435c,
      head: 0xf0c9a4,
      gun: 0x262b33,
    },
  },

  // ---- 대시 ----
  dash: {
    duration: 0.17,        // 170ms
    speedMult: 3.4,
    cooldown: 1.0,         // 1000ms
    trailInterval: 0.02,   // 잔상 생성 간격
    trailLife: 0.28,
  },

  // ---- 총 = 기본공격 ----
  // 명중 시마다 취약 스택 +1
  guns: {
    shotgun: {
      key: 'shotgun',
      label: '산탄총',
      hotkey: '1',
      pellets: 8,
      spreadDeg: 17,       // ±17°
      damage: 7,           // 펠릿당
      range: 9,
      pierce: 0,           // 관통 없음
      fireInterval: 0.6,   // 600ms
      magSize: 8,
      reload: 1.25,        // 1250ms
      bulletSpeed: 55,
      muzzleFlash: 0.9,    // PointLight 세기 배수
      shakeMult: 1.4,      // 산탄총은 발사감이 세다
    },
    sniper: {
      key: 'sniper',
      label: '저격총',
      hotkey: '2',
      pellets: 1,
      spreadDeg: 0,
      damage: 22,
      range: 45,
      pierce: 2,           // 관통 2회
      fireInterval: 0.64,  // 640ms
      magSize: 5,
      reload: 1.5,         // 1500ms
      bulletSpeed: 120,
      muzzleFlash: 1.3,
      shakeMult: 1.1,
    },
  },

  // ---- 취약 스택 (핵심 시스템) ----
  vuln: {
    max: 5,
    dmgPerStack: 0.25,     // 스택당 스킬 피해 +25%
    dotColor: 0xff5a3c,    // 머리 위 점 색
  },

  // ---- 탄종 = 스킬 ----
  ammo: {
    incendiary: {          // 소이탄 (Q)
      key: 'incendiary',
      label: '소이탄',
      hotkey: 'Q',
      maxCharges: 3,
      rechargeTime: 3.0,   // 발당 3000ms
      burnDps: 18,         // 화상 DoT 초당 피해
      burnDuration: 2.2,   // 2.2초
      // 산탄총 → 전방 부채꼴 화염
      shotgun: {
        spreadDeg: 30,     // ±30°
        range: 5,
        patchCount: 4,     // 부채꼴 화염 장판 개수
        directDamage: 20,  // 부채꼴에 맞은 적 즉발 피해(스택 배율 적용 대상)
        bulletSpeed: 40,
      },
      // 저격총 → 직선 관통 발화탄
      sniper: {
        range: 45,
        pierce: Infinity,  // 무한 관통
        patchCount: 10,    // 궤적 따라 일렬 화염 장판
        directDamage: 40,
        lineWidth: 1.1,    // 라인 명중 폭(반지름)
        bulletSpeed: 110,
      },
    },
    ap: {                  // 철갑탄 (E)
      key: 'ap',
      label: '철갑탄',
      hotkey: 'E',
      maxCharges: 2,
      rechargeTime: 5.0,   // 발당 5000ms
      // 산탄총 → 슬러그 3발 소폭 확산 관통
      shotgun: {
        slugs: 3,
        spreadDeg: 8,
        damage: 46,        // 발당
        pierce: Infinity,
        knockback: 9,      // 강한 넉백
        bulletSpeed: 70,
      },
      // 저격총 → 초장거리 단발
      sniper: {
        damage: 150,
        range: 45,
        pierce: Infinity,
        knockback: 16,     // 강한 넉백
        bulletSpeed: 150,
      },
    },
  },

  // ---- 화염 장판 (지면에 그려서 스킬 형태를 드러낸다) ----
  firePatch: {
    life: 2.4,             // 장판 지속 시간
    dps: 14,               // 장판 위 적에게 초당 피해
    radius: 0.9,           // 장판 판정 반경
    color: 0xff6a2a,
  },

  // ---- 적 ----
  enemy: {
    normal: {
      radius: 0.5,
      speedMin: 5,
      speedMax: 7,
      contactDamage: 7,
      hpBase: 44,
      hpPerWave: 9,        // 44 + wave*9
      color: 0xd85c4a,
      contactCooldown: 0.6,
    },
    elite: {
      radius: 0.85,
      speed: 4.5,
      contactDamage: 13,
      hpBase: 150,
      hpPerWave: 9,        // 150 + wave*9
      color: 0xb23bd6,
      contactCooldown: 0.6,
      // 등장 확률 min(0.22, 0.04 + wave*0.02)
      chanceBase: 0.04,
      chancePerWave: 0.02,
      chanceMax: 0.22,
    },
    knockDecay: 9,         // 넉백 속도 감쇠(초당)
    separation: 0.6,       // 적끼리 겹침 방지 밀어내기 강도
    spawnMargin: 1.5,      // 아레나 가장자리에서 안쪽으로 스폰
  },

  // ---- 웨이브 ----
  waves: {
    countBase: 6,
    countPerWave: 3,       // 6 + wave*3
    spawnInterval: 0.18,   // 순차 스폰 간격
    nextWaveDelay: 1.6,    // 전멸 후 다음 웨이브까지
  },

  // ---- 총알 시각 ----
  bullet: {
    basicColor: 0xfff2b0,
    basicRadius: 0.09,
    tracerLen: 1.6,
    skillRadius: 0.16,
    apColor: 0xffd36b,
    incendiaryColor: 0xff7a3c,
    y: 1.0,                // 총알이 나는 높이
  },

  // ---- VFX ----
  vfx: {
    muzzleFlashTime: 0.04, // 총구 섬광 PointLight 켜짐 시간 40ms
    muzzleFlashColor: 0xffd98a,
    muzzleFlashRange: 8,
    hitParticles: 6,
    popParticles: 26,      // 스택 폭발 파티클
    particleLife: 0.5,
    damageNumberLife: 0.8,
    damageNumberRise: 1.6,
    hitStop: 0.045,        // 스택 폭발 시 히트스톱(초)
  },
};

// 파생 상수(자주 쓰는 라디안 변환 등)를 미리 계산해 둔다.
export const DEG = Math.PI / 180;
