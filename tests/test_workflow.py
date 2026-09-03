import asyncio
import sqlite3

import pytest

from app.config import Settings
from app.domain import CreateRunRequest, LifecycleState, WorkflowRun, utc_now
from app.store import AuditStore
from app.workflow import WorkflowService


async def wait_for_run(store: AuditStore, run_id: str):
    for _ in range(100):
        run = store.get_run(run_id)
        if run and run.status != "RUNNING":
            return run
        await asyncio.sleep(0.01)
    raise AssertionError("workflow did not finish")


@pytest.mark.asyncio
async def test_fixture_flow_reaches_execution_ready_without_broker_mutation():
    settings = Settings(oracle_db_path=":memory:")
    store = AuditStore(":memory:")
    service = WorkflowService(settings, store)

    started = service.start(CreateRunRequest(symbol="SPY", execute=False))
    run = await wait_for_run(store, started.id)

    assert run.state == LifecycleState.EXECUTION_READY
    assert run.status == "EXECUTION_READY"
    assert len(run.decisions) == 4
    assert run.risk and run.risk.decision == "APPROVE"
    assert run.execution_guard and run.execution_guard.decision == "PASS"
    assert run.broker_order is None
    assert any(event.kind == "DRY_RUN_COMPLETE" for event in store.events(run.id))


@pytest.mark.asyncio
async def test_agent_fixture_cannot_turn_execution_on():
    settings = Settings(oracle_db_path=":memory:", execution_enabled=False)
    store = AuditStore(":memory:")
    service = WorkflowService(settings, store)

    started = service.start(CreateRunRequest(symbol="SPY", execute=True))
    run = await wait_for_run(store, started.id)

    assert run.state == LifecycleState.REJECTED
    assert "LIVE_EVIDENCE_FOR_MUTATION" in run.execution_guard.reason_codes
    assert "EXECUTION_ENABLED" in run.execution_guard.reason_codes
    assert run.broker_order is None


@pytest.mark.asyncio
async def test_kill_switch_rejects_risk():
    settings = Settings(oracle_db_path=":memory:")
    store = AuditStore(":memory:")
    service = WorkflowService(settings, store)
    service.kill_switch = True

    started = service.start(CreateRunRequest(symbol="SPY"))
    run = await wait_for_run(store, started.id)

    assert run.state == LifecycleState.REJECTED
    assert run.risk and "KILL_SWITCH" in run.risk.reason_codes
    assert run.execution_guard is None


def test_live_endpoint_is_rejected_at_configuration_boundary():
    with pytest.raises(ValueError, match="paper endpoint"):
        Settings(alpaca_trading_base_url="https://api.alpaca.markets")


def test_spoofed_paper_endpoint_is_rejected_at_configuration_boundary():
    with pytest.raises(ValueError, match="paper endpoint"):
        Settings(alpaca_trading_base_url="https://paper-api.alpaca.markets.example.com")


@pytest.mark.asyncio
async def test_fixture_inference_cannot_authorize_execution():
    settings = Settings(oracle_db_path=":memory:", execution_enabled=True)
    store = AuditStore(":memory:")
    service = WorkflowService(settings, store)

    async def alpaca_evidence(symbol: str):
        market = service.alpaca._fixture(symbol)
        market.source = "alpaca"
        return market

    service.alpaca.market_context = alpaca_evidence
    started = service.start(CreateRunRequest(symbol="SPY", execute=True))
    run = await wait_for_run(store, started.id)

    assert run.state == LifecycleState.REJECTED
    assert "LIVE_INFERENCE_FOR_MUTATION" in run.execution_guard.reason_codes
    assert run.broker_order is None


def test_execution_intent_is_unique():
    store = AuditStore(":memory:")
    now = utc_now()

    run = WorkflowRun(
        id="run-1",
        symbol="SPY",
        state=LifecycleState.DETECTED,
        status="RUNNING",
        mode="fixture",
        execute_requested=False,
        created_at=now,
        updated_at=now,
    )
    store.save_run(run)
    assert store.reserve_execution("intent-1", run.id)
    assert not store.reserve_execution("intent-1", run.id)


def test_audit_events_are_append_only():
    store = AuditStore(":memory:")
    now = utc_now()

    run = WorkflowRun(
        id="run-2",
        symbol="SPY",
        state=LifecycleState.DETECTED,
        status="RUNNING",
        mode="fixture",
        execute_requested=False,
        created_at=now,
        updated_at=now,
    )
    store.save_run(run)
    store.append(run.id, "TEST", "SYSTEM", {"ok": True})
    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        store._connection.execute("UPDATE audit_events SET actor = 'OTHER'")


@pytest.mark.asyncio
async def test_max_loss_policy_rejects_expensive_contract():
    settings = Settings(oracle_db_path=":memory:", max_trade_loss=100)
    store = AuditStore(":memory:")
    service = WorkflowService(settings, store)

    started = service.start(CreateRunRequest(symbol="SPY"))
    run = await wait_for_run(store, started.id)

    assert run.state == LifecycleState.REJECTED
    assert run.risk and "MAX_TRADE_LOSS" in run.risk.reason_codes
