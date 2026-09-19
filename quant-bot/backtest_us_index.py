"""US 지수 타이밍(절대 모멘텀) 백테스트: 종가>200일선이면 보유, 아니면 현금.

KR판 etf_timing.py의 미장 버전 검증. SPY/QQQ 일봉(yfinance)으로 돌린다.
핵심 질문: "빠지면 관망"만으로 매수후보유 대비 MDD를 얼마나 줄이는가?

미래참조 없음: 신호는 전일 종가>SMA200으로 확정하고 당일 수익률에 반영(1일 지연).
상태 전환(매수/매도)마다 왕복비용을 차감. 현금 구간은 0% (채권 이자 미가정, 보수적).

서브소스 1순위 VIX 레짐 필터(--vix): **2026-09 검증 탈락 -> 참고용**.
가설은 "VIX가 200일선보다 급락을 빨리 잡는다"였으나 실데이터는 정반대였다.
  SPY 전체 +420%/MDD-22.4% -> +376%/MDD-24.5%, 금융위기 +0.9% -> -2.8%
  QQQ 전체 +915%/MDD-27.8% -> +585%/MDD-33.0% (거래 63->85, 평균보유 67->48일)
원인: VIX는 급락을 예고하지 않고 동시/후행으로 튀며, 스파이크는 천장이 아니라
바닥 근처에서 난다. 결국 공포의 저점에서 팔고 진정 후 더 비싸게 재진입하는
휩쏘가 되어 수익은 줄고 MDD는 오히려 깊어졌다. 임계값 튜닝은 베이스라인 수렴
(무의미) 아니면 휩쏘 악화라 구조적 실패이며, 최적값 탐색은 오버피팅이다.
--vix는 재현/대조군 용도로만 남긴다.

서브소스 3순위: 신용 스프레드(--credit). 하이일드 스프레드가 자기 이동평균 위로
벌어지면(신용 악화) 200일선 위여도 관망. VIX(1순위)가 공포가 터진 뒤 튀는 동행·후행
지표라 실패한 것과 달리, 채권시장이 부도위험을 미리 가격에 반영해 주식 급락에
선행하는지를 검증한다. 데이터는 FRED 하이일드 OAS(1996~), 실패 시 HYG/IEF 비율 폴백.

사용법:
    python backtest_us_index.py --split            # SPY/QQQ, 4구간
    python backtest_us_index.py --split --vix      # VIX 필터 비교 (탈락 재현용)
    python backtest_us_index.py --split --credit   # 신용 스프레드 필터 비교 (3순위)
    python backtest_us_index.py --split --credit --credit-ma 100
    python backtest_us_index.py --split --vix --credit   # 둘 다 나란히
    python backtest_us_index.py --tickers SPY,QQQ,IWM --split
"""
import argparse

import numpy as np
import pandas as pd

from backtest_multi import _fmt, summarize

MA_DAYS = 200
SWITCH_COST = 0.001   # 전환 1회(편도) 수수료+슬리피지. 왕복이면 매수·매도 각 1회 차감
START = "2005-01-01"  # 2008 금융위기까지 포함해 하락장 회피력을 길게 검증

SPLIT_WINDOWS = [
    ("전체", None, None),
    ("금융위기 08-09", "2007-06-01", "2010-01-01"),
    ("하락장 2022", "2022-01-01", "2023-01-01"),
    ("최근 23~", "2023-01-01", None),
]


