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
- 실패 종목은 자동 재시도합니다 (`--retry-rounds 10 --retry-wait 1800` = 30분 간격 10회).

**KIS 모의투자 서버가 과거 일봉 조회에 계속 500을 뱉는 경우** 네이버 금융 기반의
대안 수집기를 사용하세요 (같은 테이블에 저장되므로 백테스트는 동일하게 동작):

```bash
python collect_history_fdr.py --years 5
```

## 8. 저장된 데이터 조회 (백테스트용)

```python
from db import get_candles_df, get_daily_candles_df

# 분봉 (매일 자동 수집분)
df_min = get_candles_df("005930", start_date="20260101", end_date="20260601")

# 일봉 (collect_history.py로 수집한 과거 데이터)
df_daily = get_daily_candles_df("005930", start_date="20230101")
print(df_daily.head())
```

## 8-1. 변동성 돌파 백테스트

`collect_history.py`로 일봉을 수집한 뒤 바로 실행할 수 있습니다.

```bash
python backtest.py                 # 전 종목, K=0.5
python backtest.py --k 0.7         # K값 변경
python backtest.py --sweep         # K 0.1~0.9 스캔 후 비교표 출력
python backtest.py --stock 005930  # 단일 종목
python backtest.py --start 20240101 --end 20251231   # 기간 지정

# 진단/개선 옵션 (조합 가능)
python backtest.py --sweep --no-cost        # 비용 제외, 순수 예측력 진단
python backtest.py --sweep --ma-filter      # 5일MA > 20일MA(상승 추세)인 날만 진입
python backtest.py --sweep --vol-filter     # 전일 거래량 > 20일 평균인 날만 진입
python backtest.py --sweep --exit-open      # 당일 종가 대신 다음날 시가 매도 (오버나잇)
python backtest.py --sweep --market-filter  # 코스피 지수가 전일 20일 이평 위일 때만 진입
```

`--market-filter`는 코스피 지수(KS11) 일봉이 필요하며, `collect_history_fdr.py`가 종목과 함께
자동으로 수집합니다.

- 전략: 돌파가격 = 시가 + K × (전일 고가-저가), 고가가 돌파가격에 닿으면 돌파가격 매수 → 당일 종가 매도
- 수수료(0.015%×2), 거래세(0.18%), 슬리피지(0.1%)를 반영한 수익률입니다.
- 모든 필터는 전일까지의 데이터만 사용해 미래 참조(look-ahead)가 없습니다.
- 종목별 거래수/승률/거래당 평균수익률/누적수익률/MDD와 전체 요약을 출력합니다.

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
| `collect_history.py` | 일봉 과거 N년치 일괄 수집 원샷 스크립트 (실패 자동 재시도) |
| `collect_history_fdr.py` | 네이버 금융(FinanceDataReader) 기반 일봉 수집 (KIS 서버 장애 시 대안) |
| `backtest.py` | 변동성 돌파 전략 백테스트 (K 스캔, 수수료/거래세/슬리피지 반영) |
| `strategy.py` | 매일 아침 진입 자격/돌파 폭 계산 (백테스트와 동일 규칙) |
| `kis_order.py` | KIS 주문 API 래퍼 (현재가/시장가 매수·매도, 실전주문 안전장치) |
| `trader.py` | 장중 돌파 감시 + 자동매매 루프 (청산 → 감시 → 매수) |
| `run_trader.py` | 자동매매 실행 트리거 (아침 cron 진입점) |
| `universe.py` | 코스피+코스닥 전 종목 리스트 (우선주/스팩 제외) |
| `collect_market.py` | 전 종목 일봉 수집 + 거래대금 상위 종목 자동 선발 (저녁 cron) |
| `backtest_dynamic.py` | 동적 유니버스(거래대금 상위 N) 방식 백테스트 |
| `backtest_multi.py` | 멀티 전략(돌파/평균회귀/추세) 백테스트 + 결합 포트폴리오 |
| `ai_report.py` | Claude가 당일 매매의 '실행 품질'을 채점해 Discord 전송 (전략 불변) |
| `ai_monthly.py` | Claude 월간 분석: 백테스트 기대치 대비 성과 + 개선 가설 제안 (자동 반영 없음) |
| `etf_timing.py` | 지수 타이밍 전략: 코스피>200일선이면 KODEX200 보유, 이탈 시 현금 (`ETF_BUDGET_KRW`로 활성화) |
| `lowvol_live.py` | 저변동성 우량주 월간 리밸런싱(방어형): 변동성 최저 N종목 보유 (`LOWVOL_BUDGET_KRW`로 활성화) |
| `report.py` | 전략별(돌파/지수/저변동성) 실현·미실현 손익 리포트. `python report.py [--discord]` |
| `us_universe.py` | US RSI(2) 백테스트용 S&P500 유동성 상위 ~100종목 (하드코딩) |
| `backtest_us_rsi2.py` | US RSI(2) 평균회귀 백테스트 (yfinance). `python backtest_us_rsi2.py --split` |

