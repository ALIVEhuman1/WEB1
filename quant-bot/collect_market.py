"""전 종목 일봉 수집 + 다음날 감시 대상(watchlist) 자동 선발.

매일 장 마감 후(17:30 KST 권장) 실행:
1. 코스피+코스닥 전 종목의 일봉을 수집/갱신 (네이버 금융 기반)
2. 최신 거래일의 거래대금(종가*거래량) 상위 TOP_N 종목을 선발
3. watchlist_auto.json에 기록 -> 다음날 아침 트레이더가 이 목록을 감시

사용법:
    python collect_market.py --init --years 5   # 최초 1회: 전 종목 5년치 백필 (약 1시간)
    python collect_market.py                    # 매일: 최근 1년치 갱신 + 선발 (cron용)
"""
import argparse
import json
import logging
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import config
import db
from alerts import _post as discord_post
from collect_history_fdr import fetch_daily_history_fdr
from logging_utils import configure_logging
from universe import get_universe

logger = logging.getLogger(__name__)

KST = ZoneInfo("Asia/Seoul")
INDEX_CODE = "KS11"
PER_STOCK_DELAY = 0.3   # 전 종목 대상이라 종목당 딜레이를 짧게
TOP_N = 50
MIN_PRICE = 1000        # 저가주(동전주) 제외 기준


def collect_market(years: int = 1) -> dict:
    """유니버스 전 종목 + 코스피 지수의 일봉을 수집한다."""
    db.init_db()
    codes = get_universe() + [INDEX_CODE]

    logger.info("[전종목] 일봉 %d년치 수집 시작: %d종목", years, len(codes))
    summary = {"total": len(codes), "success": 0, "failed": [], "rows_saved": 0}

    for i, code in enumerate(codes, 1):
        try:
            rows = fetch_daily_history_fdr(code, years)
            summary["rows_saved"] += db.upsert_daily_candles(rows)
            summary["success"] += 1
        except Exception:
            logger.exception("%s 수집 실패", code)
            summary["failed"].append(code)
        if i % 200 == 0:
            logger.info("진행: %d/%d (실패 %d)", i, len(codes), len(summary["failed"]))
        time.sleep(PER_STOCK_DELAY)

    logger.info("[전종목] 수집 완료: 성공 %d/%d, 저장 %d행, 실패 %d종목",
                summary["success"], summary["total"], summary["rows_saved"], len(summary["failed"]))
    return summary


def select_watchlist(top_n: int = TOP_N) -> list[str]:
    """최신 거래일 기준 거래대금 상위 top_n 종목을 선발한다."""
    with db.get_connection() as conn:
        row = conn.execute(
            "SELECT MAX(date) FROM daily_candles WHERE stock_code != ?", (INDEX_CODE,)
        ).fetchone()
        latest_date = row[0]
        if not latest_date:
            raise RuntimeError("일봉 데이터가 없습니다. collect_market.py --init을 먼저 실행하세요.")

        rows = conn.execute(
            """
            SELECT stock_code, close, volume, CAST(close AS REAL) * volume AS turnover
            FROM daily_candles
            WHERE date = ? AND stock_code != ? AND close >= ?
            ORDER BY turnover DESC
            LIMIT ?
            """,
            (latest_date, INDEX_CODE, MIN_PRICE, top_n),
        ).fetchall()

    codes = [r[0] for r in rows]
    logger.info("watchlist 선발 (%s 기준): 거래대금 상위 %d종목", latest_date, len(codes))
    return codes


def write_auto_watchlist(codes: list[str]) -> None:
    data = {
        "generated_at": datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S"),
        "codes": codes,
    }
    with open(config.WATCHLIST_AUTO_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logger.info("watchlist_auto.json 갱신: %d종목", len(codes))


def run(years: int = 1, top_n: int = TOP_N) -> None:
    summary = collect_market(years=years)
    codes = select_watchlist(top_n)
    write_auto_watchlist(codes)
    discord_post(
        f":telescope: **[전종목 스캔]** {summary['success']}/{summary['total']}종목 갱신, "
        f"내일 감시 대상 {len(codes)}종목 선발 (상위 5: {', '.join(codes[:5])})"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="전 종목 일봉 수집 + watchlist 자동 선발")
    parser.add_argument("--init", action="store_true", help="최초 백필 모드 (--years와 함께 사용)")
    parser.add_argument("--years", type=int, default=None, help="수집 기간(년). 기본: init=5, 평시=1")
    parser.add_argument("--top", type=int, default=TOP_N, help=f"선발 종목 수 (기본 {TOP_N})")
    args = parser.parse_args()

    config.LOG_DIR.mkdir(parents=True, exist_ok=True)
    configure_logging(str(config.LOG_DIR / "market_scan.log"))

    years = args.years if args.years is not None else (5 if args.init else 1)
    run(years=years, top_n=args.top)
