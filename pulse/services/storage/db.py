import aiosqlite
from pathlib import Path
from typing import Any, Optional

DB_PATH = Path(__file__).resolve().parents[2] / 'data' / 'pulse.db'
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

INIT_SQL = [
    '''CREATE TABLE IF NOT EXISTS telemetry (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts INTEGER NOT NULL,
        source TEXT NOT NULL,
        metric TEXT NOT NULL,
        value REAL,
        data TEXT
    )''',
    '''CREATE INDEX IF NOT EXISTS idx_tel_ts ON telemetry(ts)'''
]

async def get_db():
    db = await aiosqlite.connect(str(DB_PATH))
    await db.execute('PRAGMA journal_mode=WAL')
    for stmt in INIT_SQL:
        await db.execute(stmt)
    await db.commit()
    return db

async def insert_telemetry(ts: int, source: str, metric: str, value: Optional[float], data: Optional[str] = None):
    async with await get_db() as db:
        await db.execute(
            'INSERT INTO telemetry (ts, source, metric, value, data) VALUES (?, ?, ?, ?, ?)',
            (ts, source, metric, value, data)
        )
        await db.commit()

async def query_telemetry(metric: Optional[str] = None, since_ts: Optional[int] = None, limit: int = 1000):
    sql = 'SELECT ts, source, metric, value, data FROM telemetry WHERE 1=1'
    params: list[Any] = []
    if metric:
        sql += ' AND metric = ?'
        params.append(metric)
    if since_ts:
        sql += ' AND ts >= ?'
        params.append(since_ts)
    sql += ' ORDER BY ts DESC LIMIT ?'
    params.append(limit)
    async with await get_db() as db:
        async with db.execute(sql, params) as cur:
            rows = await cur.fetchall()
    return rows
