-- ORACLE X initial schema
-- Durable source of truth for opportunities, agents, deterministic controls,
-- broker execution, audit replay, and learning.

create extension if not exists pgcrypto;
create extension if not exists vector;

create type agent_role as enum (
  'ATHENA',
  'HADES',
  'HERMES',
  'MORPHEUS',
  'SYSTEM',
  'OPERATOR'
);

create type opportunity_state as enum (
  'DETECTED',
  'INVESTIGATING',
  'THESIS_CREATED',
  'THESIS_CHALLENGED',
  'STRATEGY_SELECTED',
  'STRESS_TESTED',
  'RISK_EVALUATED',
  'APPROVED',
  'EXECUTION_READY',
  'SUBMITTED',
  'FILLED',
  'POSITION_OPEN',
  'POSITION_MONITORING',
  'EXIT_SIGNAL',
  'EXIT_EXECUTION',
  'POSITION_CLOSED',
  'AUTOPSY',
  'LEARNED',
  'REJECTED_BY_HADES',
  'REJECTED_BY_RISK',
  'REJECTED_BY_EXECUTION_GUARD',
  'DATA_STALE',
  'BROKER_UNAVAILABLE',
  'KILL_SWITCH_ACTIVE',
  'EXECUTION_FAILED',
  'CANCELLED',
  'EXPIRED'
);

create type trade_asset_class as enum (
  'EQUITY',
  'OPTION',
  'CRYPTO',
  'CASH'
);

create type option_type as enum (
  'CALL',
  'PUT'
);

create type leg_side as enum (
  'BUY',
  'SELL'
);

create type strategy_kind as enum (
  'LONG_EQUITY',
  'SHORT_EQUITY',
  'LONG_CALL',
  'LONG_PUT',
  'VERTICAL_SPREAD',
  'STRADDLE',
  'STRANGLE',
  'IRON_CONDOR',
  'DEFINED_RISK_COMBINATION',
  'CUSTOM'
);

create type risk_decision as enum (
  'APPROVED',
  'REJECTED',
  'NEEDS_MORE_DATA',
  'SYSTEM_BLOCKED'
);

create type execution_guard_decision as enum (
  'PASSED',
  'FAILED',
  'BLOCKED'
);

create type broker_order_status as enum (
  'CREATED',
  'SUBMITTED',
  'ACCEPTED',
  'PARTIALLY_FILLED',
  'FILLED',
  'CANCELLED',
  'REJECTED',
  'EXPIRED',
  'FAILED'
);

create type trading_mode as enum (
  'PAPER',
  'LIVE'
);

create type audit_event_kind as enum (
  'STATE_TRANSITION',
  'STATE_TRANSITION_REJECTED',
  'AGENT_DECISION',
  'INFERENCE_TRACE',
  'MCP_CALL',
  'QUANT_CALCULATION',
  'RISK_EVALUATION',
  'EXECUTION_VALIDATION',
  'BROKER_ORDER',
  'BROKER_FILL',
  'POSITION_EVENT',
  'AUTOPSY',
  'MEMORY',
  'SYSTEM_STATE',
  'KILL_SWITCH',
  'SECURITY'
);

create table agents (
  id uuid primary key default gen_random_uuid(),
  role agent_role not null,
  name text not null,
  description text,
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  unique (role, name)
);

create table opportunities (
  id uuid primary key default gen_random_uuid(),
  symbol text not null,
  title text not null,
  description text,
  state opportunity_state not null default 'DETECTED',
  detected_by agent_role not null default 'SYSTEM',
  detection_source text,
  confidence numeric(6, 5),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  closed_at timestamptz,
  constraint opportunities_confidence_range check (
    confidence is null or (confidence >= 0 and confidence <= 1)
  )
);

