import sqlite3
from datetime import datetime, timezone
from pathlib import Path


class SourceStateStore:
    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS source_state (
                    source_key TEXT PRIMARY KEY,
                    etag TEXT,
                    last_modified TEXT,
                    last_seen_ts TEXT,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def get_state(self, source_key: str) -> dict:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT source_key, etag, last_modified, last_seen_ts, updated_at
                FROM source_state
                WHERE source_key = ?
                """,
                (source_key,),
            ).fetchone()

        if not row:
            return {}

        return {
            "source_key": row[0],
            "etag": row[1],
            "last_modified": row[2],
            "last_seen_ts": row[3],
            "updated_at": row[4],
        }

    def upsert_state(
        self,
        source_key: str,
        etag: str | None = None,
        last_modified: str | None = None,
        last_seen_ts: str | None = None,
    ) -> None:
        current = self.get_state(source_key)
        merged_etag = etag if etag is not None else current.get("etag")
        merged_last_modified = (
            last_modified if last_modified is not None else current.get("last_modified")
        )
        merged_last_seen_ts = (
            last_seen_ts if last_seen_ts is not None else current.get("last_seen_ts")
        )
        updated_at = datetime.now(timezone.utc).isoformat()

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO source_state (source_key, etag, last_modified, last_seen_ts, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(source_key) DO UPDATE SET
                    etag=excluded.etag,
                    last_modified=excluded.last_modified,
                    last_seen_ts=excluded.last_seen_ts,
                    updated_at=excluded.updated_at
                """,
                (
                    source_key,
                    merged_etag,
                    merged_last_modified,
                    merged_last_seen_ts,
                    updated_at,
                ),
            )
            conn.commit()