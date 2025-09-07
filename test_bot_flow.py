#!/usr/bin/env python3
"""
Test script to simulate the exact bot flow for debugging Raspberry Pi issues.
"""

import asyncio
import datetime
import logging
from src.config import Settings
from src.price_fetcher import PriceFetcher
from src.weather import get_solar_forecast
from src.cache import EnergyDataCache
from src.plotting import create_price_graph, create_irradiance_graph

# Set up detailed logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('test_bot_flow.log')
    ]
)

async def test_bot_flow():
    """Test the exact flow the bot uses for data fetching."""
    logger = logging.getLogger(__name__)
    
    print("🧪 Testing Bot Flow for Raspberry Pi Debugging")
    print("=" * 50)
    
    # Initialize settings
    settings = Settings()
    logger.info(f"Settings loaded: timezone={settings.timezone}, lat={settings.lat}, lon={settings.lon}")
    
    # Test date (today)
    target_date = datetime.date.today()
    day_label = "today"
    
    print(f"📅 Testing date: {target_date}")
    print(f"🌍 Timezone: {settings.timezone}")
    print(f"📍 Location: {settings.lat}, {settings.lon}")
    print(f"☀️ Solar: tilt={settings.tilt}, azimuth={settings.azimuth}")
    print()
    
    # Initialize cache
    logger.info("Initializing cache")
    cache = EnergyDataCache()
    
    # Clean up old cache entries first
    logger.info("Cleaning up old cache entries")
    cache.cleanup_old_data()
    
    # Try to get data from cache first
    logger.info(f"Checking cache for {target_date}")
    cached_data = cache.get_cached_data(target_date)
    
    if cached_data:
        print("✅ Cache hit - using cached data")
        prices = cached_data['prices']
        irradiance = cached_data['irradiance']
        logger.info(f"Using cached data: {len(prices)} prices, {len(irradiance)} irradiance")
    else:
        print("❌ Cache miss - fetching fresh data")
        logger.info(f"Starting fresh data fetch for {day_label}")
        
        try:
            # Fetch prices
            print("💰 Fetching prices...")
            logger.info(f"Fetching prices for {target_date}")
            price_fetcher = PriceFetcher()
            prices = await price_fetcher.fetch_prices_for_date(target_date)
            logger.info(f"Successfully fetched {len(prices)} price points for {day_label}")
            print(f"✅ Got {len(prices)} price points")

            # Fetch irradiance
            print("☀️ Fetching irradiance...")
            logger.info(f"Fetching irradiance for {target_date} with timezone {settings.timezone}")
            irradiance = get_solar_forecast(
                settings.lat, settings.lon, settings.tilt, settings.azimuth, target_date, settings.timezone
            )
            logger.info(f"Successfully fetched {len(irradiance)} irradiance points for {day_label}")
            print(f"✅ Got {len(irradiance)} irradiance points")

            # Cache the data (no graphs)
            print("💾 Caching data...")
            logger.info(f"Caching data for {target_date}")
            cache.cache_data(target_date, prices, irradiance)
            logger.info(f"Successfully cached data for {day_label}")
            print("✅ Data cached")

        except Exception as fetch_error:
            logger.error(f"Error during data fetch for {day_label}: {fetch_error}", exc_info=True)
            print(f"❌ Error during data fetch: {fetch_error}")
            return False

    # Calculate solar production estimate
    daily_solar_estimate = sum(irradiance) * settings.solar_ratio
    logger.info(f"Calculated solar estimate: {daily_solar_estimate:.1f} kWh for {day_label}")
    print(f"⚡ Solar estimate: {daily_solar_estimate:.1f} kWh")
    
    # Generate graphs
    print("📊 Generating graphs...")
    try:
        logger.info(f"Generating price graph for {day_label}")
        price_graph = create_price_graph(prices)
        logger.info(f"Successfully generated price graph ({len(price_graph)} bytes)")
        print(f"✅ Price graph: {len(price_graph)} bytes")
    except Exception as e:
        logger.error(f"Error generating price graph: {e}", exc_info=True)
        print(f"❌ Error generating price graph: {e}")
        return False

    try:
        logger.info(f"Generating irradiance graph for {day_label}")
        irradiance_graph = create_irradiance_graph(irradiance)
        logger.info(f"Successfully generated irradiance graph ({len(irradiance_graph)} bytes)")
        print(f"✅ Irradiance graph: {len(irradiance_graph)} bytes")
    except Exception as e:
        logger.error(f"Error generating irradiance graph: {e}", exc_info=True)
        print(f"❌ Error generating irradiance graph: {e}")
        return False

    print()
    print("🎉 Bot flow test completed successfully!")
    print(f"📈 Price range: {min(prices):.1f} to {max(prices):.1f} €/MWh")
    print(f"☀️ Irradiance range: {min(irradiance):.1f} to {max(irradiance):.1f} W/m²")
    print(f"⚡ Expected generation: {daily_solar_estimate:.1f} kWh")
    
    return True

if __name__ == "__main__":
    success = asyncio.run(test_bot_flow())
    if success:
        print("\n✅ All tests passed!")
    else:
        print("\n❌ Tests failed - check logs for details")
