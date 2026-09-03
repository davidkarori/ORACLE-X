import json
import sqlite3
import threading
import uuid
from pathlib import Path
from typing import Any, Protocol

from pydantic import ValidationError

from .domain import AuditEvent, LearningMemory, WorkflowRun, utc_now


def _parse_run_payload(payload: Any) -> WorkflowRun | None:
    try:
        if isinstance(payload, str):
            return WorkflowRun.model_validate_json(payload)
        return WorkflowRun.model_validate(payload)
    except ValidationError:
        return None


def _parse_memory_payload(payload: Any) -> LearningMemory | None:
    try:
        if isinstance(payload, str):
            return LearningMemory.model_validate_json(payload)
        return LearningMemory.model_validate(payload)
    except ValidationError:
        return None


class PersistenceStore(Protocol):
    backend_name: str

    def reserve_execution(self, idempotency_key: str, run_id: str) -> bool: ...
    def save_run(self, run: WorkflowRun) -> None: ...
    def append(self, run_id: str, kind: str, actor: str, payload: dict[str, Any]) -> AuditEvent: ...
    def get_run(self, run_id: str) -> WorkflowRun | None: ...
    def list_runs(self, limit: int = 20) -> list[WorkflowRun]: ...
    def events(self, run_id: str) -> list[AuditEvent]: ...
    def save_memory(self, memory: LearningMemory) -> None: ...
    def list_memories(self, symbol: str, limit: int = 10) -> list[LearningMemory]: ...
    def append_system(self, kind: str, actor: str, payload: dict[str, Any]) -> None: ...


