
import sqlite3
import os
import hashlib
import pandas as pd
from urllib.parse import urlparse

DB_PATH = os.getenv("DATABASE_PATH", "trader_scanner.db")


def connect():

    conn = sqlite3.connect(
        DB_PATH,
        check_same_thread=False
    )

    conn.row_factory = sqlite3.Row

    return conn


def init_db():

    with connect() as con:

        con.execute("""
        CREATE TABLE IF NOT EXISTS sources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT NOT NULL UNIQUE,
            source_type TEXT NOT NULL,
            label TEXT,
            enabled INTEGER NOT NULL DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """)

        con.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            record_hash TEXT NOT NULL UNIQUE,
            trader TEXT,
            asset TEXT,
            market TEXT,
            entry_price REAL,
            direction TEXT,
            trade_type TEXT,
            trade_date TEXT,
            date_basis TEXT,
            stop_loss REAL,
            take_profit REAL,
            verification_status TEXT,
            confidence REAL,
            evidence TEXT,
            source_url TEXT,
            discovered_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """)

        con.execute("""
        CREATE TABLE IF NOT EXISTS scan_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_url TEXT,
            pages_checked INTEGER DEFAULT 0,
            records_saved INTEGER DEFAULT 0,
            error TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """)


def add_source(url, source_type, label=""):

    parsed = urlparse(url)

    if parsed.scheme not in ("http", "https"):
        raise ValueError("Only HTTP and HTTPS URLs are accepted.")

    if not parsed.netloc:
        raise ValueError("Invalid website URL.")

    if source_type not in ("webpage", "rss"):
        raise ValueError("Invalid source type.")

    with connect() as con:

        con.execute(
            """
            INSERT OR IGNORE INTO sources
            (url, source_type, label)
            VALUES (?, ?, ?)
            """,
            (
                url,
                source_type,
                label or parsed.netloc
            )
        )


def list_sources():

    with connect() as con:

        rows = con.execute(
            """
            SELECT *
            FROM sources
            WHERE enabled = 1
            ORDER BY created_at DESC
            """
        ).fetchall()

    return [dict(row) for row in rows]


def delete_source(source_id):

    with connect() as con:

        con.execute(
            "DELETE FROM sources WHERE id = ?",
            (source_id,)
        )


def save_trade(item):

    stable = "|".join([
        str(item.get("source_url", "")),
        str(item.get("asset", "")),
        str(item.get("direction", "")),
        str(item.get("entry_price", "")),
        str(item.get("trade_date", "")),
        str(item.get("evidence", ""))[:180],
    ])

    digest = hashlib.sha256(
        stable.encode("utf-8")
    ).hexdigest()

    fields = [
        "trader",
        "asset",
        "market",
        "entry_price",
        "direction",
        "trade_type",
        "trade_date",
        "date_basis",
        "stop_loss",
        "take_profit",
        "verification_status",
        "confidence",
        "evidence",
        "source_url",
    ]

    values = [
        item.get(field)
        for field in fields
    ]

    with connect() as con:

        cursor = con.execute(
            f"""
            INSERT OR IGNORE INTO trades
            (record_hash, {','.join(fields)})
            VALUES (?, {','.join(['?'] * len(fields))})
            """,
            [digest] + values
        )

        return cursor.rowcount == 1


def get_trades(
    asset=None,
    start_date=None,
    end_date=None,
    direction="ALL",
    market="All markets",
    trade_kind="All",
    min_price=None,
    max_price=None
):

    query = "SELECT * FROM trades WHERE 1=1"

    args = []

    if asset:

        compact = (
            asset.upper()
            .replace("/", "")
            .replace("-", "")
            .replace(" ", "")
        )

        query += """
        AND REPLACE(
            REPLACE(
                REPLACE(UPPER(asset), '/', ''),
            '-', ''),
        ' ', '') = ?
        """

        args.append(compact)

    if start_date:

        query += " AND trade_date >= ?"

        args.append(str(start_date))

    if end_date:

        query += " AND trade_date <= ?"

        args.append(str(end_date))

    if direction != "ALL":

        query += " AND direction = ?"

        args.append(direction)

    if market != "All markets":

        query += " AND market = ?"

        args.append(market)

    if trade_kind == "Trade ideas":

        query += " AND trade_type = 'trade_idea'"

    elif trade_kind == "Execution claims":

        query += " AND trade_type = 'execution_claim'"

    if min_price is not None:

        query += " AND entry_price >= ?"

        args.append(float(min_price))

    if max_price is not None:

        query += " AND entry_price <= ?"

        args.append(float(max_price))

    query += """
    ORDER BY trade_date DESC, discovered_at DESC
    """

    with connect() as con:

        df = pd.read_sql_query(
            query,
            con,
            params=args
        )

    return df
