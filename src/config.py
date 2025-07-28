from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Project configuration loaded from .env file."""

    lat: float = 0.0
    lon: float = 0.0
    tilt: int = 0
    azimuth: int = 0
    alpha_mcp_url: str = "http://127.0.0.1:8000"
    telegram_bot_token: str = ""
    solar_ratio: float = 0.011509

    model_config = SettingsConfigDict(env_file=".env")
