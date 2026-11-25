"""Server-side request budget for the shared DeepSeek credential."""

import os
import sqlite3
import time
from pathlib import Path

DEFAULT_DB = Path(__file__).parent / "data" / "raw" / "chat_quota.sqlite3"


def reserve_request(session_id: str, db_path: Path = DEFAULT_DB, now: float | None = None) -> None:
    """Atomically reserve one request; fail closed if quota storage is unavailable."""
    if not session_id or len(session_id) > 64:
        raise RuntimeError("会话状态无效，请刷新页面后重试。")
    now = time.time() if now is None else now
    daily_limit = max(1, int(os.getenv("DEEPSEEK_DAILY_REQUEST_LIMIT", "30")))
    session_limit = max(1, int(os.getenv("DEEPSEEK_SESSION_DAILY_LIMIT", "8")))
    minute_limit = max(1, int(os.getenv("DEEPSEEK_MINUTE_REQUEST_LIMIT", "4")))
    cooldown = max(1, int(os.getenv("DEEPSEEK_SESSION_COOLDOWN_SECONDS", "12")))
    try:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(db_path, timeout=10, isolation_level=None) as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("CREATE TABLE IF NOT EXISTS requests (ts REAL NOT NULL, session TEXT NOT NULL)")
            conn.execute("CREATE INDEX IF NOT EXISTS requests_ts ON requests(ts)")
            conn.execute("DELETE FROM requests WHERE ts < ?", (now - 86400,))
            total = conn.execute("SELECT COUNT(*) FROM requests").fetchone()[0]
            recent = conn.execute("SELECT COUNT(*) FROM requests WHERE ts >= ?", (now - 60,)).fetchone()[0]
            own = conn.execute("SELECT COUNT(*), MAX(ts) FROM requests WHERE session = ?", (session_id,)).fetchone()
            if total >= daily_limit:
                raise RuntimeError("研究助手今日共享调用额度已用完，请明天再试。")
            if recent >= minute_limit:
                raise RuntimeError("研究助手当前请求较多，请一分钟后再试。")
            if own[0] >= session_limit:
                raise RuntimeError("此会话今日调用次数已用完，请明天再试。")
            if own[1] is not None and now - own[1] < cooldown:
                raise RuntimeError(f"请间隔至少 {cooldown} 秒再发送。")
            conn.execute("INSERT INTO requests(ts, session) VALUES(?, ?)", (now, session_id))
            conn.commit()
    except sqlite3.Error as exc:
        raise RuntimeError("调用保护暂时不可用，研究助手已停止外部请求。") from exc