create table lifecycle_transitions (
  id uuid primary key default gen_random_uuid(),
  opportunity_id uuid not null references opportunities(id) on delete cascade,
  previous_state opportunity_state,
  new_state opportunity_state not null,
  actor_role agent_role not null,
  actor_name text,
  reason text not null,
  validation_result jsonb not null default '{}'::jsonb,
  evidence_refs jsonb not null default '[]'::jsonb,
  idempotency_key text,
  rejected boolean not null default false,
  created_at timestamptz not null default now(),
  unique (opportunity_id, idempotency_key)
);

create table audit_events (
  id uuid primary key default gen_random_uuid(),
  event_kind audit_event_kind not null,
  opportunity_id uuid references opportunities(id) on delete set null,
  actor_role agent_role not null default 'SYSTEM',
  actor_name text,
  subject_table text,
  subject_id uuid,
  idempotency_key text,
  payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  unique (event_kind, idempotency_key)
);

create table market_evidence (
  id uuid primary key default gen_random_uuid(),
  opportunity_id uuid not null references opportunities(id) on delete cascade,
  source text not null,
  symbol text not null,
  observed_at timestamptz not null,
  freshness_seconds integer,
  summary text,
  evidence jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  constraint market_evidence_freshness_nonnegative check (
    freshness_seconds is null or freshness_seconds >= 0
  )
);

create table agent_decisions (
  id uuid primary key default gen_random_uuid(),
  opportunity_id uuid references opportunities(id) on delete cascade,
  agent_id uuid references agents(id) on delete set null,
  role agent_role not null,
  decision_type text not null,
  decision text not null,
  rationale text,
  confidence numeric(6, 5),
  evidence_refs jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now(),
  constraint agent_decisions_confidence_range check (
    confidence is null or (confidence >= 0 and confidence <= 1)
  )
);

create table inference_traces (
  id uuid primary key default gen_random_uuid(),
  opportunity_id uuid references opportunities(id) on delete set null,
  agent_decision_id uuid references agent_decisions(id) on delete set null,
  provider text not null default 'featherless',
  model text not null,
  request_hash text not null,
  request_payload jsonb not null default '{}'::jsonb,
  response_payload jsonb,
  finish_reason text,
  prompt_tokens integer,
  completion_tokens integer,
  total_tokens integer,
  latency_ms integer,
  error_code text,
  error_message text,
  created_at timestamptz not null default now(),
  constraint inference_trace_token_counts_nonnegative check (
    (prompt_tokens is null or prompt_tokens >= 0)
    and (completion_tokens is null or completion_tokens >= 0)
    and (total_tokens is null or total_tokens >= 0)
  ),
  constraint inference_trace_latency_nonnegative check (
    latency_ms is null or latency_ms >= 0
  )
);

create table mcp_calls (
  id uuid primary key default gen_random_uuid(),
  opportunity_id uuid references opportunities(id) on delete set null,
  actor_role agent_role not null,
  server_name text not null,
  tool_name text not null,
  purpose text not null,
  request_metadata jsonb not null default '{}'::jsonb,
  response_metadata jsonb,
  success boolean not null,
  latency_ms integer,
  error_code text,
  error_message text,
  created_at timestamptz not null default now(),
  constraint mcp_calls_latency_nonnegative check (
    latency_ms is null or latency_ms >= 0
  )
);

create table quantitative_calculations (
  id uuid primary key default gen_random_uuid(),
  opportunity_id uuid references opportunities(id) on delete cascade,
  calculation_type text not null,
  service_name text not null,
  service_version text,
  inputs jsonb not null default '{}'::jsonb,
  outputs jsonb not null default '{}'::jsonb,
  data_as_of timestamptz,
  created_at timestamptz not null default now()
);

create table options_contracts (
  id uuid primary key default gen_random_uuid(),
  underlying_symbol text not null,
  contract_symbol text not null unique,
  option_type option_type not null,
  expiration_date date not null,
  strike numeric(18, 6) not null,
  multiplier integer not null default 100,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  constraint options_contracts_strike_positive check (strike > 0),
  constraint options_contracts_multiplier_positive check (multiplier > 0)
);

