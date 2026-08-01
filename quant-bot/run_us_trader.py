"""미국 자동매매 실행 트리거 (cron 진입점) — ① 지수타이밍 + ② 돌파.

동작: 일봉 갱신 -> 당일 '종가'로 신호 확정 -> ①② 관리(청산/진입).
백테스트가 '종가 신호 -> 익일 시가 체결'이므로, 미 장마감 후 실행해 주문을 내면
다음 세션에 체결되어 백테스트와 정합. 예산=0이면 드라이런(신호만 Discord 통보).

토큰은 실주문(예산>0)이 하나라도 있을 때만 발급 -> 드라이런은 KIS 인증 없이도 동작.

crontab 예시 (미 동부시간 기준, 장마감 16:00 ET 직후 16:15 ET):
    # ET로 도는 서버:
    15 16 * * 1-5 cd /path/to/quant-bot && /path/to/venv/bin/python run_us_trader.py
    # KST로 도는 서버 (겨울 EST=한국-14h, 여름 EDT=한국-13h): 대략 06:15 KST
    15 6  * * 2-6 cd /path/to/quant-bot && /path/to/venv/bin/python run_us_trader.py
"""
import logging

import config
from logging_utils import configure_logging

config.LOG_DIR.mkdir(parents=True, exist_ok=True)
configure_logging(str(config.LOG_DIR / "us_trader.log"))

import db  # noqa: E402  (로깅 설정 이후 임포트)
import us_data  # noqa: E402
import us_index_timing  # noqa: E402
import us_breakout_live  # noqa: E402
from alerts import _post as discord_post  # noqa: E402
from lock import single_instance_lock  # noqa: E402
from us_universe import load_us_universe  # noqa: E402

logger = logging.getLogger(__name__)


def _latest_spy_date() -> str | None:
    rows = db.get_us_daily_candles(config.US_INDEX_SYMBOL)
    return rows[-1]["date"] if rows else None


def run_us_trading_day() -> dict:
    db.init_db()

    # 1) 일봉 갱신 (SPY + 유니버스). 돌파 드라이런도 유니버스가 필요하므로 항상 전체.
    symbols = [config.US_INDEX_SYMBOL] + load_us_universe()
    fetch = us_data.update_us_daily(symbols)
    discord_post(f":satellite: **[미장]** 일봉 갱신: 성공 {fetch['ok']}/{len(symbols)}"
                 + (f", 실패 {len(fetch['failed'])}" if fetch["failed"] else ""))

    today = _latest_spy_date()
    if today is None:
        discord_post(":rotating_light: **[미장]** SPY 일봉이 없어 신호 계산 불가. 수집/네트워크 점검 필요.")
        return {"error": "no-spy-data"}

    # 2) 실주문이 있을 때만 토큰 발급 (드라이런은 인증 불필요)
    live = config.US_INDEX_BUDGET_USD > 0 or config.US_BREAKOUT_BUDGET_USD > 0
    token = None
    if live:
        from kis_auth import get_access_token
        token = get_access_token()

    # 3) ① 지수타이밍
    try:
        idx_action = us_index_timing.manage_position(token, today)
    except Exception:
        logger.exception("미장 지수타이밍 처리 실패 (돌파는 계속)")
        idx_action = "error"
        discord_post(":rotating_light: **[미장 지수타이밍]** 처리 중 오류 - logs/us_trader.log 확인")

    # 4) ② 돌파
    try:
        brk_action = us_breakout_live.manage_position(token, today)
    except Exception:
        logger.exception("미장 돌파 처리 실패")
        brk_action = "error"
        discord_post(":rotating_light: **[미장 돌파]** 처리 중 오류 - logs/us_trader.log 확인")

    mode = "실거래" if live else "드라이런(신호만)"
    logger.info("=== 미장 자동매매 종료(%s): 지수 %s, 돌파 %s ===", mode, idx_action, brk_action)
    discord_post(f":clipboard: **[미장 자동매매 {today} · {mode}]** 지수 {idx_action} / 돌파 {brk_action}")
    return {"date": today, "index": idx_action, "breakout": brk_action, "live": live}


if __name__ == "__main__":
    try:
        with single_instance_lock("us_trader"):
            run_us_trading_day()
    except RuntimeError as exc:
        logger.warning(str(exc))
    except Exception:
        logger.exception("미장 자동매매 비정상 종료")
        discord_post(":rotating_light: **[미장 자동매매]** 비정상 종료 - logs/us_trader.log 확인 필요")
