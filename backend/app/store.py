import json
import sqlite3
import threading
import uuid
from pathlib import Path
from typing import Any, Protocol

from pydantic import ValidationError

from .domain import AgentDecision, AuditEvent, LearningMemory, RiskEvaluation, SystemState, WorkflowRun, utc_now


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
    def reserve_execution_intent(self, idempotency_key: str, run_id: str, fingerprint: str | None) -> bool: ...
    def save_run(self, run: WorkflowRun) -> None: ...
    def append(self, run_id: str, kind: str, actor: str, payload: dict[str, Any]) -> AuditEvent: ...
    def get_run(self, run_id: str) -> WorkflowRun | None: ...
    def list_runs(self, limit: int = 20) -> list[WorkflowRun]: ...
    def events(self, run_id: str) -> list[AuditEvent]: ...
    def save_memory(self, memory: LearningMemory) -> None: ...
    def list_memories(self, symbol: str, limit: int = 10) -> list[LearningMemory]: ...
    def append_system(self, kind: str, actor: str, payload: dict[str, Any]) -> None: ...
    def get_system_state(self) -> SystemState: ...
    def set_system_state(self, state: SystemState) -> SystemState: ...
    def has_active_execution_conflict(self, fingerprint: str) -> bool: ...
    def save_agent_decision(self, run_id: str, decision: AgentDecision) -> None: ...
    def save_risk_evaluation(self, run_id: str, risk: RiskEvaluation) -> None: ...
    def save_broker_order(self, run_id: str, order: dict[str, Any]) -> None: ...
    def save_reconciliation_event(self, run_id: str, status: str, payload: dict[str, Any]) -> None: ...


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
                    fingerprint TEXT,
                    status TEXT NOT NULL DEFAULT 'RESERVED',
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
                CREATE TABLE IF NOT EXISTS system_state (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    status TEXT NOT NULL CHECK (status IN ('ACTIVE','PAUSED','HALTED')),
                    kill_switch_active INTEGER NOT NULL,
                    changed_by TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS inference_traces (
                    id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL REFERENCES workflow_runs(id),
                    role TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    model TEXT NOT NULL,
                    trace_id TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS risk_evaluations_runtime (
                    id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL REFERENCES workflow_runs(id),
                    decision TEXT NOT NULL,
                    reason_codes TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS broker_orders_runtime (
                    id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL REFERENCES workflow_runs(id),
                    client_order_id TEXT NOT NULL,
                    broker_order_id TEXT,
                    status TEXT NOT NULL,
                    request_payload TEXT NOT NULL,
                    raw_response TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS broker_reconciliation_runtime (
                    id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL REFERENCES workflow_runs(id),
                    status TEXT NOT NULL,
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
            self._connection.execute(
                """
                INSERT OR IGNORE INTO system_state(id, status, kill_switch_active, changed_by, reason, updated_at)
                VALUES (1, 'ACTIVE', 0, 'SYSTEM', 'Initialized', ?)
                """,
                (utc_now().isoformat(),),
            )
            self._ensure_sqlite_column("execution_intents", "fingerprint", "TEXT")
            self._ensure_sqlite_column("execution_intents", "status", "TEXT NOT NULL DEFAULT 'RESERVED'")
            self._connection.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_execution_intents_active_fingerprint
                  ON execution_intents(fingerprint)
                  WHERE fingerprint IS NOT NULL AND status IN ('RESERVED','SUBMITTED','ACCEPTED','NEW','PARTIALLY_FILLED','PENDING_NEW','UNKNOWN')
                """
            )

    def _ensure_sqlite_column(self, table: str, column: str, declaration: str) -> None:
        columns = {row["name"] for row in self._connection.execute(f"PRAGMA table_info({table})").fetchall()}
        if column not in columns:
            self._connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {declaration}")

    def reserve_execution(self, idempotency_key: str, run_id: str) -> bool:
        return self.reserve_execution_intent(idempotency_key, run_id, None)

    def reserve_execution_intent(self, idempotency_key: str, run_id: str, fingerprint: str | None) -> bool:
        try:
            with self._lock, self._connection:
                self._connection.execute(
                    "INSERT INTO execution_intents(idempotency_key, run_id, fingerprint, created_at) VALUES (?, ?, ?, ?)",
                    (idempotency_key, run_id, fingerprint, utc_now().isoformat()),
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

    def get_system_state(self) -> SystemState:
        row = self._connection.execute(
            "SELECT status, kill_switch_active, changed_by, reason, updated_at FROM system_state WHERE id = 1"
        ).fetchone()
        if not row:
            return SystemState()
        return SystemState(
            status=row["status"],
            kill_switch_active=bool(row["kill_switch_active"]),
            changed_by=row["changed_by"],
            reason=row["reason"],
            updated_at=row["updated_at"],
        )

    def set_system_state(self, state: SystemState) -> SystemState:
        with self._lock, self._connection:
            self._connection.execute(
                """
                UPDATE system_state
                SET status = ?, kill_switch_active = ?, changed_by = ?, reason = ?, updated_at = ?
                WHERE id = 1
                """,
                (state.status, int(state.kill_switch_active), state.changed_by, state.reason, state.updated_at.isoformat()),
            )
            self._connection.execute(
                "INSERT INTO system_events(kind, actor, payload, created_at) VALUES (?, ?, ?, ?)",
                ("SYSTEM_STATE_CHANGED", state.changed_by, state.model_dump_json(), utc_now().isoformat()),
            )
        return state

    def has_active_execution_conflict(self, fingerprint: str) -> bool:
        row = self._connection.execute(
            """
            SELECT 1 FROM execution_intents
            WHERE fingerprint = ? AND status IN ('RESERVED','SUBMITTED','ACCEPTED','NEW','PARTIALLY_FILLED','PENDING_NEW','UNKNOWN')
            LIMIT 1
            """,
            (fingerprint,),
        ).fetchone()
        return row is not None

    def save_agent_decision(self, run_id: str, decision: AgentDecision) -> None:
        payload = decision.model_dump(mode="json")
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT INTO inference_traces(id, run_id, role, provider, model, trace_id, payload, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (str(uuid.uuid4()), run_id, decision.role.value, decision.provider, decision.model, decision.trace_id, json.dumps(payload, default=str), utc_now().isoformat()),
            )

    def save_risk_evaluation(self, run_id: str, risk: RiskEvaluation) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT INTO risk_evaluations_runtime(id, run_id, decision, reason_codes, payload, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (str(uuid.uuid4()), run_id, risk.decision, json.dumps(risk.reason_codes), risk.model_dump_json(), utc_now().isoformat()),
            )

    def save_broker_order(self, run_id: str, order: dict[str, Any]) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT INTO broker_orders_runtime(id, run_id, client_order_id, broker_order_id, status, request_payload, raw_response, payload, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    run_id,
                    str(order.get("client_order_id", "")),
                    order.get("order_id"),
                    str(order.get("status", "unknown")),
                    json.dumps(order.get("request_payload", {}), default=str),
                    json.dumps(order.get("raw_response", {}), default=str),
                    json.dumps(order, default=str),
                    utc_now().isoformat(),
                ),
            )

    def save_reconciliation_event(self, run_id: str, status: str, payload: dict[str, Any]) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                "INSERT INTO broker_reconciliation_runtime(id, run_id, status, payload, created_at) VALUES (?, ?, ?, ?, ?)",
                (str(uuid.uuid4()), run_id, status, json.dumps(payload, default=str), utc_now().isoformat()),
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
        return self.reserve_execution_intent(idempotency_key, run_id, None)

    def reserve_execution_intent(self, idempotency_key: str, run_id: str, fingerprint: str | None) -> bool:
        try:
            with self._lock, self._connection.transaction():
                self._connection.execute(
                    "INSERT INTO execution_intents(idempotency_key, run_id, fingerprint) VALUES (%s, %s, %s)",
                    (idempotency_key, run_id, fingerprint),
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
                (bool(payload.get("active") or payload.get("kill_switch_active")), str(payload.get("reason", kind)), actor),
            )

    def get_system_state(self) -> SystemState:
        row = self._connection.execute(
            """
            SELECT state AS status, kill_switch AS kill_switch_active, changed_by, reason, changed_at AS updated_at
            FROM system_state
            ORDER BY changed_at DESC, created_at DESC
            LIMIT 1
            """
        ).fetchone()
        return SystemState.model_validate(row) if row else SystemState()

    def set_system_state(self, state: SystemState) -> SystemState:
        with self._lock, self._connection.transaction():
            self._connection.execute(
                """
                INSERT INTO system_state(state, kill_switch, changed_by, reason, changed_at)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (state.status, state.kill_switch_active, state.changed_by, state.reason, state.updated_at),
            )
        self.append_system("SYSTEM_STATE_CHANGED", state.changed_by, state.model_dump(mode="json"))
        return state

    def has_active_execution_conflict(self, fingerprint: str) -> bool:
        row = self._connection.execute(
            """
            SELECT 1 FROM execution_intents
            WHERE fingerprint = %s AND status IN ('RESERVED','SUBMITTED','ACCEPTED','NEW','PARTIALLY_FILLED','PENDING_NEW','UNKNOWN')
            LIMIT 1
            """,
            (fingerprint,),
        ).fetchone()
        return row is not None

    def save_agent_decision(self, run_id: str, decision: AgentDecision) -> None:
        payload = decision.model_dump(mode="json")
        with self._lock, self._connection.transaction():
            self._connection.execute(
                """
                INSERT INTO inference_traces(id, run_id, role, provider, model, trace_id, request_payload, response_payload, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, '{}'::jsonb, %s::jsonb, now())
                """,
                (str(uuid.uuid4()), run_id, decision.role.value, decision.provider, decision.model, decision.trace_id, json.dumps(payload, default=str)),
            )

    def save_risk_evaluation(self, run_id: str, risk: RiskEvaluation) -> None:
        with self._lock, self._connection.transaction():
            self._connection.execute(
                """
                INSERT INTO risk_evaluations_runtime(id, run_id, decision, reason_codes, payload, created_at)
                VALUES (%s, %s, %s, %s::jsonb, %s::jsonb, now())
                """,
                (str(uuid.uuid4()), run_id, risk.decision, json.dumps(risk.reason_codes), risk.model_dump_json()),
            )

    def save_broker_order(self, run_id: str, order: dict[str, Any]) -> None:
        with self._lock, self._connection.transaction():
            self._connection.execute(
                """
                INSERT INTO broker_orders_runtime(id, run_id, client_order_id, broker_order_id, status, request_payload, raw_response, payload, created_at)
                VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb, now())
                """,
                (
                    str(uuid.uuid4()),
                    run_id,
                    str(order.get("client_order_id", "")),
                    order.get("order_id"),
                    str(order.get("status", "unknown")),
                    json.dumps(order.get("request_payload", {}), default=str),
                    json.dumps(order.get("raw_response", {}), default=str),
                    json.dumps(order, default=str),
                ),
            )

    def save_reconciliation_event(self, run_id: str, status: str, payload: dict[str, Any]) -> None:
        with self._lock, self._connection.transaction():
            self._connection.execute(
                "INSERT INTO broker_reconciliation_runtime(id, run_id, status, payload, created_at) VALUES (%s, %s, %s, %s::jsonb, now())",
                (str(uuid.uuid4()), run_id, status, json.dumps(payload, default=str)),
            )


def build_store(database_url: str, sqlite_path: str) -> PersistenceStore:
    if database_url.startswith(("postgresql://", "postgres://")):
        return PostgresAuditStore(database_url)
    return AuditStore(sqlite_path)