create table strategies (
  id uuid primary key default gen_random_uuid(),
  opportunity_id uuid not null references opportunities(id) on delete cascade,
  strategy_kind strategy_kind not null,
  name text not null,
  thesis text,
  position_intent text not null,
  net_debit_credit numeric(18, 6),
  max_profit numeric(18, 6),
  max_loss numeric(18, 6),
  reward_risk numeric(18, 6),
  break_even jsonb not null default '[]'::jsonb,
  status text not null default 'PROPOSED',
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint strategies_max_loss_nonnegative check (
    max_loss is null or max_loss >= 0
  )
);

create table trade_legs (
  id uuid primary key default gen_random_uuid(),
  strategy_id uuid not null references strategies(id) on delete cascade,
  asset_class trade_asset_class not null,
  symbol text not null,
  option_contract_id uuid references options_contracts(id) on delete restrict,
  side leg_side not null,
  quantity numeric(18, 6) not null,
  ratio numeric(18, 6) not null default 1,
  limit_price numeric(18, 6),
  greeks jsonb not null default '{}'::jsonb,
  implied_volatility numeric(18, 8),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  constraint trade_legs_quantity_positive check (quantity > 0),
  constraint trade_legs_ratio_positive check (ratio > 0),
  constraint trade_legs_limit_price_nonnegative check (
    limit_price is null or limit_price >= 0
  ),
  constraint trade_legs_iv_nonnegative check (
    implied_volatility is null or implied_volatility >= 0
  ),
  constraint trade_legs_option_contract_required check (
    (asset_class = 'OPTION' and option_contract_id is not null)
    or (asset_class <> 'OPTION' and option_contract_id is null)
  )
);

create table risk_evaluations (
  id uuid primary key default gen_random_uuid(),
  opportunity_id uuid not null references opportunities(id) on delete cascade,
  strategy_id uuid references strategies(id) on delete set null,
  decision risk_decision not null,
  risk_governor_version text not null,
  evaluated_inputs jsonb not null default '{}'::jsonb,
  checks jsonb not null default '[]'::jsonb,
  hard_limits jsonb not null default '{}'::jsonb,
  portfolio_exposure jsonb not null default '{}'::jsonb,
  max_loss numeric(18, 6),
  position_size numeric(18, 6),
  rejection_reasons jsonb not null default '[]'::jsonb,
  expires_at timestamptz,
  created_at timestamptz not null default now(),
  constraint risk_evaluations_max_loss_nonnegative check (
    max_loss is null or max_loss >= 0
  )
);

create table execution_validations (
  id uuid primary key default gen_random_uuid(),
  opportunity_id uuid not null references opportunities(id) on delete cascade,
  strategy_id uuid references strategies(id) on delete set null,
  risk_evaluation_id uuid references risk_evaluations(id) on delete restrict,
  decision execution_guard_decision not null,
  execution_guard_version text not null,
  checks jsonb not null default '[]'::jsonb,
  final_order_payload jsonb not null default '{}'::jsonb,
  idempotency_key text not null unique,
  rejection_reasons jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now()
);

create table broker_orders (
  id uuid primary key default gen_random_uuid(),
  opportunity_id uuid not null references opportunities(id) on delete restrict,
  strategy_id uuid references strategies(id) on delete restrict,
  execution_validation_id uuid not null references execution_validations(id) on delete restrict,
  trading_mode trading_mode not null default 'PAPER',
  broker text not null default 'alpaca',
  broker_order_id text,
  client_order_id text not null unique,
  status broker_order_status not null default 'CREATED',
  order_payload jsonb not null default '{}'::jsonb,
  response_payload jsonb,
  submitted_at timestamptz,
  updated_at timestamptz not null default now(),
  created_at timestamptz not null default now()
);

create table broker_order_legs (
  id uuid primary key default gen_random_uuid(),
  broker_order_id uuid not null references broker_orders(id) on delete cascade,
  trade_leg_id uuid references trade_legs(id) on delete restrict,
  broker_leg_id text,
  symbol text not null,
  side leg_side not null,
  quantity numeric(18, 6) not null,
  filled_quantity numeric(18, 6) not null default 0,
  average_fill_price numeric(18, 6),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  constraint broker_order_legs_quantity_positive check (quantity > 0),
  constraint broker_order_legs_filled_quantity_nonnegative check (filled_quantity >= 0),
  constraint broker_order_legs_avg_price_nonnegative check (
    average_fill_price is null or average_fill_price >= 0
  )
);