def load_prices(ticker: str) -> pd.DataFrame:
    import yfinance as yf

    df = yf.download(ticker, start=START, auto_adjust=True, progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df.sort_index()


def timing_backtest(df: pd.DataFrame, regime_ok: dict | None = None) -> tuple[pd.Series, pd.DataFrame]:
    """200일선 타이밍. regime_ok[날짜]=False면 200일선 위여도 그날 보유 금지(변동성 레짐 게이트).
    반환: (일별 전략 수익률, 라운드트립 거래목록)."""
    c = df["Close"].astype(float)
    sma = c.rolling(MA_DAYS).mean()
    ret = c.pct_change().to_numpy()
    sig = (c > sma).to_numpy()          # 종가 기준 신호
    dates = [d.strftime("%Y-%m-%d") for d in df.index]
    n = len(c)

    daily: dict[str, float] = {}
    trades: list[dict] = []
    in_pos = False        # 오늘 장중 보유 여부(어제 신호로 결정)
    entry_i = 0
    entry_c = 0.0
    for t in range(MA_DAYS, n):
        # 1일 지연: 어제 종가 신호 + 어제 변동성 레짐으로 오늘 보유 결정 (미래참조 없음)
        vok = True if regime_ok is None else regime_ok.get(dates[t - 1], True)
        hold_today = bool(sig[t - 1]) and vok
        r = ret[t] if hold_today else 0.0
        # 상태 전환 비용: 어제 보유상태(in_pos)와 오늘 목표가 다르면 편도 비용 1회
        if hold_today != in_pos:
            r -= SWITCH_COST
        daily[dates[t]] = r

        if hold_today and not in_pos:                 # 진입
            entry_i, entry_c = t, c.iloc[t]
        elif in_pos and not hold_today:               # 청산 -> 라운드트립 기록
            trades.append({"date": dates[t], "ret": c.iloc[t] / entry_c - 1 - 2 * SWITCH_COST,
                           "hold": t - entry_i})
        in_pos = hold_today
    if in_pos:
        trades.append({"date": dates[-1], "ret": c.iloc[-1] / entry_c - 1 - SWITCH_COST,
                       "hold": n - 1 - entry_i})
    return pd.Series(daily).sort_index(), pd.DataFrame(trades)


def vix_regime(vix_df: pd.DataFrame, threshold: float) -> dict:
    """VIX 종가 < threshold이면 '위험 낮음(진입 허용)'. 날짜(YYYY-MM-DD)->bool 맵."""
    c = vix_df["Close"].astype(float)
    return {d.strftime("%Y-%m-%d"): bool(v < threshold) for d, v in c.items()}


FRED_HY_OAS = "BAMLH0A0HYM2"   # ICE BofA 미국 하이일드 OAS(%), 1996~


def load_credit_series() -> tuple[pd.Series, str] | None:
    """신용위험 시계열을 받는다. 반환: (시계열, 방향) 또는 None.

    1순위 FRED 하이일드 스프레드(낮을수록 안전, 1996~ 장기).
    실패 시 yfinance HYG/IEF 비율로 폴백(높을수록 안전, 2007~).
    """
    # cosd/coed를 명시하지 않으면 FRED가 최근 몇 년만 돌려줘 위기 구간이 비어버린다.
    url = (f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={FRED_HY_OAS}"
           f"&cosd=1996-01-01&coed=2100-01-01")
    try:
        df = pd.read_csv(url)
        df.columns = ["date", "value"] + list(df.columns[2:])
        s = pd.Series(pd.to_numeric(df["value"], errors="coerce").values,
                      index=pd.to_datetime(df["date"])).dropna()
        if len(s) > 500:
            print(f"  신용지표: FRED {FRED_HY_OAS} (하이일드 스프레드) {len(s)}일 "
                  f"({s.index[0]:%Y-%m-%d} ~ {s.index[-1]:%Y-%m-%d})")
            return s, "spread"
        print(f"  FRED 응답이 {len(s)}일뿐 -> HYG/IEF 폴백 시도")
    except Exception as exc:
        print(f"  FRED 로드 실패({exc}) -> HYG/IEF 폴백 시도")

    try:
        hyg, ief = load_prices("HYG"), load_prices("IEF")
        if hyg is None or ief is None or hyg.empty or ief.empty:
            return None
        ratio = (hyg["Close"].astype(float) / ief["Close"].astype(float)).dropna()
        print(f"  신용지표: HYG/IEF 비율(폴백) {len(ratio)}일")
        return ratio, "ratio"
    except Exception as exc:
        print(f"  신용지표 로드 실패({exc})")
        return None


def credit_regime(series: pd.Series, direction: str, ma_days: int, target_dates) -> dict:
    """신용이 악화되지 않는 날만 진입 허용. 거래일에 맞춰 직전값으로 채운다.

    spread: 스프레드가 자기 이동평균 아래 = 신용 안정 -> 허용
    ratio : HYG/IEF가 자기 이동평균 위 = 위험자산 선호 -> 허용
    자기 이동평균 대비 상대 판단이라 수십 년에 걸친 수준 변화에 견고하다.
    """
    ma = series.rolling(ma_days).mean()
    ok = (series < ma) if direction == "spread" else (series > ma)
    idx = pd.to_datetime(sorted(target_dates))
    aligned = ok.reindex(ok.index.union(idx)).ffill().reindex(idx)
    return {d.strftime("%Y-%m-%d"): (True if pd.isna(v) else bool(v)) for d, v in aligned.items()}


def buyhold_line(df: pd.DataFrame, s, e) -> str:
    """같은 구간 매수후보유 벤치마크(누적/MDD)."""
    c = df["Close"].astype(float)
    c.index = [d.strftime("%Y-%m-%d") for d in df.index]
    if s:
        c = c[c.index >= s]
    if e:
        c = c[c.index <= e]
    if len(c) < 2:
        return "구간 데이터 부족"
    eq = c / c.iloc[0]
    mdd = (eq / eq.cummax() - 1).min()
    return f"누적 {eq.iloc[-1] - 1:+.1%} | MDD {mdd:.1%}"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="US 지수 타이밍(200일선) 백테스트")
    parser.add_argument("--tickers", type=str, default="SPY,QQQ")
    parser.add_argument("--split", action="store_true", help="전체/금융위기/2022/최근 4구간")
    parser.add_argument("--start", type=str)
    parser.add_argument("--end", type=str)
    parser.add_argument("--vix", action="store_true",
                        help="변동성 레짐 필터: VIX>=임계면 200일선 위여도 관망 (2026-09 검증 탈락)")
    parser.add_argument("--vix-threshold", type=float, default=30.0, help="VIX 진입 차단 임계 (기본 30)")
    parser.add_argument("--credit", action="store_true",
                        help="신용 스프레드 필터: 하이일드 스프레드가 자기 이평 위(신용 악화)면 관망")
    parser.add_argument("--credit-ma", type=int, default=200, help="신용지표 이동평균 기간 (기본 200)")
    args = parser.parse_args()

    tickers = [t.strip().upper() for t in args.tickers.split(",")]
    vtxt = f" | VIX필터 <{args.vix_threshold:.0f}" if args.vix else ""
    print(f"US 지수타이밍(SMA{MA_DAYS}): {', '.join(tickers)} | 전환비용 편도 {SWITCH_COST:.1%}{vtxt} | {START}~")

    data = {}
    for tk in tickers:
        df = load_prices(tk)
        if df is None or len(df) < MA_DAYS + 20:
            print(f"  {tk}: 데이터 부족, 건너뜀")
            continue
        data[tk] = df

    overlays: list[tuple[str, dict]] = []   # (표시명, 레짐맵)
    if args.vix:
        vix_df = load_prices("^VIX")
        if vix_df is None or vix_df.empty:
            print("  ^VIX 로드 실패 -> VIX 필터 건너뜀")
        else:
            overlays.append(("+VIX", vix_regime(vix_df, args.vix_threshold)))
    if args.credit:
        loaded = load_credit_series()
        if loaded is None:
            print("  신용지표 로드 실패 -> 신용 필터 건너뜀")
        else:
            series, direction = loaded
            all_dates = {d.strftime("%Y-%m-%d") for df in data.values() for d in df.index}
            cr = credit_regime(series, direction, args.credit_ma, all_dates)
            blocked = sum(1 for v in cr.values() if not v)
            print(f"  신용 필터: 이평 {args.credit_ma}일 | 차단(관망) 예정일 {blocked}/{len(cr)}일")
            # 신용 데이터가 구간을 못 덮으면 그 구간 결과는 '기존과 동일'해져 무효다.
            covered = series.index[0].strftime("%Y-%m-%d")
            for wlabel, ws, we in (SPLIT_WINDOWS if args.split else []):
                end = we or "9999"
                if covered > (ws or "0000") and covered < end:
                    print(f"  [경고] '{wlabel}' 구간 시작({ws})보다 신용 데이터가 늦게 시작({covered})"
                          f" -> 그 구간 비교는 무효(기존과 동일해짐)")
                elif covered >= end:
                    print(f"  [경고] '{wlabel}' 구간에 신용 데이터 없음({covered}부터) -> 비교 무효")
            overlays.append(("+신용", cr))

    windows = SPLIT_WINDOWS if args.split else [("결과", args.start, args.end)]
    for label, s, e in windows:
        print(f"\n===== {label} ({s or '처음'} ~ {e or '현재'}) =====")
        for tk, df in data.items():
            base_daily, base_trades = timing_backtest(df)
            rb = summarize(f"{tk}타이밍", base_daily, base_trades, s, e)
            print(f"  {tk:>4} 타이밍      | " + ("구간 없음" if rb is None else _fmt(rb[1])))
            for name, regime in overlays:
                od, ot = timing_backtest(df, regime)
                ro = summarize(f"{tk}{name}", od, ot, s, e)
                print(f"  {tk:>4} 타이밍{name:<5}| " + ("구간 없음" if ro is None else _fmt(ro[1])))
            print(f"  {tk:>4} 매수보유    | {buyhold_line(df, s, e)}")
