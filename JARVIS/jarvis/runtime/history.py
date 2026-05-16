"""
Histórico de uso (SQLite local).

Tudo OPT-IN: o registro só acontece se `runtime.history_enabled` estiver True
na config (default True). O usuário pode desabilitar em Configurações → Privacidade
e apagar todos os dados a qualquer momento.

DB fica em %APPDATA%/JARVIS/jarvis.history.db (mesma pasta dos modes/config).
Schema mínimo: 1 tabela `executions` com mode_id, source, timestamps e contadores.
"""
import os
import sqlite3
import threading
import datetime
from contextlib import contextmanager

from jarvis.constants import USER_DATA_DIR

DB_PATH = os.path.join(USER_DATA_DIR, "jarvis.history.db")

# Lock pra serializar gravações (SQLite aceita reads concorrentes mas writes melhor seriais)
_db_lock = threading.Lock()
_initialized = False


@contextmanager
def _connect():
    conn = sqlite3.connect(DB_PATH, timeout=5.0)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    """Cria a tabela se não existir. Idempotente."""
    global _initialized
    with _db_lock:
        with _connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS executions (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    mode_id      TEXT NOT NULL,
                    mode_name    TEXT NOT NULL,
                    source       TEXT NOT NULL,
                    started_at   TEXT NOT NULL,
                    duration_ms  INTEGER NOT NULL,
                    success      INTEGER NOT NULL,
                    errors       INTEGER NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_exec_started ON executions(started_at);
                CREATE INDEX IF NOT EXISTS idx_exec_mode    ON executions(mode_id);
                """
            )
            conn.commit()
        _initialized = True


def is_enabled() -> bool:
    """Lê do state em runtime — default True. Falsea quando o user desliga."""
    from jarvis import state
    cfg = state.runtime_config_state.get("data") or {}
    return cfg.get("runtime", {}).get("history_enabled", True)


def record_execution(mode_id: str, mode_name: str, source: str,
                     started_at: datetime.datetime, duration_ms: int,
                     success: int, errors: int) -> None:
    """Grava 1 execução. Não-bloqueante: erros silenciosos pra não travar nada."""
    if not _initialized or not is_enabled():
        return
    try:
        with _db_lock, _connect() as conn:
            conn.execute(
                "INSERT INTO executions (mode_id, mode_name, source, started_at, duration_ms, success, errors) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (mode_id, mode_name, source, started_at.isoformat(),
                 int(duration_ms), int(success), int(errors)),
            )
            conn.commit()
    except Exception as e:
        print(f"[History] falha ao gravar: {e}")


def get_stats(limit_recent: int = 20) -> dict:
    """Resumo do histórico pro painel."""
    if not _initialized:
        return {"total": 0, "top_modes": [], "by_hour": [], "recent": []}

    try:
        with _connect() as conn:
            total = conn.execute("SELECT COUNT(*) FROM executions").fetchone()[0]

            top_modes = [
                {"mode_id": r["mode_id"], "mode_name": r["mode_name"], "count": r["c"]}
                for r in conn.execute(
                    "SELECT mode_id, mode_name, COUNT(*) AS c FROM executions "
                    "GROUP BY mode_id ORDER BY c DESC LIMIT 5"
                )
            ]

            by_hour = [{"hour": h, "count": 0} for h in range(24)]
            for r in conn.execute(
                "SELECT CAST(strftime('%H', started_at) AS INTEGER) AS h, COUNT(*) AS c "
                "FROM executions GROUP BY h"
            ):
                if 0 <= r["h"] <= 23:
                    by_hour[r["h"]]["count"] = r["c"]

            recent = [
                {
                    "mode_id": r["mode_id"],
                    "mode_name": r["mode_name"],
                    "source": r["source"],
                    "started_at": r["started_at"],
                    "duration_ms": r["duration_ms"],
                    "success": r["success"],
                    "errors": r["errors"],
                }
                for r in conn.execute(
                    "SELECT mode_id, mode_name, source, started_at, duration_ms, success, errors "
                    "FROM executions ORDER BY id DESC LIMIT ?",
                    (limit_recent,),
                )
            ]

            return {
                "total": total,
                "top_modes": top_modes,
                "by_hour": by_hour,
                "recent": recent,
                "enabled": is_enabled(),
            }
    except Exception as e:
        print(f"[History] falha ao ler stats: {e}")
        return {"total": 0, "top_modes": [], "by_hour": [], "recent": [], "enabled": is_enabled()}


def clear_all() -> int:
    """Apaga todas as execuções. Retorna número de linhas removidas."""
    if not _initialized:
        return 0
    try:
        with _db_lock, _connect() as conn:
            cur = conn.execute("DELETE FROM executions")
            conn.commit()
            return cur.rowcount or 0
    except Exception as e:
        print(f"[History] falha ao limpar: {e}")
        return 0