create table fills (
  id uuid primary key default gen_random_uuid(),
  broker_order_id uuid not null references broker_orders(id) on delete cascade,
  broker_order_leg_id uuid references broker_order_legs(id) on delete set null,
  broker_fill_id text,
  symbol text not null,
  side leg_side not null,
  quantity numeric(18, 6) not null,
  price numeric(18, 6) not null,
  filled_at timestamptz not null,
  raw_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  constraint fills_quantity_positive check (quantity > 0),
  constraint fills_price_nonnegative check (price >= 0),
  unique (broker_order_id, broker_fill_id)
);

create table positions (
  id uuid primary key default gen_random_uuid(),
  opportunity_id uuid references opportunities(id) on delete set null,
  strategy_id uuid references strategies(id) on delete set null,
  broker text not null default 'alpaca',
  trading_mode trading_mode not null default 'PAPER',
  symbol text not null,
  asset_class trade_asset_class not null,
  quantity numeric(18, 6) not null,
  average_entry_price numeric(18, 6),
  opened_at timestamptz not null default now(),
  closed_at timestamptz,
  realized_pnl numeric(18, 6),
  unrealized_pnl numeric(18, 6),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table position_snapshots (
  id uuid primary key default gen_random_uuid(),
  position_id uuid not null references positions(id) on delete cascade,
  quantity numeric(18, 6) not null,
  market_value numeric(18, 6),
  unrealized_pnl numeric(18, 6),
  greeks jsonb not null default '{}'::jsonb,
  broker_payload jsonb not null default '{}'::jsonb,
  captured_at timestamptz not null default now()
);

create table broker_reconciliation_events (
  id uuid primary key default gen_random_uuid(),
  broker text not null default 'alpaca',
  trading_mode trading_mode not null default 'PAPER',
  status text not null,
  positions_checked integer not null default 0,
  orders_checked integer not null default 0,
  discrepancies jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now(),
  constraint broker_recon_counts_nonnegative check (
    positions_checked >= 0 and orders_checked >= 0
  )
);

create table system_state (
  key text primary key,
  value jsonb not null default '{}'::jsonb,
  updated_by agent_role not null default 'SYSTEM',
  updated_at timestamptz not null default now()
);

create table kill_switch_events (
  id uuid primary key default gen_random_uuid(),
  active boolean not null,
  reason text not null,
  actor_role agent_role not null,
  actor_name text,
  created_at timestamptz not null default now()
);

create table broker_health_events (
  id uuid primary key default gen_random_uuid(),
  broker text not null default 'alpaca',
  trading_mode trading_mode not null default 'PAPER',
  healthy boolean not null,
  latency_ms integer,
  details jsonb not null default '{}'::jsonb,
  checked_at timestamptz not null default now(),
  constraint broker_health_latency_nonnegative check (
    latency_ms is null or latency_ms >= 0
  )
);

create table data_health_events (
  id uuid primary key default gen_random_uuid(),
  provider text not null,
  healthy boolean not null,
  max_age_seconds integer,
  details jsonb not null default '{}'::jsonb,
  checked_at timestamptz not null default now(),
  constraint data_health_age_nonnegative check (
    max_age_seconds is null or max_age_seconds >= 0
  )
);

create table autopsies (
  id uuid primary key default gen_random_uuid(),
  opportunity_id uuid not null references opportunities(id) on delete cascade,
  position_id uuid references positions(id) on delete set null,
  author_role agent_role not null default 'MORPHEUS',
  outcome_summary text not null,
  thesis_review text,
  risk_review text,
  execution_review text,
  lessons jsonb not null default '[]'::jsonb,
  metrics jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table memory_records (
  id uuid primary key default gen_random_uuid(),
  source_autopsy_id uuid references autopsies(id) on delete set null,
  opportunity_id uuid references opportunities(id) on delete set null,
  memory_type text not null,
  content text not null,
  embedding vector,
  tags jsonb not null default '[]'::jsonb,
  confidence numeric(6, 5),
  created_at timestamptz not null default now(),
  constraint memory_records_confidence_range check (
    confidence is null or (confidence >= 0 and confidence <= 1)
  )
);

create index idx_opportunities_state on opportunities(state);
create index idx_opportunities_symbol on opportunities(symbol);
create index idx_lifecycle_transitions_opportunity_created on lifecycle_transitions(opportunity_id, created_at);
create index idx_audit_events_opportunity_created on audit_events(opportunity_id, created_at);
create index idx_audit_events_kind_created on audit_events(event_kind, created_at);
create index idx_market_evidence_opportunity on market_evidence(opportunity_id);
create index idx_agent_decisions_opportunity on agent_decisions(opportunity_id);
create index idx_inference_traces_opportunity on inference_traces(opportunity_id);
create index idx_mcp_calls_opportunity on mcp_calls(opportunity_id);
create index idx_quant_calculations_opportunity_type on quantitative_calculations(opportunity_id, calculation_type);
create index idx_options_contracts_underlying_expiration on options_contracts(underlying_symbol, expiration_date);
create index idx_strategies_opportunity on strategies(opportunity_id);
create index idx_trade_legs_strategy on trade_legs(strategy_id);
create index idx_risk_evaluations_opportunity_created on risk_evaluations(opportunity_id, created_at);
create index idx_execution_validations_opportunity_created on execution_validations(opportunity_id, created_at);
create index idx_broker_orders_opportunity on broker_orders(opportunity_id);
create index idx_broker_orders_status on broker_orders(status);
create index idx_broker_orders_broker_order_id on broker_orders(broker_order_id);
create index idx_fills_order on fills(broker_order_id);
create index idx_positions_symbol on positions(symbol);
create index idx_positions_opportunity on positions(opportunity_id);
create index idx_position_snapshots_position_captured on position_snapshots(position_id, captured_at);
create index idx_autopsies_opportunity on autopsies(opportunity_id);
create index idx_memory_records_opportunity on memory_records(opportunity_id);

create or replace function set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create trigger set_opportunities_updated_at
before update on opportunities
for each row execute function set_updated_at();

create trigger set_strategies_updated_at
before update on strategies
for each row execute function set_updated_at();

create trigger set_broker_orders_updated_at
before update on broker_orders
for each row execute function set_updated_at();

create trigger set_positions_updated_at
before update on positions
for each row execute function set_updated_at();

create or replace function prevent_audit_event_update()
returns trigger
language plpgsql
as $$
begin
  raise exception 'audit_events are append-only';
end;
$$;

create trigger audit_events_append_only_update
before update on audit_events
for each row execute function prevent_audit_event_update();

create trigger audit_events_append_only_delete
before delete on audit_events
for each row execute function prevent_audit_event_update();

alter table agents enable row level security;
alter table opportunities enable row level security;
alter table lifecycle_transitions enable row level security;
alter table audit_events enable row level security;
alter table market_evidence enable row level security;
alter table agent_decisions enable row level security;
alter table inference_traces enable row level security;
alter table mcp_calls enable row level security;
alter table quantitative_calculations enable row level security;
alter table options_contracts enable row level security;
alter table strategies enable row level security;
alter table trade_legs enable row level security;
alter table risk_evaluations enable row level security;
alter table execution_validations enable row level security;
alter table broker_orders enable row level security;
alter table broker_order_legs enable row level security;
alter table fills enable row level security;
alter table positions enable row level security;
alter table position_snapshots enable row level security;
alter table broker_reconciliation_events enable row level security;
alter table system_state enable row level security;
alter table kill_switch_events enable row level security;
alter table broker_health_events enable row level security;
alter table data_health_events enable row level security;
alter table autopsies enable row level security;
alter table memory_records enable row level security;
