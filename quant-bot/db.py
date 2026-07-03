"""SQLite 저장소: 분봉/일봉 데이터 스키마, UPSERT, 조회 함수."""
import sqlite3

import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS candles (
    stock_code TEXT NOT NULL,
    date       TEXT NOT NULL,  -- YYYYMMDD
    time       TEXT NOT NULL,  -- HHMMSS
    open       INTEGER NOT NULL,
    high       INTEGER NOT NULL,
    low        INTEGER NOT NULL,
    close      INTEGER NOT NULL,
    volume     INTEGER NOT NULL,
    PRIMARY KEY (stock_code, date, time)
);
"""

DAILY_SCHEMA = """
CREATE TABLE IF NOT EXISTS daily_candles (
    stock_code TEXT NOT NULL,
    date       TEXT NOT NULL,  -- YYYYMMDD
    open       INTEGER NOT NULL,
    high       INTEGER NOT NULL,
    low        INTEGER NOT NULL,
    close      INTEGER NOT NULL,
    volume     INTEGER NOT NULL,
    PRIMARY KEY (stock_code, date)
);
"""

POSITIONS_SCHEMA = """
CREATE TABLE IF NOT EXISTS positions (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_code TEXT NOT NULL,
    qty        INTEGER NOT NULL,
    buy_price  REAL NOT NULL,
    buy_date   TEXT NOT NULL,   -- YYYYMMDD
    status     TEXT NOT NULL DEFAULT 'open',  -- open / closed
    sell_price REAL,
    sell_date  TEXT
);
"""


def get_connection() -> sqlite3.Connection:
    return sqlite3.connect(config.DB_PATH)


def init_db() -> None:
    with get_connection() as conn:
        conn.execute(SCHEMA)
        conn.execute(DAILY_SCHEMA)
        conn.execute(POSITIONS_SCHEMA)


def upsert_candles(rows: list[dict]) -> int:
    if not rows:
        return 0
    with get_connection() as conn:
        conn.executemany(
            """
            INSERT INTO candles (stock_code, date, time, open, high, low, close, volume)
            VALUES (:stock_code, :date, :time, :open, :high, :low, :close, :volume)
            ON CONFLICT(stock_code, date, time) DO UPDATE SET
                open = excluded.open,
                high = excluded.high,
                low = excluded.low,
                close = excluded.close,
                volume = excluded.volume
            """,
            rows,
        )
    return len(rows)


def get_candles(stock_code: str, start_date: str | None = None, end_date: str | None = None) -> list[dict]:
    """종목의 분봉을 dict 리스트로 조회한다 (date, time 오름차순)."""
    query = "SELECT stock_code, date, time, open, high, low, close, volume FROM candles WHERE stock_code = ?"
    params: list = [stock_code]

    if start_date:
        query += " AND date >= ?"
        params.append(start_date)
    if end_date:
        query += " AND date <= ?"
        params.append(end_date)
    query += " ORDER BY date, time"

    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]


def get_candles_df(stock_code: str, start_date: str | None = None, end_date: str | None = None):
    """백테스트에서 바로 쓸 수 있도록 pandas DataFrame으로 조회한다."""
    import pandas as pd

    rows = get_candles(stock_code, start_date, end_date)
    return pd.DataFrame(rows, columns=["stock_code", "date", "time", "open", "high", "low", "close", "volume"])


def upsert_daily_candles(rows: list[dict]) -> int:
    if not rows:
        return 0
    with get_connection() as conn:
        conn.executemany(
            """
            INSERT INTO daily_candles (stock_code, date, open, high, low, close, volume)
            VALUES (:stock_code, :date, :open, :high, :low, :close, :volume)
            ON CONFLICT(stock_code, date) DO UPDATE SET
                open = excluded.open,
                high = excluded.high,
                low = excluded.low,
                close = excluded.close,
                volume = excluded.volume
            """,
            rows,
        )
    return len(rows)


def get_daily_candles(stock_code: str, start_date: str | None = None, end_date: str | None = None) -> list[dict]:
    """종목의 일봉을 dict 리스트로 조회한다 (date 오름차순)."""
    query = "SELECT stock_code, date, open, high, low, close, volume FROM daily_candles WHERE stock_code = ?"
    params: list = [stock_code]

    if start_date:
        query += " AND date >= ?"
        params.append(start_date)
    if end_date:
        query += " AND date <= ?"
        params.append(end_date)
    query += " ORDER BY date"

    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]


def get_daily_candles_df(stock_code: str, start_date: str | None = None, end_date: str | None = None):
    """일봉을 pandas DataFrame으로 조회한다 (변동성 돌파 백테스트용)."""
    import pandas as pd

    rows = get_daily_candles(stock_code, start_date, end_date)
    return pd.DataFrame(rows, columns=["stock_code", "date", "open", "high", "low", "close", "volume"])


# ---- 자동매매 포지션 관리 ----

def add_position(stock_code: str, qty: int, buy_price: float, buy_date: str) -> int:
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO positions (stock_code, qty, buy_price, buy_date) VALUES (?, ?, ?, ?)",
            (stock_code, qty, buy_price, buy_date),
        )
        return cursor.lastrowid


def get_open_positions() -> list[dict]:
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("SELECT * FROM positions WHERE status = 'open' ORDER BY id")
        return [dict(row) for row in cursor.fetchall()]


def close_position(position_id: int, sell_price: float, sell_date: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE positions SET status = 'closed', sell_price = ?, sell_date = ? WHERE id = ?",
            (sell_price, sell_date, position_id),
        )
