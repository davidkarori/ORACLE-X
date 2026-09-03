# Migration Verification

Apply `001_initial_schema.sql`, `002_safety_audit_extensions.sql` and `003_runtime_persistence.sql` in numeric order against the development Supabase/PostgreSQL database.

Verify:
- migration completes without errors;
- all canonical tables exist;
- all enums exist;
- unique client_order_id constraint exists;
- updated_at triggers exist;
- initial system_state is ACTIVE;
- workflow_runs and execution_intents exist;
- execution_intents.idempotency_key is unique;
- oracle_events.sequence exists and is unique;
- oracle_events and oracle_memory reject update/delete attempts;
- no secrets are present in the database.

Do not enable live trading.

The third migration exists because the runtime now supports PostgreSQL workflow snapshots, replay ordering and durable execution-intent reservation. It does not alter prior migration files or weaken existing schema constraints.
