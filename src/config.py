from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Project configuration loaded from .env file."""

    lat: float = 0.0
    lon: float = 0.0
    tilt: int = 0
    azimuth: int = 0
    solar_ratio: float = 0.0  # Calibrated from July 2025 data using calibrate_solar_ratio.py
    timezone: str = "Europe/Berlin"  # Timezone for consistent date handling
    telegram_bot_token: str = ""
    alpha_ess_app_id: str = ""
    alpha_ess_app_secret: str = ""

    model_config = SettingsConfigDict(env_file=".env")
