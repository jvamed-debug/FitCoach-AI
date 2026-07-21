from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Literal


class Settings(BaseSettings):
    # Supabase
    supabase_url: str
    supabase_anon_key: str
    supabase_service_key: str
    supabase_jwt_secret: str
    database_url: str

    # Criptografia
    db_encryption_key: str

    # Auth
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440

    # Strava
    strava_client_id: str = ""
    strava_client_secret: str = ""
    strava_redirect_uri: str = "http://localhost:3000/auth/callback/strava"
    strava_webhook_verify_token: str = ""

    # TrainingPeaks
    tp_client_id: str = ""
    tp_client_secret: str = ""
    tp_redirect_uri: str = "http://localhost:3000/auth/callback/trainingpeaks"

    # AI
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    default_ai_provider: Literal["anthropic", "openai"] = "anthropic"
    anthropic_model: str = "claude-sonnet-4-6"
    openai_model: str = "gpt-4o"

    # Email
    resend_api_key: str = ""
    from_email: str = "noreply@fitcoachai.com"

    # Monitoring
    sentry_dsn: str = ""
    sentry_traces_sample_rate: float = 0.1  # 10% of transactions in prod

    # Push Notifications (VAPID)
    # Generate with: python -c "from py_vapid import Vapid; v=Vapid(); v.generate_keys(); print(v.private_key, v.public_key)"
    vapid_private_key: str = ""
    vapid_public_key: str = ""
    vapid_subject: str = "mailto:noreply@fitcoachai.com"

    # Stripe
    stripe_secret_key: str = ""
    stripe_publishable_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_starter: str = ""   # Stripe Price ID for Starter plan
    stripe_price_pro: str = ""       # Stripe Price ID for Pro plan
    stripe_price_elite: str = ""     # Stripe Price ID for Elite plan

    # App
    app_env: Literal["development", "production"] = "development"
    frontend_url: str = "http://localhost:3000"
    backend_url: str = "http://localhost:8000"

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
