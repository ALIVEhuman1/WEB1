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
