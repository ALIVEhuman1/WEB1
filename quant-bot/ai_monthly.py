"""월간 AI 분석: 한 달치 실전 기록을 백테스트 기대치와 비교하고 개선 가설을 제안한다.

중요한 설계 원칙: 여기서 나온 제안은 절대 자동 반영되지 않는다.
제안 -> backtest.py로 검증 -> 사람이 승인 -> 반영 순서를 지킨다.
Claude에게도 '백테스트 가능한 구체적 규칙 변경' 형태로만 제안하도록 강제한다.
"""
import logging
import os
import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo

import config
import db
from ai_report import BACKTEST_BASELINE, post_to_discord

logger = logging.getLogger(__name__)

KST = ZoneInfo("Asia/Seoul")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
MODEL = "claude-opus-4-8"

SYSTEM_PROMPT = """당신은 퀀트 트레이딩 봇의 월간 성과 분석가입니다.

역할: 실전 한 달 기록을 백테스트 기대치와 비교 분석하고, 개선 '가설'을 제안합니다.

절대 규칙:
1. 제안은 반영되지 않습니다. 모든 제안은 백테스트 검증과 운용자 승인을 거칩니다.
   따라서 제안은 반드시 '백테스트 가능한 구체적 규칙 변경' 형태여야 합니다.
   좋은 예: "K를 0.8에서 0.9로 올려 백테스트" / 나쁜 예: "시장 상황을 더 고려"
2. 표본이 작으면(거래 30건 미만) 통계적 판단을 유보하고 그렇게 명시하세요.
3. 실전-백테스트 괴리(슬리피지, 체결율)와 전략 자체 성과를 구분해서 분석하세요.

출력 형식 (한국어, 전체 1800자 이내):
📅 월간 분석: YYYY년 MM월
1. 실전 성과 요약 (거래수/승률/수익률/최대낙폭)
2. 백테스트 기대치와의 비교 (괴리가 있다면 원인 추정)
3. 실행 품질 총평 (슬리피지 등)
4. 백테스트해볼 가설 제안 (0~3개, 각각 구체적 규칙 + 기대 효과. 근거 없으면 '이번 달은 제안 없음')"""


def collect_month_context(year_month: str | None = None) -> str:
    """해당 월(YYYYMM, 기본 이번 달)의 청산 거래 전체 + 통계."""
    ym = year_month or datetime.now(KST).strftime("%Y%m")
    with db.get_connection() as conn:
        conn.row_factory = sqlite3.Row
        closed = [dict(r) for r in conn.execute(
            "SELECT * FROM positions WHERE status='closed' AND sell_price IS NOT NULL "
            "AND sell_date LIKE ? ORDER BY sell_date", (ym + "%",)).fetchall()]
        all_closed = [dict(r) for r in conn.execute(
            "SELECT * FROM positions WHERE status='closed' AND sell_price IS NOT NULL").fetchall()]

    lines = [f"[분석 대상 월] {ym[:4]}년 {ym[4:]}월", ""]
    lines.append(f"[이달 청산 거래 {len(closed)}건]")
    for p in closed:
        ret = (p["sell_price"] / p["buy_price"] - 1) * 100
        lines.append(f"- {p['sell_date']} {p['stock_code']}: 매수 {p['buy_price']:,.0f} "
                     f"({p['buy_date']}) -> 매도 {p['sell_price']:,.0f} ({ret:+.2f}%)")

    if closed:
        rets = [(p["sell_price"] / p["buy_price"] - 1) for p in closed]
        wins = sum(1 for r in rets if r > 0)
        cum = 1.0
        for r in rets:
            cum *= (1 + r)
        lines.append(f"\n[이달 통계] 승률 {wins/len(rets):.0%}, 월 수익률 {(cum-1)*100:+.2f}%, "
                     f"평균 거래당 {sum(rets)/len(rets)*100:+.3f}%")

    if all_closed:
        rets = [(p["sell_price"] / p["buy_price"] - 1) for p in all_closed]
        cum = 1.0
        for r in rets:
            cum *= (1 + r)
        lines.append(f"[전체 누적] {len(rets)}거래, 누적수익률 {(cum-1)*100:+.2f}%")

    lines.append(f"\n[백테스트 기준선] {BACKTEST_BASELINE}")
    lines.append("\n[현재 확정 규칙] 고정 50종목, K=0.8, 전일 거래량>20일 평균 필터, "
                 "코스피>20일선 시장 필터, 익일 시가 청산, 종목당 100만원, 최대 5종목")
    return "\n".join(lines)


def run_monthly_analysis(year_month: str | None = None) -> None:
    if not ANTHROPIC_API_KEY:
        logger.info("ANTHROPIC_API_KEY 미설정으로 월간 분석 생략")
        return
    db.init_db()
    context = collect_month_context(year_month)

    import anthropic

    client = anthropic.Anthropic()
    response = client.messages.create(
        model=MODEL,
        max_tokens=3000,
        thinking={"type": "adaptive"},
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": f"이번 달 실전 기록입니다. 분석과 가설 제안 부탁합니다.\n\n{context}"}],
    )
    report = "".join(block.text for block in response.content if block.type == "text")
    logger.info("월간 AI 분석:\n%s", report)
    post_to_discord(report)


if __name__ == "__main__":
    import argparse

    from logging_utils import configure_logging

    parser = argparse.ArgumentParser(description="월간 AI 성과 분석")
    parser.add_argument("--month", type=str, help="분석할 월 YYYYMM (기본: 이번 달)")
    args = parser.parse_args()

    config.LOG_DIR.mkdir(parents=True, exist_ok=True)
    configure_logging(str(config.LOG_DIR / "ai_report.log"))
    run_monthly_analysis(args.month)
