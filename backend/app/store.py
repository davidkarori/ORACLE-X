import json
import sqlite3
import threading
from pathlib import Path
from typing import Any

from .domain import AuditEvent, WorkflowRun, utc_now


class AuditStore:
    def __init__(self, path: str) -> None:
        self.path = path
        self._lock = threading.Lock()
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._initialize()

    def _initialize(self) -> None:
        with self._connection:
            self._connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS workflow_runs (
                    id TEXT PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    state TEXT NOT NULL,
                    status TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS audit_events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL REFERENCES workflow_runs(id),
                    kind TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS execution_intents (
                    idempotency_key TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL REFERENCES workflow_runs(id),
                    created_at TEXT NOT NULL
                );
                CREATE TRIGGER IF NOT EXISTS audit_events_no_update
                BEFORE UPDATE ON audit_events BEGIN
                    SELECT RAISE(ABORT, 'audit events are append-only');
                END;
                CREATE TRIGGER IF NOT EXISTS audit_events_no_delete
                BEFORE DELETE ON audit_events BEGIN
                    SELECT RAISE(ABORT, 'audit events are append-only');
                END;
                """
            )

    def reserve_execution(self, idempotency_key: str, run_id: str) -> bool:
        try:
            with self._lock, self._connection:
                self._connection.execute(
                    "INSERT INTO execution_intents(idempotency_key, run_id, created_at) VALUES (?, ?, ?)",
                    (idempotency_key, run_id, utc_now().isoformat()),
                )
            return True
        except sqlite3.IntegrityError:
            return False

    def save_run(self, run: WorkflowRun) -> None:
        payload = json.dumps(run.model_dump(mode="json"), separators=(",", ":"))
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT INTO workflow_runs(id, symbol, state, status, payload, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    state=excluded.state,
                    status=excluded.status,
                    payload=excluded.payload,
                    updated_at=excluded.updated_at
                """,
                (
                    run.id,
                    run.symbol,
                    run.state.value,
                    run.status,
                    payload,
                    run.created_at.isoformat(),
                    run.updated_at.isoformat(),
                ),
            )

    def append(self, run_id: str, kind: str, actor: str, payload: dict[str, Any]) -> AuditEvent:
        created_at = utc_now()
        body = json.dumps(payload, separators=(",", ":"), default=str)
        with self._lock, self._connection:
            cursor = self._connection.execute(
                "INSERT INTO audit_events(run_id, kind, actor, payload, created_at) VALUES (?, ?, ?, ?, ?)",
                (run_id, kind, actor, body, created_at.isoformat()),
            )
        return AuditEvent(
            sequence=int(cursor.lastrowid),
            kind=kind,
            actor=actor,
            payload=payload,
            created_at=created_at,
        )

    def get_run(self, run_id: str) -> WorkflowRun | None:
        row = self._connection.execute(
            "SELECT payload FROM workflow_runs WHERE id = ?", (run_id,)
        ).fetchone()
        return WorkflowRun.model_validate_json(row["payload"]) if row else None

    def list_runs(self, limit: int = 20) -> list[WorkflowRun]:
        rows = self._connection.execute(
            "SELECT payload FROM workflow_runs ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [WorkflowRun.model_validate_json(row["payload"]) for row in rows]

    def events(self, run_id: str) -> list[AuditEvent]:
        rows = self._connection.execute(
            "SELECT sequence, kind, actor, payload, created_at FROM audit_events WHERE run_id = ? ORDER BY sequence",
            (run_id,),
        ).fetchall()
        return [
            AuditEvent(
                sequence=row["sequence"],
                kind=row["kind"],
                actor=row["actor"],
                payload=json.loads(row["payload"]),
                created_at=row["created_at"],
            )
            for row in rows
        ]
