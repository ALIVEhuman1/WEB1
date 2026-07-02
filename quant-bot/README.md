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

## 6. 야간 완결성 체크 (선택, 상시 운영 시 권장)

장마감 직후 수집에서 API 순간 장애 등으로 일부 분봉이 빠질 수 있습니다. 정규장은
09:00~15:30(390분)이므로, 종목별 저장된 분봉 수가 이 기준의 90% 미만이면 "부족"으로 보고
해당 종목만 다시 수집합니다.

```bash
python run_completeness_check.py
```

- watchlist 전 종목이 다 부족하면 실제 문제보다 휴장일일 가능성이 높다고 보고 재수집을 건너뜁니다
  (KRX 공휴일 캘린더 연동은 아직 안 되어 있어 이 휴리스틱으로 오탐을 줄이는 정도입니다).
- `DISCORD_WEBHOOK_URL` 설정 시 체크 결과(정상/보충 완료/여전히 부족/휴장일 스킵)를 Discord로 보냅니다.
- 로그는 `logs/completeness.log`에 쌓입니다.

## 7. 일봉 과거 데이터 일괄 수집 (백테스트 준비)

분봉은 당일 데이터만 API로 받을 수 있어 매일 쌓아야 하지만, 일봉은 과거 몇 년치를
바로 받을 수 있습니다. 변동성 돌파 전략의 기본형은 일봉만으로 백테스트가 가능하므로,
이 스크립트로 과거 데이터를 한 번에 확보하고 바로 백테스트를 시작할 수 있습니다.

```bash
python collect_history.py             # 기본 3년치
python collect_history.py --years 5   # 5년치
```

- 수정주가 기준으로 수집해 액면분할/증자로 인한 가격 왜곡을 줄입니다.
- 매일 돌릴 필요 없이 백테스트 전 한 번, 이후 가끔 갱신용으로 실행하면 됩니다.
- `daily_candles` 테이블에 저장되며 분봉(`candles`)과 별개입니다.

## 8. 저장된 데이터 조회 (백테스트용)

```python
from db import get_candles_df, get_daily_candles_df

# 분봉 (매일 자동 수집분)
df_min = get_candles_df("005930", start_date="20260101", end_date="20260601")

# 일봉 (collect_history.py로 수집한 과거 데이터)
df_daily = get_daily_candles_df("005930", start_date="20230101")
print(df_daily.head())
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
| `run_daily.py` | 실행 트리거 (중복실행 방지 락 → 수집 → 현황 알림), cron 진입점 |
| `logging_utils.py` | 로그 타임스탬프를 KST로 고정 |
| `lock.py` | 중복 실행 방지 파일 락 |
| `alerts.py` | 수집/완결성 체크 현황을 Discord 웹훅으로 알림 (선택) |
| `completeness.py` | 당일 분봉 개수 완결성 체크 및 부족분 재수집 |
| `run_completeness_check.py` | 완결성 체크 실행 트리거 (야간 cron 진입점) |
| `daily_collector.py` | 국내주식기간별시세 API로 일봉 과거 데이터 수집 (수정주가) |
| `collect_history.py` | 일봉 과거 N년치 일괄 수집 원샷 스크립트 (백테스트 준비용) |

## 주의사항

- 이 저장소는 모의투자(vps)를 기본값으로 사용합니다. 실전투자 전환 시 `.env`의 `KIS_TRADING_MODE=prod`로 변경하고,
  실전투자용 앱키/시크릿을 사용해야 합니다.
- 토큰 캐시(`.kis_token_cache.json`)와 DB 파일(`candles.db`)은 git에 커밋되지 않습니다.

## 9. GCP VM에 배포하기

이 봇은 GCP e2-micro(무료 티어) VM에 상시 배포하는 걸 전제로 합니다. VM은 디스크가 영구적이라
DB/토큰 캐시가 재시작해도 그대로 유지되고, 비밀값도 Secret Manager 없이 VM 안의 `.env` 파일로
충분합니다 (별도 GCP API 연동 불필요).

### 9-1. 브라우저 SSH로 접속 후 기본 패키지 설치

```bash
sudo apt update
sudo apt install -y python3-venv python3-pip git
```

### 9-2. 스왑 파일 추가 (필수 권장)

e2-micro는 메모리가 1GB뿐이라 `pip install pandas` 같은 빌드 중 OOM으로 세션이 끊기는 경우가
흔합니다. 스왑 파일을 만들어두면 안전합니다.

```bash
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

