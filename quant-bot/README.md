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
| `kis_auth.py` | OAuth 접근토큰 발급 및 파일 캐싱 |
| `collector.py` | 주식당일분봉조회 API 호출 및 파싱 (페이지네이션으로 당일 전체 수집) |
| `rate_limiter.py` | 종목 수 기반 배치 크기/딜레이 계산 |
| `retry.py` | 실패 시 최대 3회 지수 백오프 재시도 데코레이터 |
| `db.py` | SQLite 스키마, UPSERT, pandas 조회 함수 |
| `watchlist.json` | 관심종목 코드 목록 |
| `main.py` | 수집 로직 본체 (watchlist → 수집 → 저장) |
| `run_daily.py` | cron용 실행 트리거 (로깅 설정 후 `main.collect_and_store()` 호출) |

## 주의사항

- 이 저장소는 모의투자(vps)를 기본값으로 사용합니다. 실전투자 전환 시 `.env`의 `KIS_TRADING_MODE=prod`로 변경하고,
  실전투자용 앱키/시크릿을 사용해야 합니다.
- 토큰 캐시(`.kis_token_cache.json`)와 DB 파일(`candles.db`)은 git에 커밋되지 않습니다.
