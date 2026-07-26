"""전략별 모의투자 성과 리포트 (breakout / index / lowvol 각각 + 합계).

실현손익은 positions 테이블만으로 항상 계산되고, 보유 중(open) 포지션은 현재가로
평가해 미실현손익을 낸다. lowvol처럼 한 달 들고 가는 전략은 미실현손익이 핵심이라
현재가 평가를 포함한다 (장 마감 후에도 KIS는 마지막 체결가를 반환).

사용법:
    python report.py              # 터미널 출력
    python report.py --discord    # 디스코드로도 전송
"""
import argparse
import logging

import config
import db
from alerts import _post as discord_post

logger = logging.getLogger(__name__)

STRATEGY_LABELS = {"breakout": "돌파(단타)", "index": "지수타이밍", "lowvol": "저변동성"}


def _strategies(conn) -> list[str]:
    """positions에 존재하는 전략 목록 (알려진 순서 우선, 나머지는 뒤에)."""
    found = {r[0] for r in conn.execute("SELECT DISTINCT strategy FROM positions").fetchall()}
    ordered = [s for s in ("breakout", "index", "lowvol") if s in found]
    ordered += sorted(found - set(ordered))
    return ordered


def realized_stats(conn, strategy: str) -> dict:
    """청산 완료 거래의 실현손익/승률/평균수익률."""
    rows = conn.execute(
        "SELECT buy_price, sell_price, qty FROM positions "
        "WHERE strategy = ? AND status = 'closed' AND sell_price IS NOT NULL", (strategy,)
    ).fetchall()
    pnl = sum((s - b) * q for b, s, q in rows)
    rets = [s / b - 1 for b, s, q in rows if b > 0]
    wins = sum(1 for r in rets if r > 0)
    return {
        "trades": len(rows),
        "pnl": pnl,
        "win_rate": (wins / len(rets)) if rets else None,
        "avg_ret": (sum(rets) / len(rets)) if rets else None,
    }


def unrealized_stats(conn, strategy: str, price_of) -> dict:
    """보유 중(open) 포지션을 현재가로 평가한 미실현손익. price_of(code)->int|None."""
    rows = conn.execute(
        "SELECT stock_code, buy_price, qty FROM positions "
        "WHERE strategy = ? AND status = 'open'", (strategy,)
    ).fetchall()
    cost = 0.0
    value = 0.0
    priced = 0
    for code, buy, qty in rows:
        cost += buy * qty
        cur = price_of(code)
        if cur is None:
            value += buy * qty  # 평가 실패분은 원가로 (미실현 0 처리)
        else:
            value += cur * qty
            priced += 1
    return {
        "positions": len(rows),
        "priced": priced,
        "cost": cost,
        "pnl": value - cost,
        "pct": ((value - cost) / cost) if cost > 0 else None,
    }


def _price_lookup():
    """현재가 조회 함수를 반환. 토큰/네트워크 실패 시 항상 None 반환(원가 평가로 폴백)."""
    try:
        import kis_order
        from kis_auth import get_access_token

        token = get_access_token()
    except Exception:
        logger.warning("현재가 조회 준비 실패 (미실현은 원가 기준으로 표시)")
        return (lambda code: None), False

    def price_of(code: str):
        try:
            return kis_order.get_current_price(token, code)["price"]
        except Exception:
            logger.warning("%s 현재가 조회 실패", code)
            return None

    return price_of, True


def _won(n: float) -> str:
    return f"{n:+,.0f}원"


def build_report() -> str:
    db.init_db()
    price_of, live = _price_lookup()

    lines = ["📊 **[성과 리포트]** 전략별 모의투자 손익", ""]
    tot_realized = tot_unreal = tot_trades = 0.0

    with db.get_connection() as conn:
        strategies = _strategies(conn)
        if not strategies:
            return "📊 **[성과 리포트]** 아직 거래 기록이 없습니다. 첫 매매 이후 다시 확인하세요."

        for s in strategies:
            r = realized_stats(conn, s)
            u = unrealized_stats(conn, s, price_of)
            tot_realized += r["pnl"]
            tot_unreal += u["pnl"]
            tot_trades += r["trades"]

            label = STRATEGY_LABELS.get(s, s)
            wr = f"{r['win_rate']:.0%}" if r["win_rate"] is not None else "N/A"
            avg = f"{r['avg_ret']:+.2%}" if r["avg_ret"] is not None else "N/A"
            lines.append(f"■ {label}")
            lines.append(f"   실현: {_won(r['pnl'])} | 청산 {r['trades']}거래 | 승률 {wr} | 거래당 {avg}")
            upct = f" ({u['pct']:+.2%})" if u["pct"] is not None else ""
            lines.append(f"   미실현: {_won(u['pnl'])}{upct} | 보유 {u['positions']}종목")
            lines.append("")

    # 배분 예산 대비 총수익률
    budget = (config.TRADE_BUDGET_KRW * config.MAX_POSITIONS
              + config.ETF_BUDGET_KRW + config.LOWVOL_BUDGET_KRW)
    total = tot_realized + tot_unreal
    pct = f" ({total / budget:+.2%})" if budget > 0 else ""
    lines.append(f"━━ 합계 ━━")
    lines.append(f"실현 {_won(tot_realized)} + 미실현 {_won(tot_unreal)} = {_won(total)}{pct}")
    lines.append(f"(배분 예산 {budget:,.0f}원 / 총 {int(tot_trades)}거래)")
    if not live:
        lines.append("※ 현재가 연결 실패로 미실현은 원가 기준(변동 0)으로 표시됨")
    lines.append("※ 모의투자는 체결이 이상적이라 실전보다 낙관적이며, 표본이 적으면 노이즈입니다.")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="전략별 성과 리포트")
    parser.add_argument("--discord", action="store_true", help="디스코드로도 전송")
    args = parser.parse_args()

    report = build_report()
    print(report)
    if args.discord:
        for i in range(0, len(report), 1900):
            discord_post(report[i:i + 1900])


if __name__ == "__main__":
    from logging_utils import configure_logging

    config.LOG_DIR.mkdir(parents=True, exist_ok=True)
    configure_logging(str(config.LOG_DIR / "report.log"))
    main()
