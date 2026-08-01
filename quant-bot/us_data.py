"""미국 일봉 수집기: yfinance -> db.us_daily_candles.

미국 전략(① 지수타이밍, ② 돌파)의 신호 계산에 쓰는 일봉을 받아 저장한다.
매매 서버(네트워크 가능한 사용자 환경)에서 미장 실행 직전 갱신하는 용도.

지수 필터·200일선·ATR·돈치안 계산에 넉넉하도록 기본 400일(약 1.5년) 이상 받는다.

사용법:
    python us_data.py                 # SPY + 전체 유니버스 갱신
    python us_data.py SPY QQQ         # 특정 심볼만
    python us_data.py --days 600      # 받을 기간 조정
"""
import argparse
import logging
import time

import db
from config import US_INDEX_SYMBOL
from us_universe import load_us_universe

logger = logging.getLogger(__name__)

DEFAULT_DAYS = 400


def _to_rows(symbol: str, df) -> list[dict]:
    """yfinance DataFrame -> upsert 행 목록. 결측/0 종가 행은 버린다."""
    import pandas as pd

    if df is None or df.empty:
        return []
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    rows = []
    for idx, r in df.iterrows():
        close = r.get("Close")
        if close is None or pd.isna(close) or float(close) <= 0:
            continue
        rows.append({
            "symbol": symbol,
            "date": idx.strftime("%Y-%m-%d"),
            "open": float(r["Open"]),
            "high": float(r["High"]),
            "low": float(r["Low"]),
            "close": float(close),
            "volume": int(r["Volume"]) if not pd.isna(r.get("Volume")) else 0,
        })
    return rows


def fetch_symbol(symbol: str, days: int) -> int:
    """한 심볼의 일봉을 받아 저장하고 저장 행수를 반환한다."""
    import yfinance as yf

    period = f"{max(days, 30)}d"
    df = yf.download(symbol, period=period, auto_adjust=True, progress=False)
    rows = _to_rows(symbol, df)
    return db.upsert_us_daily_candles(rows)


def update_us_daily(symbols: list[str], days: int = DEFAULT_DAYS) -> dict:
    """여러 심볼 갱신. 반환: {"ok": 성공수, "failed": [심볼...], "rows": 총행수}."""
    db.init_db()
    ok, failed, total = 0, [], 0
    for i, sym in enumerate(symbols, 1):
        try:
            n = fetch_symbol(sym, days)
            if n > 0:
                ok += 1
                total += n
            else:
                failed.append(sym)
        except Exception as exc:
            logger.warning("미국 일봉 수집 실패 %s: %s", sym, exc)
            failed.append(sym)
        time.sleep(0.3)
        if i % 20 == 0:
            logger.info("미국 일봉 수집 %d/%d", i, len(symbols))
    logger.info("미국 일봉 갱신 완료: 성공 %d/%d, 총 %d행%s",
                ok, len(symbols), total, f", 실패 {failed}" if failed else "")
    return {"ok": ok, "failed": failed, "rows": total}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="미국 일봉 수집 (yfinance -> DB)")
    parser.add_argument("symbols", nargs="*", help="심볼 목록 (미지정 시 SPY+유니버스 전체)")
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS)
    args = parser.parse_args()

    syms = args.symbols or ([US_INDEX_SYMBOL] + load_us_universe())
    # 중복 제거(순서 유지)
    seen, uniq = set(), []
    for s in syms:
        s = s.upper()
        if s not in seen:
            seen.add(s)
            uniq.append(s)
    print(f"미국 일봉 수집: {len(uniq)}심볼, 최근 {args.days}일")
    result = update_us_daily(uniq, args.days)
    print(f"완료: 성공 {result['ok']}/{len(uniq)}, {result['rows']}행"
          + (f", 실패 {result['failed']}" if result["failed"] else ""))
