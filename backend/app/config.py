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
    featherless_temperature: float = 0.2
    featherless_allowed_hosts: str = "api.featherless.ai"
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
    alpaca_min_options_level: int = 3
    mcp_server_url: str = ""
    mcp_timeout_seconds: float = 15
    alpaca_toolsets: str = "assets,stock-data,options-data,news"
    mcp_allowed_hosts: str = "localhost,127.0.0.1"

    risk_approval_ttl_seconds: int = 300
    max_market_data_age_seconds: int = 60
    max_trade_loss: float = 750
    max_position_quantity: int = 1
    max_bid_ask_spread_pct: float = 20
    max_portfolio_exposure: float = 5000
    max_symbol_exposure: float = 1500
    max_open_trades: int = 3
    min_reward_risk: float = 0.25
    min_days_to_expiration: int = 7
    max_days_to_expiration: int = 60

    jwt_secret: str = ""
    cors_origins: str = ""

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
        if not self.is_data_endpoint:
            raise ValueError("Alpaca data URL must be the official data endpoint")
        self._validate_featherless_host()
        self._validate_mcp_configuration()
        toolsets = {item.strip() for item in self.alpaca_toolsets.split(",") if item.strip()}
        forbidden = toolsets.intersection({"trading", "watchlists", "account", "locates"})
        if forbidden:
            raise ValueError(f"Mutation-capable Alpaca MCP toolsets are forbidden: {sorted(forbidden)}")
        return self

    @property
    def is_paper_endpoint(self) -> bool:
        parsed = urlparse(self.alpaca_trading_base_url)
        return parsed.scheme == "https" and parsed.hostname == "paper-api.alpaca.markets"

    @property
    def is_data_endpoint(self) -> bool:
        parsed = urlparse(self.alpaca_data_base_url)
        return parsed.scheme == "https" and parsed.hostname == "data.alpaca.markets"

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    def _validate_featherless_host(self) -> None:
        parsed = urlparse(self.featherless_base_url)
        allowed = {item.strip().lower() for item in self.featherless_allowed_hosts.split(",") if item.strip()}
        if parsed.scheme != "https":
            raise ValueError("Featherless base URL must use HTTPS")
        if parsed.hostname not in allowed:
            raise ValueError("Featherless base URL host is not approved")

    def _validate_mcp_configuration(self) -> None:
        if not self.mcp_server_url:
            return
        parsed = urlparse(self.mcp_server_url)
        allowed = {item.strip().lower() for item in self.mcp_allowed_hosts.split(",") if item.strip()}
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("MCP server URL must be HTTP(S)")
        if parsed.scheme != "https" and parsed.hostname not in {"localhost", "127.0.0.1"}:
            raise ValueError("Non-HTTPS MCP endpoints must be local/private")
        if allowed and parsed.hostname not in allowed:
            raise ValueError("MCP server URL host is not approved")

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