## 8-2. 자동매매 (3단계, 모의투자)

백테스트로 확정한 규칙(K=0.8, 거래량 필터, 시장 필터, 익일시가 청산)을 KIS 모의투자
계좌로 실행합니다.

**하루 흐름** (평일 08:55 cron 시작):
1. 일봉 데이터 최신화(FDR) → 진입 후보 계산 (시장 필터 미통과 시 신규 진입 없음)
2. 09:01 오버나잇 포지션 전량 시장가 매도 (익일 시가 청산)
3. 15:20까지 후보 종목 현재가 감시 → 돌파가격(시가+K×전일변동폭) 도달 시 시장가 매수
4. 매수/청산/요약을 Discord로 알림

**설정** (`.env`):
- `TRADE_K=0.8` 돌파 계수
- `MAX_POSITIONS=5` 동시 보유 최대 종목 수
- `TRADE_BUDGET_KRW=1000000` 종목당 투입 금액

**안전장치**: 실전투자(prod) 모드에서는 `ALLOW_PROD_TRADING=true`를 명시하지 않으면
모든 주문이 차단됩니다. 모의투자에서 충분히 검증한 후에만 전환하세요.

### 동적 watchlist (전 종목 스캔) — 현재 비활성 (백테스트 탈락)

고정 50종목 대신 매일 저녁 전 종목을 훑어 **전일 거래대금 상위 50종목**을 자동 선발하는
기능입니다. 단, 5년 백테스트 결과 이 선발 규칙은 거래당 -0.5%로 **검증에 실패**해
(과열 종목 추격 매수가 되는 구조) 기본 비활성(`USE_AUTO_WATCHLIST=false`)입니다.
전 종목 일봉 DB와 `backtest_dynamic.py`는 다른 선발 규칙을 실험할 때 재사용하세요.

```bash
# 최초 1회: 전 종목 5년치 일봉 백필 (약 1시간, nohup 권장)
nohup python collect_market.py --init --years 5 > market_init.log 2>&1 &

# 검증: 동적 유니버스 방식 백테스트 (고정 watchlist 결과와 비교)
python backtest_dynamic.py --sweep
python backtest_dynamic.py --sweep --start 20250101   # 구간별 확인

# 매일 저녁 자동 갱신 (cron, 17:30 KST = 08:30 UTC)
# 30 8 * * 1-5 cd /home/USERNAME/WEB1/quant-bot && /home/USERNAME/WEB1/quant-bot/venv/bin/python collect_market.py
```

- 선발 결과는 `watchlist_auto.json`에 저장되고, 트레이더/수집기는 이 파일이 있으면 자동으로
  우선 사용합니다 (없으면 고정 `watchlist.json`으로 폴백).
- 고정 목록으로 되돌리려면 `.env`에 `USE_AUTO_WATCHLIST=false`를 넣거나 `watchlist_auto.json`을 삭제하세요.
- `backtest_dynamic.py`는 일봉 한계로 동시보유 종목수 제한을 근사(당일 돌파 종목 균등 배분)합니다.

```cron
# 평일 08:55 KST 자동매매 시작
55 8 * * 1-5 cd /home/USERNAME/WEB1/quant-bot && /home/USERNAME/WEB1/quant-bot/venv/bin/python run_trader.py
```

로그는 `logs/trader.log`, 체결 내역은 DB의 `positions` 테이블에 기록됩니다.

### AI 채점/분석 (선택, ANTHROPIC_API_KEY 필요)

