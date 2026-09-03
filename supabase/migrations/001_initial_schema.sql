BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

DO $$ BEGIN
  CREATE TYPE opportunity_state AS ENUM ('DETECTED','INVESTIGATING','THESIS_CREATED','THESIS_CHALLENGED','STRATEGY_SELECTED','STRESS_TESTED','RISK_EVALUATED','APPROVED','EXECUTION_READY','SUBMITTED','FILLED','FAILED','POSITION_OPEN','POSITION_MONITORING','EXIT_SIGNAL','EXIT_EXECUTION','POSITION_CLOSED','AUTOPSY','LEARNED','REJECTED');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE agent_type AS ENUM ('ATHENA','HADES','HERMES','MORPHEUS');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE agent_status AS ENUM ('PENDING','RUNNING','COMPLETED','FAILED','TIMEOUT');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE decision_type AS ENUM ('THESIS','CRITIQUE','STRATEGY','STRESS_TEST','RISK','EXECUTION','EXIT','LEARNING');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE trade_status AS ENUM ('PROPOSED','APPROVED','EXECUTION_READY','SUBMITTED','PENDING','FILLED','CANCELED','REJECTED','OPEN','CLOSING','CLOSED','FAILED');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE strategy_type AS ENUM ('LONG_CALL','LONG_PUT','CASH_SECURED_PUT','COVERED_CALL','CALL_SPREAD','PUT_SPREAD','BULL_CALL_SPREAD','BEAR_PUT_SPREAD','BULL_PUT_SPREAD','BEAR_CALL_SPREAD','STRADDLE','STRANGLE','IRON_CONDOR','IRON_BUTTERFLY','CUSTOM_MLEG');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

CREATE TABLE IF NOT EXISTS users (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), external_user_id text UNIQUE, email text UNIQUE, display_name text,
  created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS portfolios (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name text NOT NULL DEFAULT 'ORACLE X Paper Portfolio', alpaca_account_id text, base_currency text NOT NULL DEFAULT 'USD',
  equity numeric(20,8), buying_power numeric(20,8), is_active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS risk_policies (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), portfolio_id uuid NOT NULL REFERENCES portfolios(id) ON DELETE CASCADE,
  version text NOT NULL, max_position_notional numeric(20,8), max_portfolio_risk_pct numeric(12,8), max_loss_per_trade numeric(20,8),
  max_open_trades integer, min_reward_risk numeric(12,8), max_bid_ask_spread_pct numeric(12,8), max_contract_quantity integer,
  min_days_to_expiration integer, max_days_to_expiration integer, max_concentration_pct numeric(12,8),
  max_stale_market_data_seconds integer NOT NULL DEFAULT 60, paper_only boolean NOT NULL DEFAULT true, is_active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(), UNIQUE(portfolio_id, version)
);

