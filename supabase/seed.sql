-- ORACLE X seed data
-- Safe foundation records only. No broker credentials or live-trading data.

insert into agents (role, name, description)
values
  (
    'ATHENA',
    'Athena',
    'Opportunity discovery, market interpretation, thesis drafting, and evidence synthesis.'
  ),
  (
    'HADES',
    'Hades',
    'Adversarial review, thesis challenge, failure-mode discovery, and risk critique.'
  ),
  (
    'HERMES',
    'Hermes',
    'Coordination, messaging, auditable tool mediation, and War Room summaries.'
  ),
  (
    'MORPHEUS',
    'Morpheus',
    'Post-trade autopsy, replay analysis, learning, and memory extraction.'
  ),
  (
    'SYSTEM',
    'ORACLE X System',
    'Deterministic services, state machine, risk controls, execution guard, and audit writer.'
  )
on conflict (role, name) do nothing;

insert into system_state (key, value, updated_by)
values
  (
    'trading_mode',
    '{"mode": "paper", "live_trading_enabled": false}'::jsonb,
    'SYSTEM'
  ),
  (
    'kill_switch',
    '{"active": false, "reason": "Initial seed default"}'::jsonb,
    'SYSTEM'
  ),
  (
    'risk_governor',
    '{"enabled": true, "fail_closed": true, "approval_ttl_seconds": 300}'::jsonb,
    'SYSTEM'
  ),
  (
    'execution_guard',
    '{"enabled": true, "fail_closed": true}'::jsonb,
    'SYSTEM'
  ),
  (
    'inference_provider',
    '{"provider": "featherless", "required": true, "execution_authority": false}'::jsonb,
    'SYSTEM'
  )
on conflict (key) do update
set
  value = excluded.value,
  updated_by = excluded.updated_by,
  updated_at = now();

insert into kill_switch_events (active, reason, actor_role, actor_name)
values (
  false,
  'Initial seed default. Paper trading remains the expected default until explicitly configured otherwise.',
  'SYSTEM',
  'ORACLE X System'
);

insert into audit_events (
  event_kind,
  actor_role,
  actor_name,
  subject_table,
  payload
)
values (
  'SYSTEM_STATE',
  'SYSTEM',
  'ORACLE X System',
  'system_state',
  '{"message": "Initial ORACLE X foundation seed applied", "live_trading_enabled": false}'::jsonb
);
