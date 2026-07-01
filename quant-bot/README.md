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
| `config.py` | `.env`/Secret Manager 로드, 모의/실전 base_url 분리 |
| `kis_auth.py` | OAuth 접근토큰 발급 및 파일 캐싱 (권한 600) |
| `collector.py` | 주식당일분봉조회 API 호출 및 파싱 (페이지네이션으로 당일 전체 수집) |
| `rate_limiter.py` | 종목 수 기반 배치 크기/딜레이 계산 |
| `retry.py` | 실패 시 최대 3회 지수 백오프 재시도 데코레이터 |
| `db.py` | SQLite 스키마, UPSERT, pandas 조회 함수 |
| `watchlist.json` | 관심종목 코드 목록 |
| `main.py` | 수집 로직 본체 (watchlist → 수집 → 저장) |
| `run_daily.py` | 실행 트리거 (락 → 수집 → 실패 알림), cron/Cloud Run Job 진입점 |
| `logging_utils.py` | 로그 타임스탬프를 KST로 고정 |
| `lock.py` | 중복 실행 방지 파일 락 |
| `alerts.py` | 수집 실패 시 Slack 웹훅 알림 (선택) |
| `gcs_sync.py` | GCS에 DB 백업/복원 (Cloud Run Job용, 선택) |
| `Dockerfile` | Cloud Run Job 배포용 컨테이너 이미지 |

## 주의사항

- 이 저장소는 모의투자(vps)를 기본값으로 사용합니다. 실전투자 전환 시 `.env`의 `KIS_TRADING_MODE=prod`로 변경하고,
  실전투자용 앱키/시크릿을 사용해야 합니다.
- 토큰 캐시(`.kis_token_cache.json`)와 DB 파일(`candles.db`)은 git에 커밋되지 않습니다.

## 7. GCP(Google Cloud)에 배포하기

이 봇은 **Cloud Run Job + Cloud Scheduler** 조합으로 배포하는 걸 권장합니다 (서버 상시 운영 불필요,
장마감 후 정해진 시간에만 컨테이너가 떠서 수집하고 종료). Cloud Run Job은 실행마다 컨테이너가
새로 뜨기 때문에, 로컬 디스크에만 DB를 두면 다음 실행 때 데이터가 사라집니다. 이를 위해
`gcs_sync.py`가 실행 시작 시 GCS에서 DB를 내려받고 종료 시 다시 업로드합니다.

### 7-1. 비밀값을 Secret Manager에 등록

```bash
echo -n "발급받은_APP_KEY"    | gcloud secrets create kis-app-key    --data-file=-
echo -n "발급받은_APP_SECRET" | gcloud secrets create kis-app-secret --data-file=-
echo -n "본인_계좌번호"        | gcloud secrets create kis-account-no --data-file=-
```

### 7-2. DB 영속성용 GCS 버킷 생성

```bash
gcloud storage buckets create gs://YOUR_BUCKET_NAME --location=asia-northeast3
```

### 7-3. 서비스 계정 권한

Cloud Run Job이 사용할 서비스 계정에 아래 권한을 부여합니다.

```bash
gcloud secrets add-iam-policy-binding kis-app-key \
  --member="serviceAccount:YOUR_SA@YOUR_PROJECT.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
# kis-app-secret, kis-account-no도 동일하게 반복

gcloud storage buckets add-iam-policy-binding gs://YOUR_BUCKET_NAME \
  --member="serviceAccount:YOUR_SA@YOUR_PROJECT.iam.gserviceaccount.com" \
  --role="roles/storage.objectAdmin"
```

### 7-4. 이미지 빌드 및 Cloud Run Job 배포

```bash
gcloud builds submit --tag asia-northeast3-docker.pkg.dev/YOUR_PROJECT/quant-bot/collector

gcloud run jobs create candle-collector \
  --image asia-northeast3-docker.pkg.dev/YOUR_PROJECT/quant-bot/collector \
  --region asia-northeast3 \
  --service-account YOUR_SA@YOUR_PROJECT.iam.gserviceaccount.com \
  --set-env-vars USE_GCP_SECRET_MANAGER=true,GCP_PROJECT_ID=YOUR_PROJECT,GCS_BUCKET_NAME=YOUR_BUCKET_NAME \
  --set-env-vars KIS_TRADING_MODE=vps \
  --max-retries=1
```

`SLACK_WEBHOOK_URL`을 함께 `--set-env-vars`로 넘기면 수집 실패 시 Slack 알림을 받을 수 있습니다.

### 7-5. Cloud Scheduler로 매일 장마감 후 실행 (KST)

```bash
gcloud scheduler jobs create http candle-collector-trigger \
  --location asia-northeast3 \
  --schedule "40 15 * * 1-5" \
  --time-zone "Asia/Seoul" \
  --uri "https://asia-northeast3-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/YOUR_PROJECT/jobs/candle-collector:run" \
  --http-method POST \
  --oauth-service-account-email YOUR_SA@YOUR_PROJECT.iam.gserviceaccount.com
```

### 클라우드 배포 시 반영된 보안/견고성 조치

- **비밀값**: `.env` 대신 Secret Manager에서 앱키/시크릿/계좌번호를 읽음 (`USE_GCP_SECRET_MANAGER=true`).
- **DB 영속성**: 실행마다 컨테이너가 초기화돼도 GCS에 DB를 백업/복원해 데이터 유지.
- **타임존**: 컨테이너 시간대가 UTC여도 로그 타임스탬프는 항상 KST로 기록.
- **중복 실행 방지**: 이전 실행이 끝나기 전에 재트리거되면 파일 락으로 이번 실행을 건너뜀.
- **실패 알림**: `SLACK_WEBHOOK_URL` 설정 시 실패 종목이 있으면 Slack으로 알림.
- **토큰 캐시 파일 권한**: `.kis_token_cache.json`을 `chmod 600`으로 생성.
