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
LOG_DIR = BASE_DIR / "logs"


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
