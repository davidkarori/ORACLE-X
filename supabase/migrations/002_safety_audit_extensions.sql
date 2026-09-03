BEGIN;

ALTER TABLE risk_evaluations
  ADD COLUMN IF NOT EXISTS expires_at timestamptz;

CREATE TABLE IF NOT EXISTS quantitative_calculations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  opportunity_id uuid REFERENCES opportunities(id) ON DELETE CASCADE,
  trade_id uuid REFERENCES trades(id) ON DELETE CASCADE,
  calculation_type text NOT NULL,
  service_name text NOT NULL,
  service_version text NOT NULL,
  inputs jsonb NOT NULL DEFAULT '{}'::jsonb,
  outputs jsonb NOT NULL DEFAULT '{}'::jsonb,
  input_hash text,
  output_hash text,
  data_as_of timestamptz,
  calculated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS execution_validations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  trade_id uuid NOT NULL REFERENCES trades(id) ON DELETE CASCADE,
  risk_evaluation_id uuid NOT NULL REFERENCES risk_evaluations(id) ON DELETE RESTRICT,
  decision text NOT NULL CHECK (decision IN ('PASS', 'BLOCK')),
  reason_codes jsonb NOT NULL DEFAULT '[]'::jsonb,
  checks jsonb NOT NULL DEFAULT '[]'::jsonb,
  strategy_hash text NOT NULL,
  final_order_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  idempotency_key text NOT NULL UNIQUE,
  validated_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE alpaca_orders
  ADD COLUMN IF NOT EXISTS execution_validation_id uuid
  REFERENCES execution_validations(id) ON DELETE RESTRICT;

CREATE TABLE IF NOT EXISTS fills (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  alpaca_order_id uuid NOT NULL REFERENCES alpaca_orders(id) ON DELETE CASCADE,
  broker_fill_id text NOT NULL,
  symbol text NOT NULL,
  quantity numeric(20,8) NOT NULL CHECK (quantity > 0),
  price numeric(20,8) NOT NULL CHECK (price >= 0),
  filled_at timestamptz NOT NULL,
  raw_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(alpaca_order_id, broker_fill_id)
);

CREATE TABLE IF NOT EXISTS position_snapshots (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  position_id uuid NOT NULL REFERENCES positions(id) ON DELETE CASCADE,
  quantity numeric(20,8) NOT NULL,
  market_price numeric(20,8),
  market_value numeric(20,8),
  unrealized_pnl numeric(20,8),
  broker_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  captured_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS broker_reconciliation_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  portfolio_id uuid REFERENCES portfolios(id) ON DELETE SET NULL,
  status text NOT NULL,
  positions_checked integer NOT NULL DEFAULT 0 CHECK (positions_checked >= 0),
  orders_checked integer NOT NULL DEFAULT 0 CHECK (orders_checked >= 0),
  discrepancies jsonb NOT NULL DEFAULT '[]'::jsonb,
  reconciled_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS broker_health_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  healthy boolean NOT NULL,
  latency_ms integer CHECK (latency_ms IS NULL OR latency_ms >= 0),
  details jsonb NOT NULL DEFAULT '{}'::jsonb,
  checked_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS data_health_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  provider text NOT NULL,
  healthy boolean NOT NULL,
  max_age_seconds integer CHECK (max_age_seconds IS NULL OR max_age_seconds >= 0),
  details jsonb NOT NULL DEFAULT '{}'::jsonb,
  checked_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS kill_switch_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  active boolean NOT NULL,
  reason text NOT NULL,
  actor text NOT NULL,
  occurred_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_quant_calculations_trade
  ON quantitative_calculations(trade_id, calculated_at DESC);
CREATE INDEX IF NOT EXISTS idx_execution_validations_trade
  ON execution_validations(trade_id, validated_at DESC);
CREATE INDEX IF NOT EXISTS idx_fills_order
  ON fills(alpaca_order_id, filled_at DESC);
CREATE INDEX IF NOT EXISTS idx_position_snapshots_position
  ON position_snapshots(position_id, captured_at DESC);
CREATE INDEX IF NOT EXISTS idx_reconciliation_time
  ON broker_reconciliation_events(reconciled_at DESC);

CREATE OR REPLACE FUNCTION prevent_audit_mutation() RETURNS TRIGGER AS $$
BEGIN
  RAISE EXCEPTION '% is append-only', TG_TABLE_NAME;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_oracle_events_append_only ON oracle_events;
CREATE TRIGGER trg_oracle_events_append_only
  BEFORE UPDATE OR DELETE ON oracle_events
  FOR EACH ROW EXECUTE FUNCTION prevent_audit_mutation();

DROP TRIGGER IF EXISTS trg_risk_events_append_only ON risk_events;
CREATE TRIGGER trg_risk_events_append_only
  BEFORE UPDATE OR DELETE ON risk_events
  FOR EACH ROW EXECUTE FUNCTION prevent_audit_mutation();

DROP TRIGGER IF EXISTS trg_execution_events_append_only ON execution_events;
CREATE TRIGGER trg_execution_events_append_only
  BEFORE UPDATE OR DELETE ON execution_events
  FOR EACH ROW EXECUTE FUNCTION prevent_audit_mutation();

COMMIT;
