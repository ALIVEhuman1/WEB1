# 퀀트 트레이딩 봇 - 1단계: 분봉 데이터 수집기

한국투자증권(KIS) Open API로 국내주식 분봉 데이터를 수집해 로컬 SQLite DB에 저장하는 스크립트입니다.
변동성 돌파 전략 백테스트용 데이터 수집이 목적입니다.

## 1. 가상환경 설정

```bash
cd quant-bot
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## 2. .env 설정

```bash
cp .env.example .env
```

`.env` 파일을 열어 아래 값을 채워넣습니다. (KIS Developers 사이트에서 앱 등록 후 발급)

```
KIS_APP_KEY=발급받은_APP_KEY
KIS_APP_SECRET=발급받은_APP_SECRET
KIS_ACCOUNT_NO=본인_계좌번호
KIS_TRADING_MODE=vps   # vps=모의투자(기본값), prod=실전투자
```

`.env`는 `.gitignore`에 포함되어 git에 커밋되지 않습니다.

## 3. 관심종목 설정

`watchlist.json`에 수집할 종목코드를 배열로 넣습니다.

```json
["005930", "000660", "035420"]
```

## 4. 실행

```bash
python main.py
```

- `main.py`: watchlist를 순회하며 당일 분봉을 수집해 `candles.db`(SQLite)에 저장합니다.
- 종목 수에 따라 API 호출 배치 크기와 딜레이를 자동으로 조절해 초당 20건 제한을 지킵니다.
- API 호출/토큰 발급 실패 시 최대 3회, 지수 백오프로 재시도합니다.

## 5. 스케줄러(cron)로 자동 실행

수집 로직(`main.py`)과 실행 트리거(`run_daily.py`)가 분리되어 있어, 매일 장마감 후 cron으로
`run_daily.py`만 실행하면 됩니다. 실행 로그는 `logs/collector.log`에 쌓입니다.

```cron
# 매일(월~금) 15:40에 실행
40 15 * * 1-5 cd /path/to/quant-bot && /path/to/venv/bin/python run_daily.py
```

## 6. 저장된 데이터 조회 (백테스트용)

```python
from db import get_candles_df

df = get_candles_df("005930", start_date="20260101", end_date="20260601")
print(df.head())
```

## 파일 구조

| 파일 | 역할 |
|---|---|
| `config.py` | `.env` 로드, 모의/실전 base_url 분리 |
| `kis_auth.py` | OAuth 접근토큰 발급 및 파일 캐싱 (권한 600) |
| `collector.py` | 주식당일분봉조회 API 호출 및 파싱 (페이지네이션으로 당일 전체 수집) |
| `rate_limiter.py` | 종목 수 기반 배치 크기/딜레이 계산 |
| `retry.py` | 실패 시 최대 3회 지수 백오프 재시도 데코레이터 |
| `db.py` | SQLite 스키마, UPSERT, pandas 조회 함수 |
| `watchlist.json` | 관심종목 코드 목록 |
| `main.py` | 수집 로직 본체 (watchlist → 수집 → 저장) |
| `run_daily.py` | 실행 트리거 (중복실행 방지 락 → 수집 → 실패 알림), cron 진입점 |
| `logging_utils.py` | 로그 타임스탬프를 KST로 고정 |
| `lock.py` | 중복 실행 방지 파일 락 |
| `alerts.py` | 수집 실패 시 Slack 웹훅 알림 (선택) |

## 주의사항

- 이 저장소는 모의투자(vps)를 기본값으로 사용합니다. 실전투자 전환 시 `.env`의 `KIS_TRADING_MODE=prod`로 변경하고,
  실전투자용 앱키/시크릿을 사용해야 합니다.
- 토큰 캐시(`.kis_token_cache.json`)와 DB 파일(`candles.db`)은 git에 커밋되지 않습니다.

## 7. GCP VM에 배포하기

이 봇은 GCP e2-micro(무료 티어) VM에 상시 배포하는 걸 전제로 합니다. VM은 디스크가 영구적이라
DB/토큰 캐시가 재시작해도 그대로 유지되고, 비밀값도 Secret Manager 없이 VM 안의 `.env` 파일로
충분합니다 (별도 GCP API 연동 불필요).

### 7-1. 브라우저 SSH로 접속 후 기본 패키지 설치

```bash
sudo apt update
sudo apt install -y python3-venv python3-pip git
```

### 7-2. 스왑 파일 추가 (필수 권장)

e2-micro는 메모리가 1GB뿐이라 `pip install pandas` 같은 빌드 중 OOM으로 세션이 끊기는 경우가
흔합니다. 스왑 파일을 만들어두면 안전합니다.

```bash
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

### 7-3. 코드 배치 및 가상환경 설정

```bash
git clone <이 저장소 URL>
cd WEB1/quant-bot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 7-4. .env 설정

로컬과 동일하게 `.env.example`을 복사해서 채웁니다 (2번 항목 참고). VM에서는 이 파일에
직접 앱키/시크릿/계좌번호를 넣으면 됩니다.

```bash
cp .env.example .env
nano .env          # KIS_APP_KEY, KIS_APP_SECRET, KIS_ACCOUNT_NO 채우기
chmod 600 .env      # 소유자만 읽기/쓰기 가능하도록 권한 제한
```

`SLACK_WEBHOOK_URL`을 채워두면 수집 실패 시 Slack으로 알림을 받을 수 있습니다 (선택).

### 7-5. cron으로 매일 장마감 후 자동 실행

```bash
crontab -e
```

```cron
# 매일(월~금) 15:40 KST에 실행 (VM 타임존이 UTC라면 09:40 UTC로 맞추거나 TZ=Asia/Seoul을 앞에 붙이세요)
40 15 * * 1-5 cd /home/USERNAME/WEB1/quant-bot && /home/USERNAME/WEB1/quant-bot/venv/bin/python run_daily.py
```

`run_daily.py`가 중복 실행 방지 락(`lock.py`)을 쥐고 수집한 뒤, 실패 종목이 있으면 Slack 알림까지
보내므로 별도 스크립트 없이 이 한 줄이면 됩니다. 실행 로그는 `logs/collector.log`에 쌓입니다.

### 7-6. 방화벽 관련 참고

인스턴스에 HTTP(80)/HTTPS(443) 인바운드가 열려 있는데, 이 분봉 수집기 자체는 KIS API로 나가는
아웃바운드 호출만 하므로 인바운드 포트가 필요 없습니다. 80/443은 이후 단계에서 FastAPI 대시보드를
붙일 때 쓰시면 됩니다.

### VM 배포 시 반영된 보안/견고성 조치

- **비밀값**: `.env` 파일에 보관하고 `chmod 600`으로 소유자만 읽기 가능하도록 제한.
- **토큰 캐시 파일 권한**: `.kis_token_cache.json`도 `chmod 600`으로 자동 생성.
- **타임존**: VM이 UTC로 설정돼 있어도 로그 타임스탬프는 항상 KST로 기록 (`logging_utils.py`).
- **중복 실행 방지**: cron이 이전 실행 종료 전에 재트리거해도 파일 락으로 이번 실행을 건너뜀 (`lock.py`).
- **실패 알림**: `SLACK_WEBHOOK_URL` 설정 시 실패 종목이 있으면 Slack으로 알림 (`alerts.py`).
- **메모리 제약**: e2-micro(1GB)는 무거운 백테스트/대량 데이터 처리에 부적합하므로, 그런 작업은
  로컬 PC에서 `db.get_candles_df()`로 DB를 읽어와 처리하고, VM은 실거래 봇 실행/대시보드 서빙 전용으로 씁니다.