### 9-3. 코드 배치 및 가상환경 설정

```bash
git clone <이 저장소 URL>
cd WEB1/quant-bot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 9-4. .env 설정

로컬과 동일하게 `.env.example`을 복사해서 채웁니다 (2번 항목 참고). VM에서는 이 파일에
직접 앱키/시크릿/계좌번호를 넣으면 됩니다.

```bash
cp .env.example .env
nano .env          # KIS_APP_KEY, KIS_APP_SECRET, KIS_ACCOUNT_NO 채우기
chmod 600 .env      # 소유자만 읽기/쓰기 가능하도록 권한 제한
```

`DISCORD_WEBHOOK_URL`을 채워두면 매 수집/체크 후 현황(성공·실패·저장 행수)을 Discord로 받을 수 있습니다 (선택). Discord
채널 설정 → 연동 → 웹훅 → 새 웹훅에서 URL을 발급받으면 됩니다.

### 9-5. cron으로 매일 장마감 후 자동 실행

```bash
crontab -e
```

```cron
# 매일(월~금) 15:40 KST에 실행 (VM 타임존이 UTC라면 09:40 UTC로 맞추거나 TZ=Asia/Seoul을 앞에 붙이세요)
40 15 * * 1-5 cd /home/USERNAME/WEB1/quant-bot && /home/USERNAME/WEB1/quant-bot/venv/bin/python run_daily.py
```

`run_daily.py`가 중복 실행 방지 락(`lock.py`)을 쥐고 수집한 뒤, 수집 현황 Discord 알림까지
보내므로 별도 스크립트 없이 이 한 줄이면 됩니다. 실행 로그는 `logs/collector.log`에 쌓입니다.

야간 완결성 체크(6번 항목)도 같이 등록해두면 좋습니다.

```cron
# 매일(월~금) 22:00 KST에 완결성 체크 + 부족분 재수집
0 22 * * 1-5 cd /home/USERNAME/WEB1/quant-bot && /home/USERNAME/WEB1/quant-bot/venv/bin/python run_completeness_check.py
```

### 9-6. 방화벽 관련 참고

인스턴스에 HTTP(80)/HTTPS(443) 인바운드가 열려 있는데, 이 분봉 수집기 자체는 KIS API로 나가는
아웃바운드 호출만 하므로 인바운드 포트가 필요 없습니다. 80/443은 이후 단계에서 FastAPI 대시보드를
붙일 때 쓰시면 됩니다.

### VM 배포 시 반영된 보안/견고성 조치

- **비밀값**: `.env` 파일에 보관하고 `chmod 600`으로 소유자만 읽기 가능하도록 제한.
- **토큰 캐시 파일 권한**: `.kis_token_cache.json`도 `chmod 600`으로 자동 생성.
- **타임존**: VM이 UTC로 설정돼 있어도 로그 타임스탬프는 항상 KST로 기록 (`logging_utils.py`).
- **중복 실행 방지**: cron이 이전 실행 종료 전에 재트리거해도 파일 락으로 이번 실행을 건너뜀 (`lock.py`).
- **현황 알림**: `DISCORD_WEBHOOK_URL` 설정 시 매 실행 후 성공/실패 현황을 Discord로 알림 (`alerts.py`).
- **야간 완결성 체크**: 장 마감 수집에서 빠진 분봉을 22:00에 한 번 더 검증/재수집 (`completeness.py`),
  VM이 24시간 떠 있는 걸 활용해 데이터 신뢰도를 높입니다.
- **메모리 제약**: e2-micro(1GB)는 무거운 백테스트/대량 데이터 처리에 부적합하므로, 그런 작업은
  로컬 PC에서 `db.get_candles_df()`로 DB를 읽어와 처리하고, VM은 실거래 봇 실행/대시보드 서빙 전용으로 씁니다.
