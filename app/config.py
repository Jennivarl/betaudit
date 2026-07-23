"""Runtime configuration, loaded from environment / .env."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "dev"
    database_url: str = "sqlite:///./resolution_layer.db"

    # Admin bearer used to mint API keys via POST /admin/keys.
    # Empty in dev => admin routes are open locally; MUST be set in prod.
    admin_token: str = ""

    # LLM (OpenAI)
    openai_api_key: str = ""
    llm_model: str = "gpt-4o"

    # Polymarket data sources
    polymarket_gamma_url: str = "https://gamma-api.polymarket.com"
    polymarket_clob_url: str = "https://clob.polymarket.com"

    # x402 pay-per-call (Phase 3). Disabled by default => endpoint is free.
    # mode: "simulate" verifies/settles locally (no chain, for dev/tests);
    #       "live" calls the OKX facilitator and settles on X Layer.
    x402_enabled: bool = False
    x402_mode: str = "simulate"
    x402_price_usdt: str = "0.05"          # human units, per call
    x402_network: str = "eip155:196"       # X Layer mainnet (facilitator only advertises this)
    x402_asset: str = "0x779Ded0c9e1022225f8E0630b35a9b54bE713736"  # USDT0
    x402_asset_decimals: int = 6
    x402_pay_to: str = ""                  # seller receiving address (required when live)
    x402_max_timeout_seconds: int = 120
    okx_base_url: str = "https://www.web3.okx.com"  # facilitator base
    okx_facilitator_prefix: str = ""       # optional path prefix before /verify,/settle

    # Oracle monitor (Phase 4). Off by default so tests/dev don't spawn the loop.
    monitor_enabled: bool = False
    monitor_interval_seconds: int = 300
    monitor_webhook_timeout_seconds: float = 10.0

    # Redis (Phase 7). Empty URL => caching, rate-limiting, and pub/sub all no-op
    # (graceful): the service runs identically without Redis, just uncached.
    redis_url: str = ""
    cache_market_ttl_seconds: int = 3600      # raw market/oracle data
    cache_eval_ttl_seconds: int = 900         # LLM audit output
    rate_limit_enabled: bool = True
    rate_limit_per_minute: int = 60           # per API key
    live_audits_channel: str = "pubsub:live_audits"

    # Public demo-key minting for the web console (so admin can stay locked in
    # prod). IP-throttled via Redis. Set demo_key_enabled=false to disable.
    demo_key_enabled: bool = True
    demo_key_per_minute: int = 5              # per client IP

    # Telegram bot (Phase 6). Webhook mode on the existing web service.
    telegram_bot_token: str = ""
    telegram_webhook_secret: str = ""   # verifies inbound webhook calls (optional)
    public_base_url: str = "https://betauditmcp.xyz"  # for links in bot replies


@lru_cache
def get_settings() -> Settings:
    return Settings()