CREATE TABLE IF NOT EXISTS market_snapshots (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), symbol text NOT NULL, captured_at timestamptz NOT NULL DEFAULT now(),
  price numeric(20,8), bid numeric(20,8), ask numeric(20,8), volume numeric(30,8), volatility numeric(20,10), iv numeric(20,10), rsi numeric(20,10),
  greeks jsonb NOT NULL DEFAULT '{}'::jsonb, indicators jsonb NOT NULL DEFAULT '{}'::jsonb, source text, raw_payload jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS opportunities (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), portfolio_id uuid REFERENCES portfolios(id) ON DELETE SET NULL, symbol text NOT NULL,
  state opportunity_state NOT NULL DEFAULT 'DETECTED', detected_at timestamptz NOT NULL DEFAULT now(),
  current_thesis jsonb NOT NULL DEFAULT '{}'::jsonb, evidence jsonb NOT NULL DEFAULT '[]'::jsonb,
  invalidation_conditions jsonb NOT NULL DEFAULT '[]'::jsonb, confidence numeric(8,6),
  source_snapshot_id uuid REFERENCES market_snapshots(id) ON DELETE SET NULL, correlation_id uuid NOT NULL DEFAULT gen_random_uuid(),
  created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS trades (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), opportunity_id uuid REFERENCES opportunities(id) ON DELETE SET NULL,
  portfolio_id uuid REFERENCES portfolios(id) ON DELETE SET NULL, strategy_type strategy_type, status trade_status NOT NULL DEFAULT 'PROPOSED',
  thesis jsonb NOT NULL DEFAULT '{}'::jsonb, rationale jsonb NOT NULL DEFAULT '{}'::jsonb,
  max_loss numeric(20,8), max_profit numeric(20,8), expected_reward numeric(20,8), reward_risk numeric(20,8),
  entry_price numeric(20,8), exit_price numeric(20,8), quantity integer, approved_at timestamptz, submitted_at timestamptz,
  filled_at timestamptz, closed_at timestamptz, correlation_id uuid NOT NULL DEFAULT gen_random_uuid(),
  created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS agent_decisions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), opportunity_id uuid REFERENCES opportunities(id) ON DELETE CASCADE,
  trade_id uuid REFERENCES trades(id) ON DELETE SET NULL, agent agent_type NOT NULL, status agent_status NOT NULL DEFAULT 'PENDING',
  decision_type decision_type NOT NULL, provider text NOT NULL DEFAULT 'featherless', model text, agent_version text NOT NULL,
  prompt_version text NOT NULL, reasoning_summary text, evidence jsonb NOT NULL DEFAULT '[]'::jsonb,
  risks jsonb NOT NULL DEFAULT '[]'::jsonb, assumptions jsonb NOT NULL DEFAULT '[]'::jsonb,
  invalidation_conditions jsonb NOT NULL DEFAULT '[]'::jsonb, input_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  output_payload jsonb NOT NULL DEFAULT '{}'::jsonb, input_hash text, output_hash text, confidence numeric(8,6), latency_ms integer,
  input_tokens integer, output_tokens integer, created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS inference_traces (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), agent_decision_id uuid REFERENCES agent_decisions(id) ON DELETE SET NULL,
  provider text NOT NULL DEFAULT 'featherless', model text, endpoint text, request_id text, prompt_version text,
  temperature numeric(8,5), request_payload jsonb NOT NULL DEFAULT '{}'::jsonb, response_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  input_hash text, output_hash text, input_tokens integer, output_tokens integer, latency_ms integer, created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS risk_evaluations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), trade_id uuid NOT NULL REFERENCES trades(id) ON DELETE CASCADE,
  policy_id uuid REFERENCES risk_policies(id) ON DELETE SET NULL, policy_version text,
  decision text NOT NULL CHECK (decision IN ('APPROVE','REJECT')), reason_codes jsonb NOT NULL DEFAULT '[]'::jsonb,
  measured_values jsonb NOT NULL DEFAULT '{}'::jsonb, evidence_refs jsonb NOT NULL DEFAULT '[]'::jsonb,
  evaluated_at timestamptz NOT NULL DEFAULT now(), created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS trade_legs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), trade_id uuid NOT NULL REFERENCES trades(id) ON DELETE CASCADE, leg_index integer NOT NULL,
  symbol text NOT NULL, underlying_symbol text NOT NULL, option_type text CHECK (option_type IN ('CALL','PUT') OR option_type IS NULL),
  strike numeric(20,8), expiration date, side text NOT NULL, position_intent text, ratio integer NOT NULL DEFAULT 1, quantity integer NOT NULL DEFAULT 1,
  bid numeric(20,8), ask numeric(20,8), mid numeric(20,8), implied_volatility numeric(20,10), delta numeric(20,10), gamma numeric(20,10),
  theta numeric(20,10), vega numeric(20,10), rho numeric(20,10), created_at timestamptz NOT NULL DEFAULT now(), UNIQUE(trade_id, leg_index)
);

CREATE TABLE IF NOT EXISTS alpaca_orders (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), trade_id uuid REFERENCES trades(id) ON DELETE SET NULL,
  alpaca_order_id text UNIQUE, client_order_id text NOT NULL UNIQUE, order_class text, order_type text, side text, time_in_force text,
  quantity numeric(20,8), limit_price numeric(20,8), stop_price numeric(20,8), status text,
  raw_response jsonb NOT NULL DEFAULT '{}'::jsonb, submitted_at timestamptz, updated_at timestamptz NOT NULL DEFAULT now(), created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS execution_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), trade_id uuid REFERENCES trades(id) ON DELETE SET NULL,
  alpaca_order_id uuid REFERENCES alpaca_orders(id) ON DELETE SET NULL, event_type text NOT NULL, broker_status text,
  payload jsonb NOT NULL DEFAULT '{}'::jsonb, occurred_at timestamptz NOT NULL DEFAULT now(), created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS positions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), portfolio_id uuid NOT NULL REFERENCES portfolios(id) ON DELETE CASCADE,
  trade_id uuid REFERENCES trades(id) ON DELETE SET NULL, symbol text NOT NULL, quantity numeric(20,8) NOT NULL,
  avg_entry_price numeric(20,8), market_price numeric(20,8), market_value numeric(20,8), unrealized_pnl numeric(20,8), realized_pnl numeric(20,8),
  broker_position_id text, reconciled_at timestamptz, created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS oracle_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), correlation_id uuid NOT NULL, event_type text NOT NULL, entity_type text, entity_id uuid,
  from_state text, to_state text, actor text, payload jsonb NOT NULL DEFAULT '{}'::jsonb, evidence_refs jsonb NOT NULL DEFAULT '[]'::jsonb,
  occurred_at timestamptz NOT NULL DEFAULT now(), created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS risk_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), trade_id uuid REFERENCES trades(id) ON DELETE SET NULL, event_type text NOT NULL,
  severity text NOT NULL, reason_code text, payload jsonb NOT NULL DEFAULT '{}'::jsonb, occurred_at timestamptz NOT NULL DEFAULT now(), created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS mcp_tool_calls (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), correlation_id uuid, opportunity_id uuid REFERENCES opportunities(id) ON DELETE SET NULL,
  trade_id uuid REFERENCES trades(id) ON DELETE SET NULL, agent agent_type, tool_name text NOT NULL, status text NOT NULL,
  arguments jsonb NOT NULL DEFAULT '{}'::jsonb, result jsonb NOT NULL DEFAULT '{}'::jsonb, error_message text, latency_ms integer,
  called_at timestamptz NOT NULL DEFAULT now(), created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS trade_autopsies (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), trade_id uuid NOT NULL UNIQUE REFERENCES trades(id) ON DELETE CASCADE,
  outcome text, pnl numeric(20,8), thesis_quality text, strategy_quality text, risk_quality text, execution_quality text,
  what_worked jsonb NOT NULL DEFAULT '[]'::jsonb, what_failed jsonb NOT NULL DEFAULT '[]'::jsonb, lessons jsonb NOT NULL DEFAULT '[]'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS oracle_memory (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), memory_type text NOT NULL, symbol text,
  source_trade_id uuid REFERENCES trades(id) ON DELETE SET NULL, content jsonb NOT NULL DEFAULT '{}'::jsonb,
  confidence numeric(8,6), created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS system_state (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), state text NOT NULL CHECK (state IN ('ACTIVE','PAUSED','HALTED')),
  reason text, kill_switch boolean NOT NULL DEFAULT false, changed_by text, changed_at timestamptz NOT NULL DEFAULT now(), created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_market_snapshots_symbol_time ON market_snapshots(symbol, captured_at DESC);