class AuditStore:
    backend_name = "sqlite"

    def __init__(self, path: str) -> None:
        self.path = path
        self._lock = threading.Lock()
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")
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
                CREATE TABLE IF NOT EXISTS learning_memories (
                    id TEXT PRIMARY KEY,
                    source_run_id TEXT NOT NULL REFERENCES workflow_runs(id),
                    symbol TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS system_events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    kind TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TRIGGER IF NOT EXISTS audit_events_no_update
                BEFORE UPDATE ON audit_events BEGIN SELECT RAISE(ABORT, 'audit events are append-only'); END;
                CREATE TRIGGER IF NOT EXISTS audit_events_no_delete
                BEFORE DELETE ON audit_events BEGIN SELECT RAISE(ABORT, 'audit events are append-only'); END;
                CREATE TRIGGER IF NOT EXISTS learning_memories_no_update
                BEFORE UPDATE ON learning_memories BEGIN SELECT RAISE(ABORT, 'learning memories are append-only'); END;
                CREATE TRIGGER IF NOT EXISTS learning_memories_no_delete
                BEFORE DELETE ON learning_memories BEGIN SELECT RAISE(ABORT, 'learning memories are append-only'); END;
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
        payload = run.model_dump_json()
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT INTO workflow_runs(id, symbol, state, status, payload, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    state=excluded.state, status=excluded.status, payload=excluded.payload, updated_at=excluded.updated_at
                """,
                (run.id, run.symbol, run.state.value, run.status, payload, run.created_at.isoformat(), run.updated_at.isoformat()),
            )

    def append(self, run_id: str, kind: str, actor: str, payload: dict[str, Any]) -> AuditEvent:
        created_at = utc_now()
        with self._lock, self._connection:
            cursor = self._connection.execute(
                "INSERT INTO audit_events(run_id, kind, actor, payload, created_at) VALUES (?, ?, ?, ?, ?)",
                (run_id, kind, actor, json.dumps(payload, default=str), created_at.isoformat()),
            )
        return AuditEvent(sequence=int(cursor.lastrowid), kind=kind, actor=actor, payload=payload, created_at=created_at)

    def get_run(self, run_id: str) -> WorkflowRun | None:
        row = self._connection.execute("SELECT payload FROM workflow_runs WHERE id = ?", (run_id,)).fetchone()
        return _parse_run_payload(row["payload"]) if row else None

    def list_runs(self, limit: int = 20) -> list[WorkflowRun]:
        rows = self._connection.execute(
            "SELECT payload FROM workflow_runs ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [run for row in rows if (run := _parse_run_payload(row["payload"])) is not None]

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

    def save_memory(self, memory: LearningMemory) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                "INSERT INTO learning_memories(id, source_run_id, symbol, payload, created_at) VALUES (?, ?, ?, ?, ?)",
                (memory.id, memory.source_run_id, memory.symbol, memory.model_dump_json(), memory.created_at.isoformat()),
            )

    def list_memories(self, symbol: str, limit: int = 10) -> list[LearningMemory]:
        rows = self._connection.execute(
            "SELECT payload FROM learning_memories WHERE symbol = ? ORDER BY created_at DESC LIMIT ?",
            (symbol, limit),
        ).fetchall()
        return [memory for row in rows if (memory := _parse_memory_payload(row["payload"])) is not None]

    def append_system(self, kind: str, actor: str, payload: dict[str, Any]) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                "INSERT INTO system_events(kind, actor, payload, created_at) VALUES (?, ?, ?, ?)",
                (kind, actor, json.dumps(payload, default=str), utc_now().isoformat()),
            )


class PostgresAuditStore:
    backend_name = "postgresql"

    def __init__(self, dsn: str) -> None:
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as exc:
            raise RuntimeError("PostgreSQL persistence requires psycopg") from exc
        self._lock = threading.Lock()
        self._connection = psycopg.connect(dsn, row_factory=dict_row)

    def reserve_execution(self, idempotency_key: str, run_id: str) -> bool:
        try:
            with self._lock, self._connection.transaction():
                self._connection.execute(
                    "INSERT INTO execution_intents(idempotency_key, run_id) VALUES (%s, %s)",
                    (idempotency_key, run_id),
                )
            return True
        except Exception as exc:
            if getattr(exc, "sqlstate", None) == "23505":
                return False
            raise

    def save_run(self, run: WorkflowRun) -> None:
        with self._lock, self._connection.transaction():
            self._connection.execute(
                """
                INSERT INTO workflow_runs(id, symbol, state, status, payload, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s)
                ON CONFLICT(id) DO UPDATE SET
                    state=excluded.state, status=excluded.status, payload=excluded.payload, updated_at=excluded.updated_at
                """,
                (run.id, run.symbol, run.state.value, run.status, run.model_dump_json(), run.created_at, run.updated_at),
            )

    def append(self, run_id: str, kind: str, actor: str, payload: dict[str, Any]) -> AuditEvent:
        with self._lock, self._connection.transaction():
            row = self._connection.execute(
                """
                INSERT INTO oracle_events(correlation_id, event_type, entity_type, entity_id, actor, payload)
                VALUES (%s, %s, 'workflow_run', %s, %s, %s::jsonb)
                RETURNING sequence, occurred_at
                """,
                (run_id, kind, run_id, actor, json.dumps(payload, default=str)),
            ).fetchone()
        return AuditEvent(sequence=row["sequence"], kind=kind, actor=actor, payload=payload, created_at=row["occurred_at"])

    def get_run(self, run_id: str) -> WorkflowRun | None:
        row = self._connection.execute("SELECT payload FROM workflow_runs WHERE id = %s", (run_id,)).fetchone()
        return _parse_run_payload(row["payload"]) if row else None

    def list_runs(self, limit: int = 20) -> list[WorkflowRun]:
        rows = self._connection.execute(
            "SELECT payload FROM workflow_runs ORDER BY created_at DESC LIMIT %s", (limit,)
        ).fetchall()
        return [run for row in rows if (run := _parse_run_payload(row["payload"])) is not None]

    def events(self, run_id: str) -> list[AuditEvent]:
        rows = self._connection.execute(
            """
            SELECT sequence, event_type, actor, payload, occurred_at
            FROM oracle_events WHERE correlation_id = %s ORDER BY sequence
            """,
            (run_id,),
        ).fetchall()
        return [
            AuditEvent(sequence=row["sequence"], kind=row["event_type"], actor=row["actor"], payload=row["payload"], created_at=row["occurred_at"])
            for row in rows
        ]

    def save_memory(self, memory: LearningMemory) -> None:
        with self._lock, self._connection.transaction():
            self._connection.execute(
                """
                INSERT INTO oracle_memory(id, memory_type, symbol, source_trade_id, content, confidence, created_at)
                VALUES (%s, 'TRADE_LESSON', %s, NULL, %s::jsonb, %s, %s)
                """,
                (memory.id, memory.symbol, memory.model_dump_json(), memory.confidence, memory.created_at),
            )

    def list_memories(self, symbol: str, limit: int = 10) -> list[LearningMemory]:
        rows = self._connection.execute(
            "SELECT content FROM oracle_memory WHERE symbol = %s ORDER BY created_at DESC LIMIT %s",
            (symbol, limit),
        ).fetchall()
        return [memory for row in rows if (memory := _parse_memory_payload(row["content"])) is not None]

    def append_system(self, kind: str, actor: str, payload: dict[str, Any]) -> None:
        with self._lock, self._connection.transaction():
            self._connection.execute(
                "INSERT INTO kill_switch_events(active, reason, actor) VALUES (%s, %s, %s)",
                (bool(payload.get("active")), str(payload.get("reason", kind)), actor),
            )


def build_store(database_url: str, sqlite_path: str) -> PersistenceStore:
    if database_url.startswith(("postgresql://", "postgres://")):
        return PostgresAuditStore(database_url)
    return AuditStore(sqlite_path)
