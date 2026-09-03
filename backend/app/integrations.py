import hashlib
import json
import time
import uuid
from datetime import date, timedelta
from typing import Any

import httpx

from .config import Settings
from .domain import AgentDecision, AgentRole, MarketContext, utc_now


class IntegrationError(RuntimeError):
    pass


class FeatherlessClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def decide(self, role: AgentRole, context: dict[str, Any]) -> AgentDecision:
        if not self.settings.featherless_configured:
            return self._fixture(role, context)

        model = self.settings.model_for(role.value)
        started = time.perf_counter()
        payload = {
            "model": model,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": self._system_prompt(role)},
                {"role": "user", "content": json.dumps(context, default=str)},
            ],
        }
        headers = {
            "Authorization": f"Bearer {self.settings.featherless_api_key}",
            "Content-Type": "application/json",
            "X-Title": "ORACLE X",
        }
        attempts = self.settings.featherless_max_retries + 1
        last_error: Exception | None = None
        for attempt in range(attempts):
            try:
                async with httpx.AsyncClient(timeout=self.settings.featherless_timeout_seconds) as client:
                    response = await client.post(
                        f"{self.settings.featherless_base_url.rstrip('/')}/chat/completions",
                        headers=headers,
                        json=payload,
                    )
                    response.raise_for_status()
                    result = response.json()
                    content = result["choices"][0]["message"]["content"]
                    parsed = json.loads(content)
                    elapsed = int((time.perf_counter() - started) * 1000)
                    return AgentDecision(
                        role=role,
                        decision=str(parsed["decision"]),
                        confidence=float(parsed["confidence"]),
                        summary=str(parsed["summary"]),
                        evidence_refs=[str(x) for x in parsed.get("evidence_refs", [])],
                        risks=[str(x) for x in parsed.get("risks", [])],
                        assumptions=[str(x) for x in parsed.get("assumptions", [])],
                        invalidation_conditions=[str(x) for x in parsed.get("invalidation_conditions", [])],
                        provider="featherless",
                        model=model,
                        latency_ms=elapsed,
                        trace_id=result.get("id", uuid.uuid4().hex),
                    )
            except (httpx.HTTPError, KeyError, ValueError, json.JSONDecodeError) as exc:
                last_error = exc
                if attempt + 1 >= attempts:
                    break
        raise IntegrationError(f"Featherless {role.value} inference failed: {last_error}")

    @staticmethod
    def _system_prompt(role: AgentRole) -> str:
        jobs = {
            AgentRole.ATHENA: "Build an evidence-backed opportunity thesis.",
            AgentRole.HADES: "Attack the thesis and identify its strongest failure modes.",
            AgentRole.HERMES: "Choose a defined-risk options expression. Never invent prices or Greeks.",
            AgentRole.MORPHEUS: "Assess the deterministic stress results and identify break conditions.",
        }
        return (
            "You are ORACLE X " + role.value + ". " + jobs[role] + " "
            "You are advisory and have no execution authority. Return only JSON with keys: "
            "decision, confidence (0 to 1), summary, evidence_refs, risks, assumptions, "
            "invalidation_conditions. Keep each list concise."
        )

    def _fixture(self, role: AgentRole, context: dict[str, Any]) -> AgentDecision:
        symbol = str(context.get("symbol", "SPY"))
        summaries = {
            AgentRole.ATHENA: f"{symbol} presents a liquid, bounded-risk options candidate for committee review.",
            AgentRole.HADES: "The thesis is vulnerable to volatility compression, adverse gaps, and stale evidence.",
            AgentRole.HERMES: "Use one long call so premium paid is the mechanically bounded maximum loss.",
            AgentRole.MORPHEUS: "The position survives only if price appreciation exceeds premium decay before expiry.",
        }
        decisions = {
            AgentRole.ATHENA: "CONTINUE",
            AgentRole.HADES: "CHALLENGE_RECORDED",
            AgentRole.HERMES: "LONG_CALL",
            AgentRole.MORPHEUS: "STRESS_ACCEPTABLE",
        }
        trace = hashlib.sha256(f"fixture:{role.value}:{symbol}".encode()).hexdigest()[:16]
        return AgentDecision(
            role=role,
            decision=decisions[role],
            confidence=0.72,
            summary=summaries[role],
            evidence_refs=["market-snapshot", "deterministic-quant"],
            risks=["market movement", "liquidity", "time decay"],
            assumptions=["paper environment", "one-contract position"],
            invalidation_conditions=["stale data", "spread above policy", "kill switch active"],
            provider="fixture",
            model="deterministic-demo-fixture",
            latency_ms=0,
            trace_id=trace,
        )


class AlpacaClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.headers = {
            "APCA-API-KEY-ID": settings.alpaca_api_key,
            "APCA-API-SECRET-KEY": settings.alpaca_api_secret,
        }

    async def market_context(self, symbol: str) -> MarketContext:
        if not self.settings.alpaca_configured:
            return self._fixture(symbol)
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                account_response, stock_response = await self._account_and_stock(client, symbol)
                account = account_response.json()
                stock = stock_response.json()
                price = self._stock_price(stock)
                contract = await self._nearest_call(client, symbol, price)
                bid, ask = await self._option_quote(client, symbol, contract["symbol"])
                return MarketContext(
                    symbol=symbol,
                    source="alpaca",
                    observed_at=utc_now(),
                    underlying_price=price,
                    option_symbol=contract["symbol"],
                    strike=float(contract["strike_price"]),
                    expiration=contract["expiration_date"],
                    bid=bid,
                    ask=ask,
                    account_status=str(account.get("status", "UNKNOWN")),
                    buying_power=float(account.get("buying_power", 0)),
                    raw_refs=["alpaca:v2/account", "alpaca:v2/stocks/snapshot", "alpaca:v2/options/contracts"],
                )
        except (httpx.HTTPError, KeyError, ValueError, IndexError) as exc:
            raise IntegrationError(f"Alpaca evidence retrieval failed: {exc}") from exc

    async def _account_and_stock(self, client: httpx.AsyncClient, symbol: str):
        account = client.get(
            f"{self.settings.alpaca_trading_base_url.rstrip('/')}/v2/account", headers=self.headers
        )
        stock = client.get(
            f"{self.settings.alpaca_data_base_url.rstrip('/')}/v2/stocks/{symbol}/snapshot",
            headers=self.headers,
            params={"feed": "iex"},
        )
        results = await __import__("asyncio").gather(account, stock)
        for response in results:
            response.raise_for_status()
        return results

    @staticmethod
    def _stock_price(snapshot: dict[str, Any]) -> float:
        trade = snapshot.get("latestTrade") or snapshot.get("latest_trade") or {}
        bar = snapshot.get("minuteBar") or snapshot.get("minute_bar") or {}
        return float(trade.get("p") or bar.get("c"))

    async def _nearest_call(self, client: httpx.AsyncClient, symbol: str, price: float) -> dict[str, Any]:
        today = date.today()
        response = await client.get(
            f"{self.settings.alpaca_trading_base_url.rstrip('/')}/v2/options/contracts",
            headers=self.headers,
            params={
                "underlying_symbols": symbol,
                "status": "active",
                "type": "call",
                "expiration_date_gte": (today + timedelta(days=14)).isoformat(),
                "expiration_date_lte": (today + timedelta(days=45)).isoformat(),
                "limit": 100,
            },
        )
        response.raise_for_status()
        contracts = response.json().get("option_contracts", [])
        candidates = [item for item in contracts if float(item["strike_price"]) >= price]
        return min(candidates or contracts, key=lambda item: abs(float(item["strike_price"]) - price))

    async def _option_quote(self, client: httpx.AsyncClient, underlying: str, contract: str) -> tuple[float, float]:
        response = await client.get(
            f"{self.settings.alpaca_data_base_url.rstrip('/')}/v1beta1/options/snapshots/{underlying}",
            headers=self.headers,
            params={"symbols": contract, "feed": "indicative"},
        )
        response.raise_for_status()
        snapshot = response.json().get("snapshots", {}).get(contract, {})
        quote = snapshot.get("latestQuote") or snapshot.get("latest_quote") or {}
        return float(quote["bp"]), float(quote["ap"])

    async def submit(self, symbol: str, quantity: int, limit_price: float, client_order_id: str) -> dict[str, Any]:
        if not self.settings.execution_enabled:
            raise IntegrationError("Paper execution is disabled by configuration")
        payload = {
            "symbol": symbol,
            "qty": str(quantity),
            "side": "buy",
            "type": "limit",
            "time_in_force": "day",
            "limit_price": f"{limit_price:.2f}",
            "client_order_id": client_order_id,
        }
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                f"{self.settings.alpaca_trading_base_url.rstrip('/')}/v2/orders",
                headers=self.headers,
                json=payload,
            )
            response.raise_for_status()
            result = response.json()
        return {
            "broker": "alpaca",
            "order_id": result.get("id"),
            "client_order_id": result.get("client_order_id", client_order_id),
            "status": result.get("status", "submitted"),
            "submitted_at": result.get("submitted_at"),
        }

    @staticmethod
    def _fixture(symbol: str) -> MarketContext:
        expiration = (date.today() + timedelta(days=28)).isoformat()
        strike = 100.0
        contract = f"{symbol}{expiration.replace('-', '')[2:]}C{int(strike * 1000):08d}"
        return MarketContext(
            symbol=symbol,
            source="fixture",
            observed_at=utc_now(),
            underlying_price=99.25,
            option_symbol=contract,
            strike=strike,
            expiration=expiration,
            bid=4.70,
            ask=4.90,
            account_status="FIXTURE_ACTIVE",
            buying_power=100_000,
            raw_refs=["fixture:submission-safe-snapshot"],
        )
