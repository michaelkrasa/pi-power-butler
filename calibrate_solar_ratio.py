#!/usr/bin/env python3
"""
Solar Irradiance to kWh Calibration Tool

This program analyzes historical data to determine the optimal ratio for converting 
daily irradiance (W/m²) to actual solar generation (kWh) for your specific solar system.

USAGE:
    python calibrate_solar_ratio.py           # Full calibration using July 2025 data
    python calibrate_solar_ratio.py --test    # Quick test with recent 2 days
    python calibrate_solar_ratio.py --debug   # Debug MCP data availability

RECOMMENDATIONS:
    - Run this calibration monthly to maintain accuracy as seasons change
    - After any solar system hardware changes (panels, inverters, etc.)
    - If you notice significant discrepancies in solar predictions

The calibration uses:
    - Historical solar generation data from AlphaESS via MCP
    - Historical irradiance data from Open-Meteo weather API
    - Statistical analysis to determine optimal conversion ratio

Last calibration: July 2025 - Ratio: 0.011509 (230x improvement over default)
"""

import asyncio
import datetime
import statistics
from typing import List, Tuple

import openmeteo_requests
import requests_cache
from alphaess.alphaess import alphaess
from retry_requests import retry

from src.config import Settings

settings = Settings()


def get_historical_irradiance(date: datetime.date, lat: float, lon: float, tilt: int, azimuth: int) -> float:
    """Get historical irradiance data for a specific date."""
    # Setup cache and retry
    cache_session = requests_cache.CachedSession(".cache", expire_after=3600)
    retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
    openmeteo = openmeteo_requests.Client(session=retry_session)

    # Use the historical weather API for past dates
    url = "https://historical-forecast-api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "global_tilted_irradiance",
        "start_date": date.isoformat(),
        "end_date": date.isoformat(),
        "tilt": tilt,
        "azimuth": azimuth,
    }

    try:
        responses = openmeteo.weather_api(url, params=params)
        response = responses[0]
        hourly = response.Hourly()
        irradiance_values = hourly.Variables(0).ValuesAsNumpy()

        # Sum all hourly values to get daily total
        daily_irradiance = sum(irradiance_values)
        return float(daily_irradiance)
    except Exception as e:
        print(f"Error getting irradiance for {date}: {e}")
        return 0.0


async def get_historical_solar_generation(date: datetime.date, alpha_client, serial_number) -> float:
    """Get historical solar generation for a specific date using alphaess client."""
    try:
        # Use the alphaess client to get energy data
        power_data = await alpha_client.getOneDateEnergyBySn(serial_number, date.strftime("%Y-%m-%d"))

        # Extract solar generation (epv = energy from photovoltaic)
        if power_data and isinstance(power_data, dict):
            if "epv" in power_data:
                return float(power_data["epv"])

        print(f"No solar generation data found for {date}")
        return 0.0

    except Exception as e:
        print(f"Error getting solar data for {date}: {e}")
        import traceback
        traceback.print_exc()
        return 0.0


async def debug_data(alpha_client, serial_number) -> None:
    """Debug function to understand what MCP data is available."""
    print("🔍 Debug Mode: Testing MCP data availability")

    test_dates = [
        datetime.date.today(),
        datetime.date.today() - datetime.timedelta(days=1),
    ]

    for date in test_dates:
        print(f"\nTesting {date.strftime('%Y-%m-%d')}:")
        try:
            power_data = await alpha_client.getOneDateEnergyBySn(serial_number, date.strftime("%Y-%m-%d"))

            print(power_data)

        except Exception as e:
            print(f"  💥 Exception: {e}")
            import traceback
            traceback.print_exc()


async def calibrate_solar_ratio(test_mode: bool = False, debug: bool = False) -> None:
    """Main calibration function for July 2025."""

    alpha_client = alphaess(appID=settings.alpha_ess_app_id, appSecret=settings.alpha_ess_app_secret)
    print(alpha_client)

    try:
        # Get the system list to find the serial number
        try:
            ess_list = await alpha_client.getESSList()
            if not ess_list or len(ess_list) == 0:
                print("❌ No ESS systems found!")
                return

            # Use the first system's serial number
            serial_number = ess_list[0].get('sysSn')
            if not serial_number:
                print("❌ No serial number found in ESS list!")
                return

            print(f"📡 Using system serial: {serial_number}")

        except Exception as e:
            print(f"❌ Error getting ESS list: {e}")
            return

        if debug:
            await debug_data(alpha_client, serial_number)
            return

        print("🔄 Starting Solar Irradiance to kWh Calibration")

        if test_mode:
            print("🧪 Test mode: Using available recent days...")
            # Try with just today and yesterday for now
            end_date = datetime.date.today()
            start_date = end_date - datetime.timedelta(days=1)
        else:
            print("📅 Analyzing data for July 2025 (up to today)...")
            start_date = datetime.date(2025, 7, 20)  # Start from a more recent date
            end_date = datetime.date.today()

        print(f"Date range: {start_date} to {end_date}")
        print()

        data_points: List[Tuple[float, float]] = []  # (irradiance, generation)

        current_date = start_date
        while current_date <= end_date:
            print(f"Processing {current_date.strftime('%Y-%m-%d')}...", end=" ")

            # Get irradiance data
            irradiance = get_historical_irradiance(
                current_date, settings.lat, settings.lon, settings.tilt, settings.azimuth
            )

            # Get solar generation data
            generation = await get_historical_solar_generation(current_date, alpha_client, serial_number)
            print(f"Generation: {generation} kWh")

            if irradiance > 0 and generation > 0:
                data_points.append((irradiance, generation))
                ratio = generation / irradiance
                print(f"✅ Irradiance: {irradiance:.0f} W/m²·day, Generation: {generation:.2f} kWh, Ratio: {ratio:.6f}")
            else:
                print("❌ No valid data")

            current_date += datetime.timedelta(days=1)

        print()

        if not data_points:
            print("❌ No valid data points found for calibration!")
            return

        # Calculate the mean ratio
        ratios = [gen / irr for irr, gen in data_points]
        mean_ratio = statistics.mean(ratios)

        print(f"Calibrated solar ratio: {mean_ratio:.6f}")
        print(f"Based on {len(data_points)} data points")

    finally:
        # Properly close the client session
        if hasattr(alpha_client, 'session') and alpha_client.session:
            await alpha_client.session.close()


if __name__ == "__main__":
    import sys

    test_mode = "--test" in sys.argv
    debug_mode = "--debug" in sys.argv
    asyncio.run(calibrate_solar_ratio(test_mode=test_mode, debug=debug_mode))
