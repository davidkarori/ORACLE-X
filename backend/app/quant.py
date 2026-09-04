from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

from .domain import (
    Bias,
    MarketContext,
    OptionLeg,
    OptionQuote,
    QuantMetrics,
    ScenarioPnl,
    Strategy,
    StrategyFamily,
    StressReport,
    StressScenario,
    utc_now,
)


class StrategyError(ValueError):
    pass


@dataclass(frozen=True)
class StrategyRequest:
    bias: Bias
    risk_profile: str
    thesis: str
    recommended_family: StrategyFamily
    target_risk_profile: str


class StrategyEngine:
    SUPPORTED = frozenset(StrategyFamily)
    DIRECTIONAL_FAMILIES = {
        Bias.BULLISH: frozenset({StrategyFamily.LONG_CALL, StrategyFamily.BULL_CALL_SPREAD}),
        Bias.BEARISH: frozenset({StrategyFamily.LONG_PUT, StrategyFamily.BEAR_PUT_SPREAD}),
        Bias.NEUTRAL: frozenset({StrategyFamily.IRON_CONDOR}),
    }

    def select_family(self, request: StrategyRequest) -> StrategyFamily:
        family = request.recommended_family
        if family not in self.SUPPORTED:
            raise StrategyError(f"Unsupported strategy family: {family}")
        if family not in self.DIRECTIONAL_FAMILIES[request.bias]:
            raise StrategyError(f"{family.value} conflicts with {request.bias.value} directional intent")
        expected_target = "PREMIUM_ONLY" if family in {StrategyFamily.LONG_CALL, StrategyFamily.LONG_PUT} else "DEFINED_RISK"
        if request.target_risk_profile != expected_target:
            raise StrategyError(f"{family.value} requires target risk profile {expected_target}")
        if request.risk_profile == "CONSERVATIVE" and expected_target != "DEFINED_RISK":
            raise StrategyError("Conservative workflow requires a defined-risk spread structure")
        return family

    def build(self, market: MarketContext, request: StrategyRequest) -> list[OptionLeg]:
        family = self.select_family(request)
        calls = self._sorted(market.option_chain, "CALL")
        puts = self._sorted(market.option_chain, "PUT")
        if family == StrategyFamily.LONG_CALL:
            return [self._leg(self._nearest(calls, market.underlying_price), "BUY")]
        if family == StrategyFamily.LONG_PUT:
            return [self._leg(self._nearest(puts, market.underlying_price), "BUY")]
        if family == StrategyFamily.BULL_CALL_SPREAD:
            lower, upper = self._bracket(calls, market.underlying_price)
            return [self._leg(lower, "BUY"), self._leg(upper, "SELL")]
        if family == StrategyFamily.BEAR_PUT_SPREAD:
            lower, upper = self._bracket(puts, market.underlying_price)
            return [self._leg(upper, "BUY"), self._leg(lower, "SELL")]
        if family == StrategyFamily.IRON_CONDOR:
            lower_put, short_put = self._below_pair(puts, market.underlying_price)
            short_call, upper_call = self._above_pair(calls, market.underlying_price)
            return [
                self._leg(lower_put, "BUY"),
                self._leg(short_put, "SELL"),
                self._leg(short_call, "SELL"),
                self._leg(upper_call, "BUY"),
            ]
        raise StrategyError(f"Unsupported strategy family: {family}")

    def validate(self, family: StrategyFamily, legs: list[OptionLeg]) -> None:
        expected = {
            StrategyFamily.LONG_CALL: [("CALL", "BUY")],
            StrategyFamily.LONG_PUT: [("PUT", "BUY")],
            StrategyFamily.BULL_CALL_SPREAD: [("CALL", "BUY"), ("CALL", "SELL")],
            StrategyFamily.BEAR_PUT_SPREAD: [("PUT", "BUY"), ("PUT", "SELL")],
            StrategyFamily.IRON_CONDOR: [("PUT", "BUY"), ("PUT", "SELL"), ("CALL", "SELL"), ("CALL", "BUY")],
        }[family]
        if [(leg.option_type, leg.side) for leg in legs] != expected:
            raise StrategyError(f"Unsafe or malformed {family.value} leg structure")
        if len({leg.expiration for leg in legs}) != 1:
            raise StrategyError("All legs must have the same expiration")
        if any(leg.quantity != 1 or leg.ratio != 1 for leg in legs):
            raise StrategyError("Hardening build supports one 1:1 strategy unit")
        if family == StrategyFamily.IRON_CONDOR and [leg.strike for leg in legs] != sorted(leg.strike for leg in legs):
            raise StrategyError("Iron condor strikes must be strictly ordered")

    @staticmethod
    def _sorted(chain: Iterable[OptionQuote], option_type: str) -> list[OptionQuote]:
        result = sorted((quote for quote in chain if quote.option_type == option_type), key=lambda quote: quote.strike)
        if len(result) < 2:
            raise StrategyError(f"Insufficient {option_type} contracts")
        return result

    @staticmethod
    def _nearest(quotes: list[OptionQuote], price: float) -> OptionQuote:
        return min(quotes, key=lambda quote: abs(quote.strike - price))

    @staticmethod
    def _bracket(quotes: list[OptionQuote], price: float) -> tuple[OptionQuote, OptionQuote]:
        lower = [quote for quote in quotes if quote.strike <= price]
        upper = [quote for quote in quotes if quote.strike > price]
        if not lower or not upper:
            raise StrategyError("Option chain does not bracket the underlying")
        return lower[-1], upper[0]

    @staticmethod
    def _below_pair(quotes: list[OptionQuote], price: float) -> tuple[OptionQuote, OptionQuote]:
        candidates = [quote for quote in quotes if quote.strike < price]
        if len(candidates) < 2:
            raise StrategyError("Iron condor requires two put strikes below spot")
        return candidates[-2], candidates[-1]

    @staticmethod
    def _above_pair(quotes: list[OptionQuote], price: float) -> tuple[OptionQuote, OptionQuote]:
        candidates = [quote for quote in quotes if quote.strike > price]
        if len(candidates) < 2:
            raise StrategyError("Iron condor requires two call strikes above spot")
        return candidates[0], candidates[1]

    @staticmethod
    def _leg(quote: OptionQuote, side: str) -> OptionLeg:
        return OptionLeg(
            contract_symbol=quote.contract_symbol,
            underlying_symbol=quote.underlying_symbol,
            option_type=quote.option_type,
            expiration=quote.expiration,
            strike=quote.strike,
            side=side,
            quantity=1,
            ratio=1,
            position_intent="BUY_TO_OPEN" if side == "BUY" else "SELL_TO_OPEN",
            bid=quote.bid,
            ask=quote.ask,
            midpoint=quote.midpoint,
            implied_volatility=quote.implied_volatility,
            delta=quote.delta,
            gamma=quote.gamma,
            theta=quote.theta,
            vega=quote.vega,
            rho=quote.rho,
        )


