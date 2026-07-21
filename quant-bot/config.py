"""환경설정: .env 로드 및 모의투자/실전투자 base_url 분리."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

APP_KEY = os.getenv("KIS_APP_KEY", "")
APP_SECRET = os.getenv("KIS_APP_SECRET", "")
ACCOUNT_NO = os.getenv("KIS_ACCOUNT_NO", "")

# vps = 모의투자, prod = 실전투자
TRADING_MODE = os.getenv("KIS_TRADING_MODE", "vps").strip().lower()

BASE_URLS = {
    "vps": "https://openapivts.koreainvestment.com:29443",
    "prod": "https://openapi.koreainvestment.com:9443",
}


def get_base_url() -> str:
    if TRADING_MODE not in BASE_URLS:
        raise ValueError(f"알 수 없는 KIS_TRADING_MODE: {TRADING_MODE} (vps 또는 prod만 허용)")
    return BASE_URLS[TRADING_MODE]


TOKEN_CACHE_PATH = BASE_DIR / ".kis_token_cache.json"
DB_PATH = BASE_DIR / "candles.db"
WATCHLIST_PATH = BASE_DIR / "watchlist.json"
WATCHLIST_AUTO_PATH = BASE_DIR / "watchlist_auto.json"
LOG_DIR = BASE_DIR / "logs"

# true면 collect_market.py가 생성한 watchlist_auto.json(전일 거래대금 상위 종목)을 우선 사용.
# 백테스트 결과 '거래대금 상위 추격' 선발은 이 전략과 궁합이 나빠(전 구간 거래당 -0.5%)
# 기본값을 false로 둔다. 다른 선발 규칙을 검증한 뒤에만 명시적으로 켤 것.
USE_AUTO_WATCHLIST = os.getenv("USE_AUTO_WATCHLIST", "false").strip().lower() == "true"


def _split_account() -> tuple[str, str]:
    """계좌번호를 KIS API 형식(종합계좌 8자리, 상품코드 2자리)으로 분리한다."""
    raw = ACCOUNT_NO.replace("-", "").strip()
    if len(raw) < 10:
        raise ValueError("KIS_ACCOUNT_NO 형식이 올바르지 않습니다 (예: 12345678-01)")
    return raw[:8], raw[8:10]


# ---- 자동매매 파라미터 (백테스트로 확정한 값이 기본) ----
TRADE_K = float(os.getenv("TRADE_K", "0.8"))                       # 돌파 계수
MAX_POSITIONS = int(os.getenv("MAX_POSITIONS", "5"))               # 동시 보유 종목 수
TRADE_BUDGET_KRW = int(os.getenv("TRADE_BUDGET_KRW", "1000000"))   # 종목당 투입 금액(원)

# 지수 타이밍 전략(KODEX 200)에 배분할 금액. 0이면 비활성.
ETF_BUDGET_KRW = int(os.getenv("ETF_BUDGET_KRW", "0"))

# 저변동성 우량주 전략(월간 리밸런싱)에 배분할 총액. 0이면 비활성.
# 종목당 예산 = LOWVOL_BUDGET_KRW / LOWVOL_TOP_N (예: 500만 / 10종목 = 종목당 50만)
LOWVOL_BUDGET_KRW = int(os.getenv("LOWVOL_BUDGET_KRW", "0"))
LOWVOL_TOP_N = int(os.getenv("LOWVOL_TOP_N", "10"))     # 보유 종목 수 (변동성 최저)

# ---- 안전장치 (kill-switch, 백테스트 불필요한 리스크 관리) ----
# 코스피(KODEX200 대용) 당일 등락률이 이 값(%) 이하로 급락하면 그날 신규 진입 중단.
CRASH_HALT_PCT = float(os.getenv("CRASH_HALT_PCT", "-4.0"))
# 실현 누적손익이 이 금액(원) 이상 손실이면 신규 진입 중단 + 알림. 0이면 비활성.
LOSS_LIMIT_KRW = int(os.getenv("LOSS_LIMIT_KRW", "0"))
