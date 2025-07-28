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

import datetime
import statistics
from typing import List, Tuple

import openmeteo_requests
import requests_cache
from retry_requests import retry

# Import MCP tools (assuming we're in the same project structure)
from src.mcp_alphaess import execute_mcp_tool
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


def get_historical_solar_generation(date: datetime.date) -> float:
    """Get historical solar generation for a specific date using MCP."""
    try:
        power_data = execute_mcp_tool("mcp_alpha-ess-mcp_get_one_day_power_data", {
            "query_date": date.strftime("%Y-%m-%d")
        })
        
        # Handle wrapped MCP response format
        if isinstance(power_data, dict) and power_data.get('type') == 'text':
            import json
            power_data = json.loads(power_data['text'])
        
        # Navigate to the solar section and extract total_generation_kwh
        if power_data.get("success") and "structured" in power_data:
            structured = power_data["structured"]
            if "summary" in structured and "solar" in structured["summary"]:
                solar_summary = structured["summary"]["solar"]
                if "total_generation_kwh" in solar_summary:
                    return float(solar_summary["total_generation_kwh"])
        
        print(f"No solar generation data found for {date}")
        return 0.0
        
    except Exception as e:
        print(f"Error getting solar data for {date}: {e}")
        import traceback
        traceback.print_exc()
        return 0.0


def debug_mcp_data() -> None:
    """Debug function to understand what MCP data is available."""
    print("🔍 Debug Mode: Testing MCP data availability")
    
    test_dates = [
        datetime.date.today(),
        datetime.date.today() - datetime.timedelta(days=1),
    ]
    
    for date in test_dates:
        print(f"\nTesting {date.strftime('%Y-%m-%d')}:")
        try:
            power_data = execute_mcp_tool("mcp_alpha-ess-mcp_get_one_day_power_data", {
                "query_date": date.strftime("%Y-%m-%d")
            })
            
            # Handle wrapped MCP response format
            if isinstance(power_data, dict) and power_data.get('type') == 'text':
                import json
                power_data = json.loads(power_data['text'])
            
            if power_data.get("success"):
                print(f"  ✅ Success: {power_data.get('message', 'No message')}")
                if "structured" in power_data and "summary" in power_data["structured"]:
                    solar_data = power_data["structured"]["summary"].get("solar", {})
                    generation = solar_data.get("total_generation_kwh", 0)
                    print(f"  📊 Solar generation: {generation} kWh")
                else:
                    print("  ❌ No structured summary data found")
            else:
                print(f"  ❌ Failed: {power_data.get('message', 'Unknown error')}")
                
        except Exception as e:
            print(f"  💥 Exception: {e}")
            import traceback
            traceback.print_exc()


def calibrate_solar_ratio(test_mode: bool = False, debug: bool = False) -> None:
    """Main calibration function for July 2025."""
    
    if debug:
        debug_mcp_data()
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
        generation = get_historical_solar_generation(current_date)
        
        if irradiance > 0 and generation > 0:
            data_points.append((irradiance, generation))
            ratio = generation / irradiance
            print(f"✅ Irradiance: {irradiance:.0f} W/m²·day, Generation: {generation:.2f} kWh, Ratio: {ratio:.6f}")
        else:
            print("❌ No valid data")
        
        current_date += datetime.timedelta(days=1)
    
    print()
    print("📊 Analysis Results:")
    print("=" * 50)
    
    if not data_points:
        print("❌ No valid data points found for calibration!")
        print("\n💡 Try running with --debug to see what MCP data is available")
        return
    
    # Calculate ratios and statistics
    ratios = [gen / irr for irr, gen in data_points]
    
    mean_ratio = statistics.mean(ratios)
    median_ratio = statistics.median(ratios)
    stdev_ratio = statistics.stdev(ratios) if len(ratios) > 1 else 0
    min_ratio = min(ratios)
    max_ratio = max(ratios)
    
    print(f"📈 Data Points Collected: {len(data_points)}")
    print(f"📊 Ratio Statistics:")
    print(f"   • Mean:     {mean_ratio:.6f}")
    print(f"   • Median:   {median_ratio:.6f}")
    print(f"   • Std Dev:  {stdev_ratio:.6f}")
    print(f"   • Min:      {min_ratio:.6f}")
    print(f"   • Max:      {max_ratio:.6f}")
    print()
    
    # Test current ratio vs recommended
    current_ratio = 0.05 / 1000  # Current ratio in main.py
    print(f"🔍 Comparison:")
    print(f"   • Current ratio in code: {current_ratio:.6f}")
    print(f"   • Recommended ratio:     {mean_ratio:.6f}")
    print(f"   • Improvement factor:    {mean_ratio / current_ratio:.1f}x")
    print()
    
    # Generate code suggestion
    print("💡 Suggested Code Update:")
    print("-" * 30)
    print(f"# Replace this line in src/main.py:")
    print(f"daily_solar_estimate = sum(irradiance) * 0.05 / 1000")
    print(f"# With:")
    print(f"daily_solar_estimate = sum(irradiance) * {mean_ratio:.6f}  # Calibrated from July 2025 data")
    print()
    
    # Validation examples
    print("✅ Validation Examples:")
    print("-" * 20)
    for i, (irradiance, actual_gen) in enumerate(data_points[:5]):  # Show first 5 examples
        predicted_old = irradiance * current_ratio
        predicted_new = irradiance * mean_ratio
        print(f"Day {i+1}: Actual={actual_gen:.2f} kWh, Old={predicted_old:.2f} kWh, New={predicted_new:.2f} kWh")


if __name__ == "__main__":
    import sys
    test_mode = "--test" in sys.argv
    debug_mode = "--debug" in sys.argv
    calibrate_solar_ratio(test_mode=test_mode, debug=debug_mode) 