Claude API로 두 가지 자동 리뷰를 돌릴 수 있습니다. **둘 다 매매 전략을 자동으로
바꾸지 않습니다** — 일일 리포트는 실행 품질(슬리피지/청산 타이밍/에러)만 채점하고,
월간 분석의 개선 제안은 반드시 백테스트 검증과 운용자 승인을 거쳐 수동 반영합니다.

```bash
python report.py       # 전략별 실현·미실현 손익 현황 (터미널)
python report.py --discord   # 위 내용을 Discord로도 전송
python ai_report.py    # 당일 실행 품질 채점 -> Discord
python ai_monthly.py   # 이번 달 분석 + 백테스트할 가설 제안 -> Discord
python ai_monthly.py --month 202607   # 특정 월 분석
```

```cron
# 평일 16:10 KST 일일 채점 = 07:10 UTC
10 7 * * 1-5 cd /home/USERNAME/WEB1/quant-bot && /home/USERNAME/WEB1/quant-bot/venv/bin/python ai_report.py
# 매월 1일 09:00 KST 월간 분석 = 00:00 UTC
0 0 1 * * cd /home/USERNAME/WEB1/quant-bot && /home/USERNAME/WEB1/quant-bot/venv/bin/python ai_monthly.py
# (선택) 매주 토 08:00 KST 주간 성과 리포트 = 금 23:00 UTC
0 23 * * 5 cd /home/USERNAME/WEB1/quant-bot && /home/USERNAME/WEB1/quant-bot/venv/bin/python report.py --discord
```

## 8-3. 미국 자동매매 (① 지수타이밍 + ② 돌파)

미국주식 전략 두 가지. 백테스트로 검증했습니다(③ RSI2 평균회귀는 하락장에서 시장필터로도
방어가 안 돼 폐기). 국내 봇(`run_trader.py`)과 **완전 분리**되어 미장 스케줄로 따로 돕니다.

- **① 지수타이밍** (`us_index_timing.py`, 방패): SPY 종가>200일선이면 SPY 보유, 아니면 현금.
  2008 금융위기 -23%→+0.9%, 2022 -18.6%→-16.2%로 하락장 MDD를 반토막.
- **② 돌파+시장필터** (`us_breakout_live.py`, 창): SPY>200일선일 때만, 개별종목 100일 신고가
  돌파 매수 → ATR×3 샹들리에 트레일링 청산. 하락장은 필터로 관망, 상승장 추세추종.
  ⚠️ 유니버스가 현재 대형주라 백테스트 절대수익엔 생존편향 있음(국면 행동은 유효).

### 안전 단계 (실돈 나가기 전 반드시)

1. **드라이런** (기본): `US_INDEX_BUDGET_USD=0`, `US_BREAKOUT_BUDGET_USD=0`이면 실주문 없이
   매일 신호만 Discord로 통보합니다. 며칠 돌려 신호가 백테스트대로 나오는지 눈으로 확인.
2. **모의투자**: `KIS_TRADING_MODE=vps` 상태에서 예산을 소액(예: 지수 $600, 돌파 $3000)으로
   올려 체결을 확인. ⚠️ `kis_order_us.py`의 **TR ID·거래소코드는 KIS 최신 문서와 대조** 후
   1주 테스트로 응답을 검증하세요(해외 API는 계정/버전차가 있음).
3. **실전**: 검증 끝나면 `KIS_TRADING_MODE=prod` + `ALLOW_PROD_TRADING=true`.

```bash
# 미국 일봉 먼저 수집 (SPY + 유니버스)
python us_data.py

# 하루치 실행 (일봉 갱신 → 신호 → ①② 관리). 예산 0이면 드라이런.
python run_us_trader.py

# 백테스트 재확인
python backtest_us_index.py --split                 # ① 지수타이밍
python backtest_us_breakout.py --split              # ② 돌파 (--no-filter로 필터효과 비교)
```

### cron (미 장마감 16:00 ET 직후 실행 → 다음 세션 체결, 백테스트와 정합)

```bash
# ET 서버: 평일 16:15 ET
15 16 * * 1-5 cd /path/to/quant-bot && /path/to/venv/bin/python run_us_trader.py
# KST 서버: 대략 06:15 KST (겨울 EST=한국-14h, 여름 EDT=한국-13h, 화~토로 지정)
15 6  * * 2-6 cd /path/to/quant-bot && /path/to/venv/bin/python run_us_trader.py
```

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
