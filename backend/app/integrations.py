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
            (
                "Recommend exactly one allowed defined-risk strategy family, directional intent, target risk profile, and structural intent. "
                "Do not choose contracts, strikes, expiry, quantity, prices, Greeks, payoff values, exposure, or position size."
            ),
        )

    async def morpheus(self, context: dict[str, Any]) -> MorpheusDecision:
        return await self._decide(
            AgentRole.MORPHEUS,
            context,
            MorpheusDecision,
            (
                "Interpret the immutable deterministic stress scenarios and choose PASS, CAUTION, or REJECT. "
                "Do not recalculate scenario values, approve risk, or authorize execution."
            ),
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
            "temperature": self.settings.featherless_temperature,
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
                    if response.status_code == 429:
                        retry_after = response.headers.get("Retry-After")
                        raise IntegrationError(f"Featherless rate limited; retry_after={retry_after or 'unspecified'}")
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
            except (httpx.HTTPError, IntegrationError, KeyError, TypeError, ValueError, json.JSONDecodeError, ValidationError) as exc:
                last_error = exc
                if attempt < self.settings.featherless_max_retries:
                    retry_after = getattr(exc, "response", None).headers.get("Retry-After") if isinstance(exc, httpx.HTTPStatusError) else None
                    if isinstance(exc, IntegrationError) and "retry_after=" in str(exc):
                        retry_after = str(exc).split("retry_after=", 1)[1]
                    delay = min(float(retry_after), 2.0) if retry_after and retry_after.replace(".", "", 1).isdigit() else 0.1 * (attempt + 1)
                    await asyncio.sleep(delay)
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
        athena_context = context.get("athena", {})
        bias = Bias(athena_context.get("bias", Bias.BULLISH))
        risk_profile = str(context.get("risk_profile", "CONSERVATIVE"))
        if bias == Bias.NEUTRAL:
            family = "IRON_CONDOR"
        elif bias == Bias.BULLISH:
            family = "LONG_CALL" if risk_profile == "AGGRESSIVE" else "BULL_CALL_SPREAD"
        else:
            family = "LONG_PUT" if risk_profile == "AGGRESSIVE" else "BEAR_PUT_SPREAD"
        target_risk = "PREMIUM_ONLY" if family in {"LONG_CALL", "LONG_PUT"} else "DEFINED_RISK"
        stress_context = context.get("stress", {})
        stress_recommendation = str(stress_context.get("recommendation", "PASS"))
        critical_scenarios = [
            str(item.get("name"))
            for item in stress_context.get("scenarios", [])
            if item.get("severity") == "CRITICAL" or item.get("breaks_thesis")
        ]
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
                "preferred_strategy_family": family,
                "rationale": f"{family} expresses the surviving {bias.value} thesis while keeping the structure bounded.",
                "directional_intent": bias,
                "target_risk_profile": target_risk,
                "structural_intent": ["Use normalized explicit legs", "Reject naked short exposure"],
            },
            AgentRole.MORPHEUS: {
                "interpretation": "Deterministic scenarios show bounded loss and identify the conditions that break the thesis.",
                "break_conditions": list(stress_context.get("break_conditions", [])),
                "critical_scenarios": critical_scenarios,
                "recommendation": stress_recommendation,
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
                clock_response = await client.get(f"{self.settings.alpaca_trading_base_url.rstrip('/')}/v2/clock", headers=self.headers)
                orders_response = await client.get(
                    f"{self.settings.alpaca_trading_base_url.rstrip('/')}/v2/orders",
                    headers=self.headers,
                    params={"status": "open", "symbols": symbol, "nested": "true"},
                )
                positions_response = await client.get(f"{self.settings.alpaca_trading_base_url.rstrip('/')}/v2/positions", headers=self.headers)
                clock_response.raise_for_status()
                orders_response.raise_for_status()
                positions_response.raise_for_status()
                clock = clock_response.json()
                open_orders = orders_response.json()
                positions = positions_response.json()
                price = self._stock_price(stock_snapshot)
                stock_observed_at = self._market_timestamp(stock_snapshot)
                chain, options_observed_at = await self._option_chain(client, symbol, price)
                symbol_positions = [
                    str(item.get("symbol"))
                    for item in positions
                    if str(item.get("symbol", "")).startswith(symbol)
                ]
            return MarketContext(
                symbol=symbol,
                source="alpaca",
                observed_at=min(stock_observed_at, options_observed_at),
                underlying_price=price,
                account_status=str(account.get("status", "UNKNOWN")),
                buying_power=float(account.get("buying_power", 0)),
                options_approved_level=int(account.get("options_approved_level") or account.get("options_trading_level") or 0),
                market_is_open=bool(clock.get("is_open")),
                portfolio_exposure=sum(abs(float(item.get("market_value", 0) or 0)) for item in positions),
                symbol_exposure=sum(abs(float(item.get("market_value", 0) or 0)) for item in positions if str(item.get("symbol", "")).startswith(symbol)),
                open_trade_count=len(open_orders),
                conflicting_orders=[str(item.get("client_order_id") or item.get("id")) for item in open_orders],
                conflicting_positions=symbol_positions,
                option_chain=chain,
                raw_refs=["alpaca:v2/account", "alpaca:v2/clock", "alpaca:v2/orders", "alpaca:v2/positions", "alpaca:v2/stocks/snapshot", "alpaca:v2/options/contracts", "alpaca:v1beta1/options/snapshots"],
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
        snapshots_response = await client.get(
            f"{self.settings.alpaca_data_base_url.rstrip('/')}/v1beta1/options/snapshots/{symbol}",
            headers=self.headers,
            params={"feed": "indicative", "limit": 100},
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
                    status=str(item.get("status", "active")),
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
        payload = self.order_payload(strategy, client_order_id)
        async with httpx.AsyncClient(timeout=20) as client:
            try:
                response = await client.post(
                    f"{self.settings.alpaca_trading_base_url.rstrip('/')}/v2/orders",
                    headers=self.headers,
                    json=payload,
                )
                response.raise_for_status()
                result = response.json()
                reconciliation = await self.reconcile_order(client_order_id, result)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                lookup = await self.lookup_order(client_order_id)
                if lookup is None:
                    return {
                        "broker": "alpaca",
                        "request_payload": payload,
                        "raw_response": {"error": str(exc)},
                        "order_id": None,
                        "client_order_id": client_order_id,
                        "status": "unknown",
                        "simulated": False,
                        "legs": payload.get("legs", []),
                        "fills": [],
                        "positions": [],
                        "reconciliation_status": "UNKNOWN",
                        "reconciliation_events": [{"status": "UNKNOWN_SUBMISSION", "error": str(exc)}],
                    }
                result = lookup
                reconciliation = await self.reconcile_order(client_order_id, result)
        return {
            "broker": "alpaca",
            "request_payload": payload,
            "raw_response": result,
            "order_id": result.get("id"),
            "client_order_id": result.get("client_order_id", client_order_id),
            "status": result.get("status", "submitted"),
            "submitted_at": result.get("submitted_at"),
            "simulated": False,
            "legs": result.get("legs") or payload.get("legs", []),
            "fills": reconciliation["fills"],
            "positions": reconciliation["positions"],
            "reconciliation_status": reconciliation["status"],
            "reconciliation_events": reconciliation["events"],
        }

    def order_payload(self, strategy: Strategy, client_order_id: str) -> dict[str, Any]:
        if len(strategy.legs) == 1:
            leg = strategy.legs[0]
            return {
                "symbol": leg.contract_symbol,
                "qty": str(strategy.quantity),
                "side": leg.side.lower(),
                "type": "limit",
                "time_in_force": "day",
                "limit_price": f"{leg.midpoint:.2f}",
                "client_order_id": client_order_id,
            }
        limit_price = (strategy.net_debit or -strategy.net_credit) / 100
        return {
            "order_class": "mleg",
            "qty": str(strategy.quantity),
            "type": "limit",
            "time_in_force": "day",
            "limit_price": f"{limit_price:.2f}",
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

    async def lookup_order(self, client_order_id: str) -> dict[str, Any] | None:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(
                f"{self.settings.alpaca_trading_base_url.rstrip('/')}/v2/orders:by_client_order_id",
                headers=self.headers,
                params={"client_order_id": client_order_id, "nested": "true"},
            )
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.json()

    async def reconcile_order(self, client_order_id: str, order: dict[str, Any]) -> dict[str, Any]:
        lookup = await self.lookup_order(client_order_id)
        resolved = lookup or order
        fills = [leg for leg in resolved.get("legs", []) if str(leg.get("filled_qty", "0")) not in {"0", "0.0"}]
        if str(resolved.get("filled_qty", "0")) not in {"0", "0.0"}:
            fills.append(resolved)
        positions = await self.positions_for_order(resolved)
        filled_without_position = str(resolved.get("status", "")).lower() in {"filled", "partially_filled"} and not positions
        mismatch = resolved.get("client_order_id") not in {None, client_order_id} or filled_without_position
        return {
            "status": "MISMATCH" if mismatch else "KNOWN",
            "fills": fills,
            "positions": positions,
            "events": [
                {
                    "status": "ORDER_LOOKUP",
                    "client_order_id": client_order_id,
                    "broker_order_id": resolved.get("id"),
                    "order_status": resolved.get("status"),
                    "mismatch": mismatch,
                    "filled_without_position": filled_without_position,
                }
            ],
        }

    async def positions_for_order(self, order: dict[str, Any]) -> list[dict[str, Any]]:
        symbols = [str(leg.get("symbol")) for leg in order.get("legs", []) if leg.get("symbol")]
        if not symbols and order.get("symbol"):
            symbols = [str(order["symbol"])]
        positions: list[dict[str, Any]] = []
        async with httpx.AsyncClient(timeout=20) as client:
            for symbol in symbols:
                response = await client.get(f"{self.settings.alpaca_trading_base_url.rstrip('/')}/v2/positions/{symbol}", headers=self.headers)
                if response.status_code == 404:
                    continue
                response.raise_for_status()
                positions.append(response.json())
        return positions

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
            options_approved_level=3,
            market_is_open=True,
            option_chain=quotes,
            raw_refs=["fixture:submission-safe-option-chain"],
        )
