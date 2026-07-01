"""환경설정: .env 로드 및 모의투자/실전투자 base_url 분리."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# true면 아래 값들을 .env 대신 GCP Secret Manager에서 읽는다 (클라우드 배포용).
USE_SECRET_MANAGER = os.getenv("USE_GCP_SECRET_MANAGER", "false").strip().lower() == "true"
GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID", "")


def _load_secret(env_name: str, secret_id: str) -> str:
    if USE_SECRET_MANAGER:
        from google.cloud import secretmanager

        client = secretmanager.SecretManagerServiceClient()
        name = f"projects/{GCP_PROJECT_ID}/secrets/{secret_id}/versions/latest"
        return client.access_secret_version(name=name).payload.data.decode("utf-8")
    return os.getenv(env_name, "")


APP_KEY = _load_secret("KIS_APP_KEY", "kis-app-key")
APP_SECRET = _load_secret("KIS_APP_SECRET", "kis-app-secret")
ACCOUNT_NO = _load_secret("KIS_ACCOUNT_NO", "kis-account-no")

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
