import asyncio
import hashlib
import json
import time
import uuid
from datetime import date, datetime, timedelta
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from .config import Settings
from .domain import (
    AgentRole,
    AthenaDecision,
    Bias,
    HadesDecision,
    HermesDecision,
    MarketContext,
    MorpheusDecision,
    OptionQuote,
    Strategy,
    utc_now,
)


class IntegrationError(RuntimeError):
    pass


DecisionT = TypeVar("DecisionT", bound=BaseModel)


class FeatherlessClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def athena(self, context: dict[str, Any]) -> AthenaDecision:
        return await self._decide(
            AgentRole.ATHENA,
            context,
            AthenaDecision,
            "Create a falsifiable opportunity thesis and directional bias. Do not calculate prices or risk.",
        )

    async def hades(self, context: dict[str, Any]) -> HadesDecision:
        return await self._decide(
            AgentRole.HADES,
            context,
            HadesDecision,
            "Attack Athena's thesis. Separate fatal from survivable objections and choose CONTINUE, REVISE, or REJECT.",
        )

    async def hermes(self, context: dict[str, Any]) -> HermesDecision:
        return await self._decide(
            AgentRole.HERMES,
            context,
            HermesDecision,
            "Summarize the mediated read-only MCP research, identify data gaps, and choose READY or BLOCKED. Do not select or price a trade.",
        )

    async def morpheus(self, context: dict[str, Any]) -> MorpheusDecision:
        return await self._decide(
            AgentRole.MORPHEUS,
            context,
            MorpheusDecision,
            "Perform a post-trade autopsy from the immutable record. Identify lessons only; never alter execution authority.",
        )

    async def _decide(
        self,
        role: AgentRole,
        context: dict[str, Any],
        contract: type[DecisionT],
        job: str,
    ) -> DecisionT:
        if not self.settings.featherless_configured:
            return self._fixture(role, context, contract)
        model = self.settings.model_for(role.value)
        started = time.perf_counter()
        payload = {
            "model": model,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": (
                        f"You are ORACLE X {role.value}. {job} You are advisory and have no order authority. "
                        f"Return only JSON matching this schema: {json.dumps(contract.model_json_schema())}"
                    ),
                },
                {"role": "user", "content": json.dumps(context, default=str)},
            ],
        }
        headers = {
            "Authorization": f"Bearer {self.settings.featherless_api_key}",
            "Content-Type": "application/json",
            "X-Title": "ORACLE X",
        }
        last_error: Exception | None = None
        for attempt in range(self.settings.featherless_max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.settings.featherless_timeout_seconds) as client:
                    response = await client.post(
                        f"{self.settings.featherless_base_url.rstrip('/')}/chat/completions",
                        headers=headers,
                        json=payload,
                    )
                    response.raise_for_status()
                    result = response.json()
                parsed = json.loads(result["choices"][0]["message"]["content"])
                parsed.update(
                    role=role,
                    provider="featherless",
                    model=model,
                    latency_ms=int((time.perf_counter() - started) * 1000),
                    trace_id=result.get("id", uuid.uuid4().hex),
                )
                return contract.model_validate(parsed)
            except (httpx.HTTPError, KeyError, TypeError, ValueError, json.JSONDecodeError, ValidationError) as exc:
                last_error = exc
                if attempt < self.settings.featherless_max_retries:
                    await asyncio.sleep(0.1 * (attempt + 1))
        raise IntegrationError(f"Featherless {role.value} output failed contract validation: {last_error}")

    def parse_for_test(self, role: AgentRole, payload: dict[str, Any]) -> BaseModel:
        contracts: dict[AgentRole, type[BaseModel]] = {
            AgentRole.ATHENA: AthenaDecision,
            AgentRole.HADES: HadesDecision,
            AgentRole.HERMES: HermesDecision,
            AgentRole.MORPHEUS: MorpheusDecision,
        }
        envelope = {
            **payload,
            "role": role,
            "provider": "test",
            "model": "test",
            "latency_ms": 0,
            "trace_id": "test-trace",
        }
        try:
            return contracts[role].model_validate(envelope)
        except ValidationError as exc:
            raise IntegrationError(f"Malformed {role.value} output") from exc

    def _fixture(self, role: AgentRole, context: dict[str, Any], contract: type[DecisionT]) -> DecisionT:
        symbol = str(context.get("symbol", "SPY"))
        common = {
            "role": role,
            "confidence": 0.76,
            "evidence_refs": ["market-snapshot", "mcp-research"],
            "provider": "fixture",
            "model": "deterministic-demo-fixture",
            "latency_ms": 0,
            "trace_id": hashlib.sha256(f"fixture:{role.value}:{symbol}".encode()).hexdigest()[:16],
        }
        payloads: dict[AgentRole, dict[str, Any]] = {
            AgentRole.ATHENA: {
                "thesis": f"{symbol} has a liquid, bounded-risk options opportunity suitable for committee review.",
                "bias": Bias.BULLISH,
                "assumptions": ["Paper environment", "One strategy unit", "Evidence remains fresh"],
                "invalidation_conditions": ["Evidence becomes stale", "Liquidity exceeds policy"],
            },
            AgentRole.HADES: {
                "critique": "The thesis can fail through an adverse gap, volatility compression, or time decay.",
                "fatal_objections": [],
                "survivable_objections": ["Time decay", "Volatility compression"],
                "recommendation": "CONTINUE",
            },
            AgentRole.HERMES: {
                "research_summary": "Read-only market, option-chain, and news checks are available for deterministic evaluation.",
                "tool_refs": ["get_stock_snapshot", "get_option_chain", "get_news"],
                "data_gaps": [],
                "recommendation": "READY",
            },
            AgentRole.MORPHEUS: {
                "outcome_summary": "The simulated lifecycle preserved every gate and produced a replayable bounded outcome.",
                "what_worked": ["Defined risk", "Fresh evidence", "Idempotent intent"],
                "what_failed": [],
                "wrong_assumptions": [],
                "lessons": ["Keep deterministic gates independent from advisory memory"],
                "recommendation": "RETAIN",
            },
        }
        return contract.model_validate({**common, **payloads[role]})


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
                account_response, stock_response = await asyncio.gather(
                    client.get(f"{self.settings.alpaca_trading_base_url.rstrip('/')}/v2/account", headers=self.headers),
                    client.get(
                        f"{self.settings.alpaca_data_base_url.rstrip('/')}/v2/stocks/{symbol}/snapshot",
                        headers=self.headers,
                        params={"feed": "iex"},
                    ),
                )
                account_response.raise_for_status()
                stock_response.raise_for_status()
                account = account_response.json()
                stock_snapshot = stock_response.json()
                price = self._stock_price(stock_snapshot)
                stock_observed_at = self._market_timestamp(stock_snapshot)
                chain, options_observed_at = await self._option_chain(client, symbol, price)
            return MarketContext(
                symbol=symbol,
                source="alpaca",
                observed_at=min(stock_observed_at, options_observed_at),
                underlying_price=price,
                account_status=str(account.get("status", "UNKNOWN")),
                buying_power=float(account.get("buying_power", 0)),
                option_chain=chain,
                raw_refs=["alpaca:v2/account", "alpaca:v2/stocks/snapshot", "alpaca:v2/options/contracts", "alpaca:v1beta1/options/snapshots"],
            )
        except (httpx.HTTPError, KeyError, TypeError, ValueError, IndexError) as exc:
            raise IntegrationError(f"Alpaca evidence retrieval failed: {exc}") from exc

    @staticmethod
    def _stock_price(snapshot: dict[str, Any]) -> float:
        trade = snapshot.get("latestTrade") or snapshot.get("latest_trade") or {}
        bar = snapshot.get("minuteBar") or snapshot.get("minute_bar") or {}
        return float(trade.get("p") or bar.get("c"))

    @staticmethod
    def _market_timestamp(snapshot: dict[str, Any]) -> datetime:
        for key in ("latestTrade", "latest_trade", "latestQuote", "latest_quote", "minuteBar", "minute_bar"):
            value = (snapshot.get(key) or {}).get("t")
            if value:
                parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
                if parsed.tzinfo is None:
                    raise IntegrationError("Alpaca market timestamp was missing its timezone")
                return parsed
        raise IntegrationError("Alpaca market evidence did not include a timestamp")

    async def _option_chain(self, client: httpx.AsyncClient, symbol: str, price: float) -> tuple[list[OptionQuote], datetime]:
        today = date.today()
        contracts_response = await client.get(
            f"{self.settings.alpaca_trading_base_url.rstrip('/')}/v2/options/contracts",
            headers=self.headers,
            params={
                "underlying_symbols": symbol,
                "status": "active",
                "expiration_date_gte": (today + timedelta(days=14)).isoformat(),
                "expiration_date_lte": (today + timedelta(days=45)).isoformat(),
                "strike_price_gte": round(price * 0.85, 2),
                "strike_price_lte": round(price * 1.15, 2),
                "limit": 100,
            },
        )
        contracts_response.raise_for_status()
        contracts = contracts_response.json().get("option_contracts", [])
        if not contracts:
            raise IntegrationError("Alpaca returned no suitable option contracts")
        expiration = min(item["expiration_date"] for item in contracts)
        selected = [item for item in contracts if item["expiration_date"] == expiration]
        selected = sorted(selected, key=lambda item: abs(float(item["strike_price"]) - price))[:24]
        symbols = ",".join(item["symbol"] for item in selected)
        snapshots_response = await client.get(
            f"{self.settings.alpaca_data_base_url.rstrip('/')}/v1beta1/options/snapshots/{symbol}",
            headers=self.headers,
            params={"symbols": symbols, "feed": "indicative"},
        )
        snapshots_response.raise_for_status()
        snapshots = snapshots_response.json().get("snapshots", {})
        quotes: list[OptionQuote] = []
        observed_times: list[datetime] = []
        for item in selected:
            snapshot = snapshots.get(item["symbol"], {})
            quote = snapshot.get("latestQuote") or snapshot.get("latest_quote") or {}
            if not quote.get("ap") or not quote.get("t"):
                continue
            greeks = snapshot.get("greeks") or {}
            quotes.append(
                OptionQuote(
                    contract_symbol=item["symbol"],
                    underlying_symbol=symbol,
                    option_type=str(item["type"]).upper(),
                    expiration=item["expiration_date"],
                    strike=float(item["strike_price"]),
                    bid=float(quote.get("bp", 0)),
                    ask=float(quote["ap"]),
                    implied_volatility=snapshot.get("impliedVolatility") or snapshot.get("implied_volatility"),
                    delta=greeks.get("delta"),
                    gamma=greeks.get("gamma"),
                    theta=greeks.get("theta"),
                    vega=greeks.get("vega"),
                    rho=greeks.get("rho"),
                )
            )
            observed_times.append(self._market_timestamp(snapshot))
        if len(quotes) < 4:
            raise IntegrationError("Alpaca option chain did not contain enough quoted contracts")
        return quotes, min(observed_times)

    async def submit_strategy(self, strategy: Strategy, client_order_id: str) -> dict[str, Any]:
        if not self.settings.execution_enabled:
            raise IntegrationError("Paper execution is disabled by configuration")
        if not self.settings.is_paper_endpoint:
            raise IntegrationError("Refusing non-paper Alpaca endpoint")
        if len(strategy.legs) == 1:
            leg = strategy.legs[0]
            payload: dict[str, Any] = {
                "symbol": leg.contract_symbol,
                "qty": str(strategy.quantity),
                "side": leg.side.lower(),
                "type": "limit",
                "time_in_force": "day",
                "limit_price": f"{leg.midpoint:.2f}",
                "client_order_id": client_order_id,
            }
        else:
            payload = {
                "order_class": "mleg",
                "qty": str(strategy.quantity),
                "type": "limit",
                "time_in_force": "day",
                "limit_price": f"{(strategy.net_debit or strategy.net_credit) / 100:.2f}",
                "client_order_id": client_order_id,
                "legs": [
                    {
                        "symbol": leg.contract_symbol,
                        "ratio_qty": str(leg.ratio),
                        "side": leg.side.lower(),
                        "position_intent": leg.position_intent.lower(),
                    }
                    for leg in strategy.legs
                ],
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
            "simulated": False,
        }

    @staticmethod
    def _fixture(symbol: str) -> MarketContext:
        expiration = (date.today() + timedelta(days=28)).isoformat()
        quotes: list[OptionQuote] = []
        call_mid = {90: 10.5, 95: 6.0, 100: 2.8, 105: 1.4, 110: 0.8}
        put_mid = {90: 0.8, 95: 1.4, 100: 2.8, 105: 6.0, 110: 10.5}
        for option_type, prices in (("CALL", call_mid), ("PUT", put_mid)):
            for strike, midpoint in prices.items():
                code = "C" if option_type == "CALL" else "P"
                contract = f"{symbol}{expiration.replace('-', '')[2:]}{code}{strike * 1000:08d}"
                quotes.append(
                    OptionQuote(
                        contract_symbol=contract,
                        underlying_symbol=symbol,
                        option_type=option_type,
                        expiration=expiration,
                        strike=float(strike),
                        bid=round(midpoint - 0.05, 2),
                        ask=round(midpoint + 0.05, 2),
                    )
                )
        return MarketContext(
            symbol=symbol,
            source="fixture",
            observed_at=utc_now(),
            underlying_price=100.0,
            account_status="FIXTURE_ACTIVE",
            buying_power=100_000,
            option_chain=quotes,
            raw_refs=["fixture:submission-safe-option-chain"],
        )
