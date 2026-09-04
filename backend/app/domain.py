from datetime import datetime, timezone
from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AgentRole(StrEnum):
    ATHENA = "ATHENA"
    HADES = "HADES"
    HERMES = "HERMES"
    MORPHEUS = "MORPHEUS"


class Bias(StrEnum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"


class StrategyFamily(StrEnum):
    LONG_CALL = "LONG_CALL"
    LONG_PUT = "LONG_PUT"
    BULL_CALL_SPREAD = "BULL_CALL_SPREAD"
    BEAR_PUT_SPREAD = "BEAR_PUT_SPREAD"
    IRON_CONDOR = "IRON_CONDOR"


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
    POSITION_MONITORING = "POSITION_MONITORING"
    EXIT_SIGNAL = "EXIT_SIGNAL"
    EXIT_EXECUTION = "EXIT_EXECUTION"
    POSITION_CLOSED = "POSITION_CLOSED"
    AUTOPSY = "AUTOPSY"
    LEARNED = "LEARNED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"


class DecisionMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confidence: float = Field(ge=0, le=1)
    evidence_refs: list[str] = Field(default_factory=list)
    provider: str
    model: str
    latency_ms: int = Field(ge=0)
    trace_id: str
    decided_at: datetime = Field(default_factory=utc_now)
    agent_version: str = "committee-v2"
    prompt_version: str = "hardening-v1"


class AthenaDecision(DecisionMetadata):
    role: Literal[AgentRole.ATHENA] = AgentRole.ATHENA
    thesis: str = Field(min_length=10)
    bias: Bias
    assumptions: list[str] = Field(default_factory=list)
    invalidation_conditions: list[str] = Field(default_factory=list)


class HadesDecision(DecisionMetadata):
    role: Literal[AgentRole.HADES] = AgentRole.HADES
    critique: str = Field(min_length=10)
    fatal_objections: list[str] = Field(default_factory=list)
    survivable_objections: list[str] = Field(default_factory=list)
    recommendation: Literal["CONTINUE", "REVISE", "REJECT"]


class HermesDecision(DecisionMetadata):
    role: Literal[AgentRole.HERMES] = AgentRole.HERMES
    preferred_strategy_family: StrategyFamily
    rationale: str = Field(min_length=10)
    directional_intent: Bias
    target_risk_profile: Literal["DEFINED_RISK", "PREMIUM_ONLY"]
    structural_intent: list[str] = Field(default_factory=list)


class MorpheusDecision(DecisionMetadata):
    role: Literal[AgentRole.MORPHEUS] = AgentRole.MORPHEUS
    interpretation: str = Field(min_length=10)
    break_conditions: list[str] = Field(default_factory=list)
    critical_scenarios: list[str] = Field(default_factory=list)
    recommendation: Literal["PASS", "CAUTION", "REJECT"]


AgentDecision = Annotated[
    AthenaDecision | HadesDecision | HermesDecision | MorpheusDecision,
    Field(discriminator="role"),
]


class OptionQuote(BaseModel):
    contract_symbol: str
    underlying_symbol: str
    option_type: Literal["CALL", "PUT"]
    expiration: str
    strike: float = Field(gt=0)
    bid: float = Field(ge=0)
    ask: float = Field(gt=0)
    implied_volatility: float | None = Field(default=None, ge=0)
    delta: float | None = None
    gamma: float | None = None
    theta: float | None = None
    vega: float | None = None
    rho: float | None = None

    @property
    def midpoint(self) -> float:
        return round((self.bid + self.ask) / 2, 4)


class MarketContext(BaseModel):
    symbol: str
    source: str
    observed_at: datetime
    underlying_price: float = Field(gt=0)
    account_status: str
    buying_power: float = Field(ge=0)
    option_chain: list[OptionQuote] = Field(min_length=4)
    raw_refs: list[str] = Field(default_factory=list)


class OptionLeg(BaseModel):
    contract_symbol: str
    underlying_symbol: str
    option_type: Literal["CALL", "PUT"]
    expiration: str
    strike: float = Field(gt=0)
    side: Literal["BUY", "SELL"]
    quantity: int = Field(gt=0)
    ratio: int = Field(gt=0)
    position_intent: Literal["BUY_TO_OPEN", "SELL_TO_OPEN", "BUY_TO_CLOSE", "SELL_TO_CLOSE"]
    bid: float = Field(ge=0)
    ask: float = Field(gt=0)
    midpoint: float = Field(gt=0)
    implied_volatility: float | None = None
    delta: float | None = None
    gamma: float | None = None
    theta: float | None = None
    vega: float | None = None
    rho: float | None = None


class Strategy(BaseModel):
    strategy_type: StrategyFamily
    thesis: str
    directional_intent: Bias
    target_risk_profile: Literal["DEFINED_RISK", "PREMIUM_ONLY"]
    legs: list[OptionLeg] = Field(min_length=1, max_length=4)
    expiration: str
    quantity: int = Field(gt=0)
    net_debit: float = Field(default=0, ge=0)
    net_credit: float = Field(default=0, ge=0)
    max_loss: float = Field(ge=0)
    max_profit: float | None = Field(default=None, ge=0)
    break_even: list[float] = Field(default_factory=list)


class ScenarioPnl(BaseModel):
    label: str
    underlying_price: float = Field(gt=0)
    pnl: float


class QuantMetrics(BaseModel):
    leg_midpoints: list[float]
    max_spread_pct: float = Field(ge=0)
    premium: float = Field(ge=0)
    net_debit: float = Field(ge=0)
    net_credit: float = Field(ge=0)
    max_loss: float = Field(ge=0)
    max_profit: float | None = Field(default=None, ge=0)
    break_even: list[float]
    position_quantity: int = Field(gt=0)
    exposure: float = Field(ge=0)
    reward_risk: float | None = Field(default=None, ge=0)
    scenario_pnl: list[ScenarioPnl]
    data_age_seconds: float = Field(ge=0)
    liquidity_passed: bool
    greeks_status: Literal["AVAILABLE", "PARTIAL", "UNAVAILABLE"]
    service_version: str = "quant-v2"


class StressScenario(BaseModel):
    name: str
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    pnl: float
    breaks_thesis: bool


class StressReport(BaseModel):
    scenarios: list[StressScenario]
    break_conditions: list[str]
    recommendation: Literal["PASS", "CAUTION", "REJECT"]
    service_version: str = "stress-v1"


class McpToolCall(BaseModel):
    id: str
    tool_name: str
    requesting_agent: AgentRole
    arguments: dict[str, Any]
    result_metadata: dict[str, Any]
    latency_ms: int = Field(ge=0)
    success: bool
    error: str | None = None
    called_at: datetime = Field(default_factory=utc_now)


class GateResult(BaseModel):
    code: str
    passed: bool
    measured: Any
    limit: Any | None = None


class RiskEvaluation(BaseModel):
    decision: Literal["APPROVE", "REJECT"]
    reason_codes: list[str]
    gates: list[GateResult]
    policy_version: str = "hardening-v2"
    evaluated_at: datetime
    expires_at: datetime


class ExecutionValidation(BaseModel):
    decision: Literal["PASS", "BLOCK"]
    reason_codes: list[str]
    checks: list[GateResult]
    idempotency_key: str
    strategy_hash: str
    validated_at: datetime


class PositionState(BaseModel):
    status: Literal["OPEN", "MONITORING", "CLOSED"]
    quantity: int = Field(gt=0)
    entry_value: float = Field(ge=0)
    current_value: float = Field(ge=0)
    unrealized_pnl: float = 0
    realized_pnl: float = 0
    opened_at: datetime
    closed_at: datetime | None = None
    simulated: bool = False


class TradeAutopsy(BaseModel):
    id: str
    source_run_id: str
    symbol: str
    original_thesis: str
    hades_objections: list[str]
    strategy_type: StrategyFamily
    stress_recommendation: Literal["PASS", "CAUTION", "REJECT"]
    morpheus_verdict: Literal["PASS", "CAUTION", "REJECT"]
    risk_decision: Literal["APPROVE", "REJECT"]
    execution_outcome: str
    realized_pnl: float
    unrealized_pnl: float
    outcome_summary: str
    what_worked: list[str]
    what_failed: list[str]
    wrong_assumptions: list[str]
    created_at: datetime = Field(default_factory=utc_now)


class LearningMemory(BaseModel):
    id: str
    source_run_id: str
    symbol: str
    lessons: list[str]
    confidence: float = Field(ge=0, le=1)
    advisory_only: Literal[True] = True
    execution_authority: Literal[False] = False
    created_at: datetime = Field(default_factory=utc_now)


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
    simulate_lifecycle: bool
    risk_profile: Literal["CONSERVATIVE", "AGGRESSIVE"]
    created_at: datetime
    updated_at: datetime
    market: MarketContext | None = None
    mcp_calls: list[McpToolCall] = Field(default_factory=list)
    decisions: list[AgentDecision] = Field(default_factory=list)
    strategy: Strategy | None = None
    quant: QuantMetrics | None = None
    stress: StressReport | None = None
    risk: RiskEvaluation | None = None
    execution_guard: ExecutionValidation | None = None
    broker_order: dict[str, Any] | None = None
    position: PositionState | None = None
    autopsy: TradeAutopsy | None = None
    memory: LearningMemory | None = None
    error: str | None = None


class CreateRunRequest(BaseModel):
    symbol: str = "SPY"
    execute: bool = False
    simulate_lifecycle: bool = True
    risk_profile: Literal["CONSERVATIVE", "AGGRESSIVE"] = "CONSERVATIVE"

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        value = value.strip().upper()
        if not value or len(value) > 8 or not value.isalnum():
            raise ValueError("symbol must be 1-8 alphanumeric characters")
        return value
