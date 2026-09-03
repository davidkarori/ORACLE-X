# ORACLE X Submission Brief

## Short description

ORACLE X is a safety-first AI options committee. Four specialized models build, challenge, structure and stress-test a trade, while deterministic software alone controls risk approval and Alpaca paper execution.

## Problem

Most AI trading demos allow one probabilistic model to generate both the idea and the action. That makes numerical errors, prompt injection and untraceable decisions capable of reaching a broker. ORACLE X separates advisory intelligence from execution authority.

## AI logic

Athena creates an evidence-backed thesis. Hades attacks its assumptions. Hermes proposes a defined-risk options expression. Morpheus interprets deterministic stress results. Each Featherless response is schema-validated and recorded with its provider, model, confidence and trace identifier. Invalid or unavailable inference fails closed.

## Deterministic controls

Application code normalizes the option leg and calculates premium, spread, maximum loss, break-even, position quantity and data age. The Risk Governor checks paper mode, kill switch, account state, evidence freshness, loss, liquidity, quantity and buying power. Its approval expires.

Immediately before submission, the Execution Guard rechecks lifecycle state, approval, kill switch, paper endpoint, evidence source and execution configuration. A durable idempotency reservation prevents duplicate intent. No agent class imports or calls the broker submission method.

## Alpaca infrastructure

ORACLE X reads account, stock and options evidence from Alpaca. Its official MCP configuration excludes the entire trading toolset and exposes only account, assets, stock data, options data and news. Alpaca CLI is used for read-only diagnostics. The deterministic execution adapter is the only component capable of calling the Alpaca Trading API, and it rejects every non-paper endpoint during application startup.

## Options strategy

The emergency submission demonstrates a long call: a first-class options leg with contract symbol, underlying, strike, expiration, side, quantity, ratio, intent and limit price. Maximum loss is bounded to premium paid. The domain contract is leg-based so spreads and other combinations can be added without giving models authority over quantities or prices.

## Audit and replay

Every opportunity, state transition, market snapshot, agent decision, quantitative result, risk verdict, execution validation and broker action is appended to an immutable event timeline. The War Room reconstructs why a trade was permitted or blocked from one replay endpoint.

## Safety posture

The submitted build is paper-only. Execution defaults off. Fixture market or inference evidence can demonstrate the workflow but can never authorize broker mutation. The system requires the exact HTTPS Alpaca paper host and refuses live endpoints, live configuration, stale evidence, expired approval, duplicate intent and active kill switches.
