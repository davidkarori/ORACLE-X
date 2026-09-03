BEGIN;

CREATE TABLE IF NOT EXISTS workflow_runs (
  id uuid PRIMARY KEY,
  symbol text NOT NULL,
  state opportunity_state NOT NULL,
  status text NOT NULL,
  payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS execution_intents (
  idempotency_key text PRIMARY KEY,
  run_id uuid NOT NULL REFERENCES workflow_runs(id) ON DELETE RESTRICT,
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE oracle_events
  ADD COLUMN IF NOT EXISTS sequence bigserial;

CREATE UNIQUE INDEX IF NOT EXISTS idx_oracle_events_sequence
  ON oracle_events(sequence);

CREATE INDEX IF NOT EXISTS idx_workflow_runs_created
  ON workflow_runs(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_execution_intents_run
  ON execution_intents(run_id);

DROP TRIGGER IF EXISTS trg_oracle_memory_append_only ON oracle_memory;
CREATE TRIGGER trg_oracle_memory_append_only
  BEFORE UPDATE OR DELETE ON oracle_memory
  FOR EACH ROW EXECUTE FUNCTION prevent_audit_mutation();

COMMIT;