CREATE INDEX IF NOT EXISTS idx_opportunities_state ON opportunities(state);
CREATE INDEX IF NOT EXISTS idx_opportunities_symbol ON opportunities(symbol);
CREATE INDEX IF NOT EXISTS idx_trades_status ON trades(status);
CREATE INDEX IF NOT EXISTS idx_trades_portfolio ON trades(portfolio_id);
CREATE INDEX IF NOT EXISTS idx_agent_decisions_opportunity ON agent_decisions(opportunity_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_inference_traces_decision ON inference_traces(agent_decision_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_risk_evaluations_trade ON risk_evaluations(trade_id, evaluated_at DESC);
CREATE INDEX IF NOT EXISTS idx_alpaca_orders_client ON alpaca_orders(client_order_id);
CREATE INDEX IF NOT EXISTS idx_execution_events_trade ON execution_events(trade_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_positions_portfolio_symbol ON positions(portfolio_id, symbol);
CREATE INDEX IF NOT EXISTS idx_oracle_events_correlation ON oracle_events(correlation_id, occurred_at);
CREATE INDEX IF NOT EXISTS idx_oracle_events_entity ON oracle_events(entity_type, entity_id, occurred_at);
CREATE INDEX IF NOT EXISTS idx_mcp_tool_calls_correlation ON mcp_tool_calls(correlation_id, called_at);
CREATE INDEX IF NOT EXISTS idx_memory_symbol ON oracle_memory(symbol, created_at DESC);

CREATE OR REPLACE FUNCTION update_updated_at_column() RETURNS TRIGGER AS $$
BEGIN NEW.updated_at = now(); RETURN NEW; END; $$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_users_updated_at ON users;
CREATE TRIGGER trg_users_updated_at BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
DROP TRIGGER IF EXISTS trg_portfolios_updated_at ON portfolios;
CREATE TRIGGER trg_portfolios_updated_at BEFORE UPDATE ON portfolios FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
DROP TRIGGER IF EXISTS trg_risk_policies_updated_at ON risk_policies;
CREATE TRIGGER trg_risk_policies_updated_at BEFORE UPDATE ON risk_policies FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
DROP TRIGGER IF EXISTS trg_opportunities_updated_at ON opportunities;
CREATE TRIGGER trg_opportunities_updated_at BEFORE UPDATE ON opportunities FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
DROP TRIGGER IF EXISTS trg_trades_updated_at ON trades;
CREATE TRIGGER trg_trades_updated_at BEFORE UPDATE ON trades FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
DROP TRIGGER IF EXISTS trg_positions_updated_at ON positions;
CREATE TRIGGER trg_positions_updated_at BEFORE UPDATE ON positions FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
DROP TRIGGER IF EXISTS trg_oracle_memory_updated_at ON oracle_memory;
CREATE TRIGGER trg_oracle_memory_updated_at BEFORE UPDATE ON oracle_memory FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

INSERT INTO system_state (state, reason, kill_switch, changed_by)
SELECT 'ACTIVE', 'Initial ORACLE X system state', false, 'migration'
WHERE NOT EXISTS (SELECT 1 FROM system_state);

COMMIT;
