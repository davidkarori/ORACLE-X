# ORACLE X Submission Checklist

## Ready in the repository

- Working War Room vertical slice
- Deterministic fixture demo with no credentials required
- Featherless OpenAI-compatible provider adapter
- Alpaca paper account, stock, options and order adapters
- Read-only Alpaca MCP configuration
- Read-only Alpaca CLI diagnostics script
- Deterministic Risk Governor and Execution Guard
- Options-first typed contracts and calculations
- Append-only decision replay
- Focused automated safety tests
- Dockerfile and Procfile
- Cover image, presentation and two-minute demo script

## Operator actions before submission

- Add Featherless and Alpaca paper credentials locally; never commit `.env`
- Run one connected analysis and capture the War Room
- Only enable paper execution if every gate passes
- Record the two-minute demo using `docs/VIDEO-SCRIPT.md`
- Publish the repository or provide judges access
- Deploy with Vercel, the Docker image or the Procfile service and verify `/api/health`
- Add the public demo, repository and video URLs to the hackathon form
- Submit before the platform deadline; do not rely on a last-minute grace period
