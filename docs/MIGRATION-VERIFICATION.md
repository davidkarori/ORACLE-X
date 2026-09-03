# Step 6B — Migration Verification

Run the migration against the development Supabase/PostgreSQL database.

Verify:
- migration completes without errors;
- all canonical tables exist;
- all enums exist;
- unique client_order_id constraint exists;
- updated_at triggers exist;
- initial system_state is ACTIVE;
- no secrets are present in the database.

Do not enable live trading.

After successful verification, commit:

`feat: add canonical oracle x database migration`

Then proceed to Step 7: Featherless AI Engine.
