"""FinanceDataReader(네이버 금융) 기반 일봉 과거 데이터 일괄 수집.

KIS 모의투자 서버가 과거 일봉 조회에 500을 계속 뱉는 경우의 대안 경로.
네이버 금융 차트 데이터를 받아오므로 KIS API 키/서버 상태와 무관하며,
수정주가 기준이라 KIS 수집분과 동일하게 백테스트에 쓸 수 있다.
저장 테이블(daily_candles)도 동일해서 backtest.py를 그대로 사용하면 된다.

사용법:
    python collect_history_fdr.py            # 기본 5년치
    python collect_history_fdr.py --years 3
"""
import argparse
import logging
import time
from datetime import datetime, timedelta

import db
from logging_utils import configure_logging
from main import load_watchlist
from retry import retry_with_backoff

logger = logging.getLogger(__name__)

PER_STOCK_DELAY = 0.5  # 네이버 쪽 과도한 요청 방지용 딜레이 (초)
INDEX_CODE = "KS11"    # 코스피 지수 (시장 상태 필터용, 종목과 함께 daily_candles에 저장)

# FDR의 지수(KS11)가 비현실적 값(스케일 3배·일간 8%+ 급변 다수)을 반환하는 문제가 있어
# 지수만 yfinance(Yahoo)의 실제 코스피 컴포지트 티커로 받는다. 개별종목 FDR은 정상이라 유지.
YF_INDEX = {"KS11": "^KS11"}


def fetch_index_history_yf(code: str, years: int) -> list[dict]:
    """지수(코스피 등)를 yfinance로 받는다. FDR KS11 오염 우회. 저장 형식은 종목과 동일."""
    import pandas as pd
    import yfinance as yf

    start = (datetime.now() - timedelta(days=years * 365)).strftime("%Y-%m-%d")
    df = yf.download(YF_INDEX[code], start=start, auto_adjust=False, progress=False)
    if df is None or df.empty:
        return []
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    rows = []
    for idx, r in df.iterrows():
        o, c = r["Open"], r["Close"]
        if pd.isna(o) or pd.isna(c) or float(o) <= 0:
            continue
        rows.append({
            "stock_code": code,
            "date": idx.strftime("%Y%m%d"),
            "open": int(r["Open"]),
            "high": int(r["High"]),
            "low": int(r["Low"]),
            "close": int(r["Close"]),
            "volume": int(r["Volume"]) if pd.notna(r.get("Volume")) else 0,
        })
    return rows


@retry_with_backoff(max_retries=3, base_delay=2.0)
def fetch_daily_history_fdr(stock_code: str, years: int) -> list[dict]:
    if stock_code in YF_INDEX:          # 지수는 yfinance 경로로 (FDR 오염 회피)
        return fetch_index_history_yf(stock_code, years)

    import FinanceDataReader as fdr

    start = (datetime.now() - timedelta(days=years * 365)).strftime("%Y-%m-%d")
    df = fdr.DataReader(stock_code, start)

    import pandas as pd

    rows = []
    for idx, r in df.iterrows():
        if pd.isna(r["Open"]) or pd.isna(r["Close"]):
            continue
        open_, high, low, close = int(r["Open"]), int(r["High"]), int(r["Low"]), int(r["Close"])
        if open_ <= 0 or high <= 0:
            continue  # 거래정지일 등 가격이 비어있는 날은 제외
        volume = int(r["Volume"]) if "Volume" in df.columns and pd.notna(r["Volume"]) else 0
        rows.append({
            "stock_code": stock_code,
            "date": idx.strftime("%Y%m%d"),
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        })
    return rows


def collect_history_fdr(years: int = 5, watchlist: list[str] | None = None) -> dict:
    watchlist = watchlist if watchlist is not None else load_watchlist()
    db.init_db()

    # 코스피 지수도 함께 수집 (backtest.py --market-filter에서 사용)
    targets = watchlist + [INDEX_CODE]

    logger.info("[FDR] 일봉 %d년치 수집 시작: 종목 %d개 + 지수(%s)", years, len(watchlist), INDEX_CODE)
    summary = {"total_stocks": len(targets), "success": 0, "failed": [], "rows_saved": 0}

    for stock_code in targets:
        try:
            rows = fetch_daily_history_fdr(stock_code, years)
            saved = db.upsert_daily_candles(rows)
            summary["success"] += 1
            summary["rows_saved"] += saved
            logger.info("%s: 일봉 %d개 저장 (%s ~ %s)",
                        stock_code, saved,
                        rows[0]["date"] if rows else "-",
                        rows[-1]["date"] if rows else "-")
        except Exception:
            logger.exception("%s 일봉 수집 실패", stock_code)
            summary["failed"].append(stock_code)
        time.sleep(PER_STOCK_DELAY)

    logger.info(
        "[FDR] 일봉 수집 완료: 성공 %d/%d, 저장 %d행, 실패 %s",
        summary["success"], summary["total_stocks"], summary["rows_saved"], summary["failed"],
    )
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FinanceDataReader 기반 일봉 과거 데이터 수집")
    parser.add_argument("--years", type=int, default=5, help="수집할 과거 기간(년), 기본 5년")
    args = parser.parse_args()

    configure_logging()
    collect_history_fdr(years=args.years)
