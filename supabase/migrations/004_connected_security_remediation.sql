BEGIN;

ALTER TABLE execution_intents
  ADD COLUMN IF NOT EXISTS fingerprint text,
  ADD COLUMN IF NOT EXISTS status text NOT NULL DEFAULT 'RESERVED';

CREATE UNIQUE INDEX IF NOT EXISTS idx_execution_intents_active_fingerprint
  ON execution_intents(fingerprint)
  WHERE fingerprint IS NOT NULL
    AND status IN ('RESERVED','SUBMITTED','ACCEPTED','NEW','PARTIALLY_FILLED','PENDING_NEW','UNKNOWN');

ALTER TABLE inference_traces
  ADD COLUMN IF NOT EXISTS run_id uuid REFERENCES workflow_runs(id) ON DELETE CASCADE,
  ADD COLUMN IF NOT EXISTS role text,
  ADD COLUMN IF NOT EXISTS trace_id text;

CREATE TABLE IF NOT EXISTS risk_evaluations_runtime (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  run_id uuid NOT NULL REFERENCES workflow_runs(id) ON DELETE CASCADE,
  decision text NOT NULL CHECK (decision IN ('APPROVE','REJECT')),
  reason_codes jsonb NOT NULL DEFAULT '[]'::jsonb,
  payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS broker_orders_runtime (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  run_id uuid NOT NULL REFERENCES workflow_runs(id) ON DELETE CASCADE,
  client_order_id text NOT NULL,
  broker_order_id text,
  status text NOT NULL,
  request_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  raw_response jsonb NOT NULL DEFAULT '{}'::jsonb,
  payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS broker_reconciliation_runtime (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  run_id uuid NOT NULL REFERENCES workflow_runs(id) ON DELETE CASCADE,
  status text NOT NULL,
  payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_broker_orders_runtime_run
  ON broker_orders_runtime(run_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_broker_orders_runtime_client
  ON broker_orders_runtime(client_order_id);
CREATE INDEX IF NOT EXISTS idx_broker_reconciliation_runtime_run
  ON broker_reconciliation_runtime(run_id, created_at DESC);

DO $$ BEGIN
  CREATE TYPE oracle_api_role AS ENUM ('read','operator','admin');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

REVOKE ALL ON ALL TABLES IN SCHEMA public FROM anon;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM anon;
REVOKE INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public FROM authenticated;

ALTER TABLE workflow_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE oracle_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE execution_intents ENABLE ROW LEVEL SECURITY;
ALTER TABLE inference_traces ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_decisions ENABLE ROW LEVEL SECURITY;
ALTER TABLE risk_evaluations ENABLE ROW LEVEL SECURITY;
ALTER TABLE risk_evaluations_runtime ENABLE ROW LEVEL SECURITY;
ALTER TABLE alpaca_orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE broker_orders_runtime ENABLE ROW LEVEL SECURITY;
ALTER TABLE broker_reconciliation_runtime ENABLE ROW LEVEL SECURITY;
ALTER TABLE execution_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE fills ENABLE ROW LEVEL SECURITY;
ALTER TABLE positions ENABLE ROW LEVEL SECURITY;
ALTER TABLE position_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE oracle_memory ENABLE ROW LEVEL SECURITY;
ALTER TABLE system_state ENABLE ROW LEVEL SECURITY;
ALTER TABLE kill_switch_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE mcp_tool_calls ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "runtime service role owns workflow_runs" ON workflow_runs;
CREATE POLICY "runtime service role owns workflow_runs" ON workflow_runs
  FOR ALL USING (auth.role() = 'service_role') WITH CHECK (auth.role() = 'service_role');

DROP POLICY IF EXISTS "runtime service role owns oracle_events" ON oracle_events;
CREATE POLICY "runtime service role owns oracle_events" ON oracle_events
  FOR ALL USING (auth.role() = 'service_role') WITH CHECK (auth.role() = 'service_role');

DROP POLICY IF EXISTS "runtime service role owns execution_intents" ON execution_intents;
CREATE POLICY "runtime service role owns execution_intents" ON execution_intents
  FOR ALL USING (auth.role() = 'service_role') WITH CHECK (auth.role() = 'service_role');

DROP POLICY IF EXISTS "runtime service role owns inference_traces" ON inference_traces;
CREATE POLICY "runtime service role owns inference_traces" ON inference_traces
  FOR ALL USING (auth.role() = 'service_role') WITH CHECK (auth.role() = 'service_role');

DROP POLICY IF EXISTS "runtime service role owns agent_decisions" ON agent_decisions;
CREATE POLICY "runtime service role owns agent_decisions" ON agent_decisions
  FOR ALL USING (auth.role() = 'service_role') WITH CHECK (auth.role() = 'service_role');

DROP POLICY IF EXISTS "runtime service role owns risk_evaluations" ON risk_evaluations;
CREATE POLICY "runtime service role owns risk_evaluations" ON risk_evaluations
  FOR ALL USING (auth.role() = 'service_role') WITH CHECK (auth.role() = 'service_role');

DROP POLICY IF EXISTS "runtime service role owns risk_evaluations_runtime" ON risk_evaluations_runtime;
CREATE POLICY "runtime service role owns risk_evaluations_runtime" ON risk_evaluations_runtime
  FOR ALL USING (auth.role() = 'service_role') WITH CHECK (auth.role() = 'service_role');

DROP POLICY IF EXISTS "runtime service role owns alpaca_orders" ON alpaca_orders;
CREATE POLICY "runtime service role owns alpaca_orders" ON alpaca_orders
  FOR ALL USING (auth.role() = 'service_role') WITH CHECK (auth.role() = 'service_role');

DROP POLICY IF EXISTS "runtime service role owns broker_orders_runtime" ON broker_orders_runtime;
CREATE POLICY "runtime service role owns broker_orders_runtime" ON broker_orders_runtime
  FOR ALL USING (auth.role() = 'service_role') WITH CHECK (auth.role() = 'service_role');

DROP POLICY IF EXISTS "runtime service role owns broker_reconciliation_runtime" ON broker_reconciliation_runtime;
CREATE POLICY "runtime service role owns broker_reconciliation_runtime" ON broker_reconciliation_runtime
  FOR ALL USING (auth.role() = 'service_role') WITH CHECK (auth.role() = 'service_role');

DROP POLICY IF EXISTS "runtime service role owns execution_events" ON execution_events;
CREATE POLICY "runtime service role owns execution_events" ON execution_events
  FOR ALL USING (auth.role() = 'service_role') WITH CHECK (auth.role() = 'service_role');

DROP POLICY IF EXISTS "runtime service role owns fills" ON fills;
CREATE POLICY "runtime service role owns fills" ON fills
  FOR ALL USING (auth.role() = 'service_role') WITH CHECK (auth.role() = 'service_role');

DROP POLICY IF EXISTS "runtime service role owns positions" ON positions;
CREATE POLICY "runtime service role owns positions" ON positions
  FOR ALL USING (auth.role() = 'service_role') WITH CHECK (auth.role() = 'service_role');

DROP POLICY IF EXISTS "runtime service role owns position_snapshots" ON position_snapshots;
CREATE POLICY "runtime service role owns position_snapshots" ON position_snapshots
  FOR ALL USING (auth.role() = 'service_role') WITH CHECK (auth.role() = 'service_role');

DROP POLICY IF EXISTS "runtime service role owns oracle_memory" ON oracle_memory;
CREATE POLICY "runtime service role owns oracle_memory" ON oracle_memory
  FOR ALL USING (auth.role() = 'service_role') WITH CHECK (auth.role() = 'service_role');

DROP POLICY IF EXISTS "runtime service role owns system_state" ON system_state;
CREATE POLICY "runtime service role owns system_state" ON system_state
  FOR ALL USING (auth.role() = 'service_role') WITH CHECK (auth.role() = 'service_role');

DROP POLICY IF EXISTS "runtime service role owns kill_switch_events" ON kill_switch_events;
CREATE POLICY "runtime service role owns kill_switch_events" ON kill_switch_events
  FOR ALL USING (auth.role() = 'service_role') WITH CHECK (auth.role() = 'service_role');

DROP POLICY IF EXISTS "runtime service role owns mcp_tool_calls" ON mcp_tool_calls;
CREATE POLICY "runtime service role owns mcp_tool_calls" ON mcp_tool_calls
  FOR ALL USING (auth.role() = 'service_role') WITH CHECK (auth.role() = 'service_role');

COMMIT;
