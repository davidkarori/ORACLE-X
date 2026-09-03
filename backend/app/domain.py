from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AgentRole(StrEnum):
    ATHENA = "ATHENA"
    HADES = "HADES"
    HERMES = "HERMES"
    MORPHEUS = "MORPHEUS"


class LifecycleState(StrEnum):
    DETECTED = "DETECTED"
    INVESTIGATING = "INVESTIGATING"
    THESIS_CREATED = "THESIS_CREATED"
    THESIS_CHALLENGED = "THESIS_CHALLENGED"
    STRATEGY_SELECTED = "STRATEGY_SELECTED"
    STRESS_TESTED = "STRESS_TESTED"
    RISK_EVALUATED = "RISK_EVALUATED"
    APPROVED = "APPROVED"
    EXECUTION_READY = "EXECUTION_READY"
    SUBMITTED = "SUBMITTED"
    FILLED = "FILLED"
    POSITION_OPEN = "POSITION_OPEN"
    REJECTED = "REJECTED"
    FAILED = "FAILED"


class AgentDecision(BaseModel):
    role: AgentRole
    decision: str
    confidence: float = Field(ge=0, le=1)
    summary: str
    evidence_refs: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    invalidation_conditions: list[str] = Field(default_factory=list)
    provider: str
    model: str
    latency_ms: int = Field(ge=0)
    trace_id: str


class MarketContext(BaseModel):
    symbol: str
    source: str
    observed_at: datetime
    underlying_price: float = Field(gt=0)
    option_symbol: str
    option_type: str = "CALL"
    strike: float = Field(gt=0)
    expiration: str
    bid: float = Field(ge=0)
    ask: float = Field(gt=0)
    account_status: str
    buying_power: float = Field(ge=0)
    raw_refs: list[str] = Field(default_factory=list)


class OptionLeg(BaseModel):
    contract_symbol: str
    underlying_symbol: str
    option_type: str
    expiration: str
    strike: float
    side: str
    quantity: int = Field(gt=0)
    ratio: int = Field(gt=0)
    position_intent: str
    limit_price: float = Field(gt=0)


class Strategy(BaseModel):
    strategy_type: str = "LONG_CALL"
    thesis: str
    legs: list[OptionLeg]
    net_debit: float
    max_loss: float
    max_profit: str = "UNBOUNDED"
    break_even: list[float]


class QuantMetrics(BaseModel):
    midpoint: float
    spread_pct: float
    premium: float
    max_loss: float
    position_quantity: int
    data_age_seconds: float
    service_version: str = "quant-v1"


class GateResult(BaseModel):
    code: str
    passed: bool
    measured: Any
    limit: Any | None = None


class RiskEvaluation(BaseModel):
    decision: str
    reason_codes: list[str]
    gates: list[GateResult]
    policy_version: str = "hackathon-v1"
    evaluated_at: datetime
    expires_at: datetime


class ExecutionValidation(BaseModel):
    decision: str
    reason_codes: list[str]
    checks: list[GateResult]
    idempotency_key: str
    validated_at: datetime


class AuditEvent(BaseModel):
    sequence: int
    kind: str
    actor: str
    payload: dict[str, Any]
    created_at: datetime


class WorkflowRun(BaseModel):
    id: str
    symbol: str
    state: LifecycleState
    status: str
    mode: str
    execute_requested: bool
    created_at: datetime
    updated_at: datetime
    market: MarketContext | None = None
    decisions: list[AgentDecision] = Field(default_factory=list)
    strategy: Strategy | None = None
    quant: QuantMetrics | None = None
    risk: RiskEvaluation | None = None
    execution_guard: ExecutionValidation | None = None
    broker_order: dict[str, Any] | None = None
    error: str | None = None


class CreateRunRequest(BaseModel):
    symbol: str = "SPY"
    execute: bool = False

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        value = value.strip().upper()
        if not value or len(value) > 8 or not value.isalnum():
            raise ValueError("symbol must be 1-8 alphanumeric characters")
        return value
