from functools import lru_cache
import os
from urllib.parse import urlparse

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    log_level: str = "INFO"
    trading_mode: str = "paper"
    live_trading_enabled: bool = False
    execution_enabled: bool = False
    kill_switch_active: bool = False
    oracle_db_path: str = "/tmp/oracle_x.db" if os.getenv("VERCEL") else "oracle_x.db"
    database_url: str = ""

    featherless_api_key: str = ""
    featherless_base_url: str = "https://api.featherless.ai/v1"
    featherless_model_athena: str = "meta-llama/Meta-Llama-3.1-8B-Instruct"
    featherless_model_hades: str = "meta-llama/Meta-Llama-3.1-8B-Instruct"
    featherless_model_hermes: str = "meta-llama/Meta-Llama-3.1-8B-Instruct"
    featherless_model_morpheus: str = "meta-llama/Meta-Llama-3.1-8B-Instruct"
    featherless_timeout_seconds: float = 30
    featherless_max_retries: int = 2

    alpaca_api_key: str = ""
    alpaca_api_secret: str = ""
    alpaca_trading_base_url: str = "https://paper-api.alpaca.markets"
    alpaca_data_base_url: str = "https://data.alpaca.markets"
    alpaca_paper_trade: bool = True
    mcp_server_url: str = ""
    mcp_timeout_seconds: float = 15
    alpaca_toolsets: str = "assets,stock-data,options-data,news"

    risk_approval_ttl_seconds: int = 300
    max_market_data_age_seconds: int = 60
    max_trade_loss: float = 750
    max_position_quantity: int = 1
    max_bid_ask_spread_pct: float = 20

    @model_validator(mode="after")
    def enforce_paper_only(self) -> "Settings":
        if self.trading_mode.lower() != "paper":
            raise ValueError("ORACLE X emergency build supports paper trading only")
        if self.live_trading_enabled:
            raise ValueError("LIVE_TRADING_ENABLED must remain false")
        if not self.alpaca_paper_trade:
            raise ValueError("ALPACA_PAPER_TRADE must remain true")
        if not self.is_paper_endpoint:
            raise ValueError("Alpaca trading URL must be the paper endpoint")
        toolsets = {item.strip() for item in self.alpaca_toolsets.split(",") if item.strip()}
        forbidden = toolsets.intersection({"trading", "watchlists"})
        if forbidden:
            raise ValueError(f"Mutation-capable Alpaca MCP toolsets are forbidden: {sorted(forbidden)}")
        return self

    @property
    def is_paper_endpoint(self) -> bool:
        parsed = urlparse(self.alpaca_trading_base_url)
        return parsed.scheme == "https" and parsed.hostname == "paper-api.alpaca.markets"

    @property
    def alpaca_configured(self) -> bool:
        return bool(self.alpaca_api_key and self.alpaca_api_secret)

    @property
    def featherless_configured(self) -> bool:
        return bool(self.featherless_api_key)

    @property
    def postgres_configured(self) -> bool:
        return self.database_url.startswith(("postgresql://", "postgres://"))

    def model_for(self, role: str) -> str:
        return {
            "ATHENA": self.featherless_model_athena,
            "HADES": self.featherless_model_hades,
            "HERMES": self.featherless_model_hermes,
            "MORPHEUS": self.featherless_model_morpheus,
        }[role]


@lru_cache
def get_settings() -> Settings:
    return Settings()