class QuantService:
    CONTRACT_MULTIPLIER = 100

    def evaluate(
        self,
        family: StrategyFamily,
        thesis: str,
        bias: Bias,
        legs: list[OptionLeg],
        underlying_price: float,
        observed_at: datetime,
        max_spread_pct: float,
    ) -> tuple[Strategy, QuantMetrics]:
        StrategyEngine().validate(family, legs)
        signed_premium = sum((leg.midpoint if leg.side == "BUY" else -leg.midpoint) * leg.ratio for leg in legs)
        net_debit = round(max(signed_premium, 0) * 100, 2)
        net_credit = round(max(-signed_premium, 0) * 100, 2)
        premium = round(sum(leg.midpoint * leg.ratio for leg in legs) * 100, 2)
        max_loss, max_profit, break_even = self._payoff_limits(family, legs, net_debit, net_credit)
        spreads = [round((leg.ask - leg.bid) / leg.midpoint * 100, 2) for leg in legs]
        scenario_pnl = [
            ScenarioPnl(
                label=f"{change:+.0%} at expiration",
                underlying_price=round(max(0.01, underlying_price * (1 + change)), 2),
                pnl=self.pnl_at_expiration(legs, underlying_price * (1 + change), net_debit, net_credit),
            )
            for change in (-0.10, -0.05, 0.0, 0.05, 0.10)
        ]
        greeks = [leg.delta for leg in legs]
        greeks_status = "AVAILABLE" if all(value is not None for value in greeks) else "PARTIAL" if any(value is not None for value in greeks) else "UNAVAILABLE"
        reward_risk = round(max_profit / max_loss, 3) if max_profit is not None and max_loss > 0 else None
        strategy = Strategy(
            strategy_type=family,
            thesis=thesis,
            directional_intent=bias,
            target_risk_profile="PREMIUM_ONLY" if family in {StrategyFamily.LONG_CALL, StrategyFamily.LONG_PUT} else "DEFINED_RISK",
            legs=legs,
            expiration=legs[0].expiration,
            quantity=1,
            net_debit=net_debit,
            net_credit=net_credit,
            max_loss=max_loss,
            max_profit=max_profit,
            break_even=break_even,
        )
        metrics = QuantMetrics(
            leg_midpoints=[leg.midpoint for leg in legs],
            max_spread_pct=max(spreads),
            premium=premium,
            net_debit=net_debit,
            net_credit=net_credit,
            max_loss=max_loss,
            max_profit=max_profit,
            break_even=break_even,
            position_quantity=1,
            exposure=max_loss,
            reward_risk=reward_risk,
            scenario_pnl=scenario_pnl,
            data_age_seconds=round(max(0.0, (utc_now() - observed_at).total_seconds()), 3),
            liquidity_passed=max(spreads) <= max_spread_pct,
            greeks_status=greeks_status,
        )
        return strategy, metrics

    @classmethod
    def pnl_at_expiration(cls, legs: list[OptionLeg], underlying_price: float, net_debit: float, net_credit: float) -> float:
        intrinsic = 0.0
        for leg in legs:
            value = max(underlying_price - leg.strike, 0) if leg.option_type == "CALL" else max(leg.strike - underlying_price, 0)
            intrinsic += value * 100 * leg.ratio * (1 if leg.side == "BUY" else -1)
        return round(intrinsic - net_debit + net_credit, 2)

    @staticmethod
    def _payoff_limits(family: StrategyFamily, legs: list[OptionLeg], net_debit: float, net_credit: float) -> tuple[float, float | None, list[float]]:
        if family == StrategyFamily.LONG_CALL:
            return net_debit, None, [round(legs[0].strike + net_debit / 100, 2)]
        if family == StrategyFamily.LONG_PUT:
            return net_debit, round(max(0, legs[0].strike * 100 - net_debit), 2), [round(legs[0].strike - net_debit / 100, 2)]
        if family == StrategyFamily.BULL_CALL_SPREAD:
            width = (legs[1].strike - legs[0].strike) * 100
            return net_debit, round(width - net_debit, 2), [round(legs[0].strike + net_debit / 100, 2)]
        if family == StrategyFamily.BEAR_PUT_SPREAD:
            width = (legs[0].strike - legs[1].strike) * 100
            return net_debit, round(width - net_debit, 2), [round(legs[0].strike - net_debit / 100, 2)]
        put_width = (legs[1].strike - legs[0].strike) * 100
        call_width = (legs[3].strike - legs[2].strike) * 100
        return round(max(put_width, call_width) - net_credit, 2), net_credit, [round(legs[1].strike - net_credit / 100, 2), round(legs[2].strike + net_credit / 100, 2)]


class StressEngine:
    def evaluate(self, strategy: Strategy, quant: QuantMetrics) -> StressReport:
        scenarios = [
            StressScenario(
                name=item.label,
                severity=self._severity(item.pnl, strategy.max_loss),
                pnl=item.pnl,
                breaks_thesis=item.pnl <= -0.8 * strategy.max_loss,
            )
            for item in quant.scenario_pnl
        ]
        critical = sum(item.severity == "CRITICAL" for item in scenarios)
        recommendation = "REJECT" if not quant.liquidity_passed or strategy.max_loss <= 0 else "CAUTION" if critical >= 3 else "PASS"
        return StressReport(
            scenarios=scenarios,
            break_conditions=["Maximum loss threshold reached", "Market evidence becomes stale", "Bid/ask spread exceeds policy"],
            recommendation=recommendation,
        )

    @staticmethod
    def _severity(pnl: float, max_loss: float) -> str:
        if max_loss <= 0 or pnl <= -0.8 * max_loss:
            return "CRITICAL"
        if pnl < 0:
            return "HIGH"
        if pnl == 0:
            return "MEDIUM"
        return "LOW"
