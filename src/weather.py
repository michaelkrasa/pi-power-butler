"""Module for fetching solar irradiance forecasts."""

import datetime

import openmeteo_requests
import requests_cache
from retry_requests import retry


def get_solar_forecast(lat: float, lon: float, tilt: int, azimuth: int) -> list[float]:
    """Fetch tomorrow's hourly global tilted irradiance forecast from Open-Meteo.

    Args:
        lat: Latitude of the location.
        lon: Longitude of the location.
        tilt: Solar panel tilt angle.
        azimuth: Solar panel azimuth angle.

    Returns:
        List of 24 hourly irradiance values in W/m² for tomorrow.
    """
    # Setup cache and retry
    cache_session = requests_cache.CachedSession(".cache", expire_after=3600)
    retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
    openmeteo = openmeteo_requests.Client(session=retry_session)

    tomorrow = datetime.date.today() + datetime.timedelta(days=1)

    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "global_tilted_irradiance",
        "start_date": tomorrow.isoformat(),
        "end_date": tomorrow.isoformat(),
        "tilt": tilt,
        "azimuth": azimuth,
    }

    responses = openmeteo.weather_api(url, params=params)
    response = responses[0]

    hourly = response.Hourly()
    irradiance_values = hourly.Variables(0).ValuesAsNumpy()

    return irradiance_values.tolist()
