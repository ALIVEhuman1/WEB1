"""매일 장 마감 후 Claude가 당일 매매의 '실행 품질'을 채점하는 리포트.

중요한 설계 원칙: 이 모듈은 전략 파라미터를 절대 조정하지 않는다.
하루 결과는 노이즈라서 전략 판단의 근거가 될 수 없고, 평가 대상은
오직 실행 품질(체결 슬리피지, 청산 타이밍, 에러, 놓친 신호)과
백테스트 기대 궤도 대비 누적 성과의 위치다.

ANTHROPIC_API_KEY가 .env에 없으면 조용히 건너뛴다 (opt-in).
"""
import logging
import os
from datetime import datetime
from zoneinfo import ZoneInfo

import config
import db
from alerts import _post as discord_post

logger = logging.getLogger(__name__)

KST = ZoneInfo("Asia/Seoul")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
MODEL = "claude-opus-4-8"

# 백테스트로 확정된 기대치 (5년, K=0.8 + 거래량/시장 필터 + 익일시가 청산)
BACKTEST_BASELINE = (
    "백테스트 기대치: 연 수익률 약 +3%, 승률 약 49%, 거래당 평균 +0.37%(상승장 기준), "
    "MDD -11% 이내, 슬리피지 가정 0.1%, 하락장에서는 시장 필터로 진입 자체가 드묾."
)

SYSTEM_PROMPT = """당신은 퀀트 트레이딩 봇의 '실행 품질' 평가자입니다.

절대 규칙: 전략(K값, 필터, 종목 선정)의 수정을 제안하지 마세요. 하루 결과는
통계적 노이즈이며 전략 평가의 근거가 될 수 없습니다. 당신의 평가 대상은
봇이 정해진 규칙을 '기계적으로 정확히 실행했는가'입니다.

채점 기준 (100점 만점):
- 체결 품질: 매수가가 돌파가 대비 슬리피지 가정(0.1%) 이내인가
- 청산 품질: 오버나잇 포지션이 9시 초반에 제때 청산됐는가
- 시스템 안정성: 로그에 에러/재시도 폭주/비정상 종료가 없는가
- 규칙 준수: 필터 판정과 실제 행동이 일치하는가 (진입 금지일에 매수 없음 등)

당일 손익이 마이너스라는 이유로 감점하지 마세요. 규칙대로 정확히 실행하고
돈을 잃은 날은 100점이고, 규칙을 어기고 돈을 번 날은 낮은 점수입니다.

출력 형식 (한국어, 전체 1200자 이내):
📊 실행 품질: NN/100
한 줄 요약
- 체결/청산/시스템 각각 1줄 평가
- 특이사항 또는 관찰 포인트 (없으면 '없음')
- 누적 성과의 백테스트 궤도 대비 위치 1줄"""


def _today() -> str:
    return datetime.now(KST).strftime("%Y%m%d")


def _read_log_tail(path, max_lines: int = 120) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return "".join(f.readlines()[-max_lines:])
    except OSError:
        return "(로그 파일 없음)"


def collect_context(today: str | None = None) -> str:
    """당일 거래/포지션/로그/누적 성과를 텍스트로 수집한다."""
    today = today or _today()
    with db.get_connection() as conn:
        conn.row_factory = __import__("sqlite3").Row
        opened = [dict(r) for r in conn.execute(
            "SELECT * FROM positions WHERE buy_date = ?", (today,)).fetchall()]
        closed = [dict(r) for r in conn.execute(
            "SELECT * FROM positions WHERE sell_date = ?", (today,)).fetchall()]
        all_closed = [dict(r) for r in conn.execute(
            "SELECT * FROM positions WHERE status = 'closed' AND sell_price IS NOT NULL").fetchall()]

    lines = [f"[날짜] {today}", ""]

    lines.append(f"[오늘 신규 매수 {len(opened)}건]")
    for p in opened:
        lines.append(f"- {p['stock_code']} x{p['qty']} @ {p['buy_price']:,.0f}원")

    lines.append(f"\n[오늘 청산 {len(closed)}건]")
    for p in closed:
        ret = (p["sell_price"] / p["buy_price"] - 1) * 100
        lines.append(f"- {p['stock_code']}: 매수 {p['buy_price']:,.0f} -> 매도 {p['sell_price']:,.0f} ({ret:+.2f}%)")

    if all_closed:
        rets = [(p["sell_price"] / p["buy_price"] - 1) for p in all_closed]
        wins = sum(1 for r in rets if r > 0)
        cum = 1.0
        for r in rets:
            cum *= (1 + r)
        lines.append(f"\n[누적 실전 성과] 총 {len(rets)}거래, 승률 {wins/len(rets):.0%}, "
                     f"누적수익률 {(cum-1)*100:+.2f}%")

    lines.append(f"\n[백테스트 기준선] {BACKTEST_BASELINE}")
    lines.append(f"\n[오늘 트레이더 로그 (마지막 120줄)]\n{_read_log_tail(config.LOG_DIR / 'trader.log')}")
    return "\n".join(lines)


def generate_report(context: str) -> str:
    import anthropic

    client = anthropic.Anthropic()
    response = client.messages.create(
        model=MODEL,
        max_tokens=2000,
        thinking={"type": "adaptive"},
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": f"오늘의 매매 기록입니다. 실행 품질을 채점해주세요.\n\n{context}"}],
    )
    return "".join(block.text for block in response.content if block.type == "text")


def post_to_discord(text: str) -> None:
    """Discord 메시지는 2000자 제한이 있어 나눠 보낸다."""
    for i in range(0, len(text), 1900):
        discord_post(text[i:i + 1900])


def run_daily_report() -> None:
    if not ANTHROPIC_API_KEY:
        logger.info("ANTHROPIC_API_KEY 미설정으로 AI 리포트 생략")
        return
    db.init_db()
    context = collect_context()
    logger.info("AI 실행 품질 채점 요청 (%s)", MODEL)
    report = generate_report(context)
    logger.info("AI 리포트:\n%s", report)
    post_to_discord(report)


if __name__ == "__main__":
    from logging_utils import configure_logging

    config.LOG_DIR.mkdir(parents=True, exist_ok=True)
    configure_logging(str(config.LOG_DIR / "ai_report.log"))
    run_daily_report()
