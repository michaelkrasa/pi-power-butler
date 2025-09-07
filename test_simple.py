#!/usr/bin/env python3
"""
Simple test to verify the bot functionality works.
"""

import asyncio
import datetime
from src.main import generate_simple_recommendation
from src.config import Settings

def test_recommendation():
    """Test the recommendation generation logic."""
    # Test low battery scenario
    soc = 25.0
    prices = [15.0, 12.0, 8.0, 6.0, 10.0, 18.0] * 4  # 24 hours
    irradiance = [0, 0, 0, 0, 0, 100] * 4  # 24 hours
    
    rec = generate_simple_recommendation(soc, prices, irradiance)
    
    assert "reasoning" in rec, "Recommendation should have reasoning"
    assert "telegram_draft" in rec, "Recommendation should have telegram draft"
    
    # With 25% SoC, should recommend charging (check message content)
    assert "CHARGE" in rec["telegram_draft"], "Should recommend charging at 25% SoC"
    assert "Current Battery: 25%" in rec["telegram_draft"], "Should show current battery level"
    
    print("✅ Low battery test passed")
    
    # Test high battery scenario
    soc = 80.0
    rec = generate_simple_recommendation(soc, prices, irradiance)
    
    # With 80% SoC, should not recommend charging
    assert "No charging needed" in rec["telegram_draft"], "Should not recommend charging at 80% SoC"
    
    print("✅ High battery test passed")

async def test_data_fetching():
    """Test data fetching components."""
    from src.price_fetcher import PriceFetcher
    from src.weather import get_solar_forecast
    from src.cache import EnergyDataCache
    from src.plotting import create_price_graph, create_irradiance_graph
    
    settings = Settings()
    target_date = datetime.date.today()
    
    print("🧪 Testing data fetching components...")
    
    # Test price fetching
    price_fetcher = PriceFetcher()
    prices = await price_fetcher.fetch_prices_for_date(target_date)
    assert len(prices) == 24, f"Expected 24 price points, got {len(prices)}"
    print("✅ Price fetching works")
    
    # Test irradiance fetching
    irradiance = get_solar_forecast(
        settings.lat, settings.lon, settings.tilt, settings.azimuth, 
        target_date, settings.timezone
    )
    assert len(irradiance) == 24, f"Expected 24 irradiance points, got {len(irradiance)}"
    print("✅ Irradiance fetching works")
    
    # Test caching
    cache = EnergyDataCache()
    cache.cleanup_old_data()
    cache.cache_data(target_date, prices, irradiance)
    cached_data = cache.get_cached_data(target_date)
    assert cached_data is not None, "Data should be cached"
    print("✅ Caching works")
    
    # Test graph generation
    price_graph = create_price_graph(prices)
    irradiance_graph = create_irradiance_graph(irradiance)
    assert isinstance(price_graph, bytes), "Price graph should be bytes"
    assert isinstance(irradiance_graph, bytes), "Irradiance graph should be bytes"
    print("✅ Graph generation works")
    
    print("🎉 All data fetching tests passed!")

if __name__ == "__main__":
    print("🧪 Running Pi Power Butler Tests")
    print("=" * 40)
    
    # Test recommendation logic
    test_recommendation()
    
    # Test data fetching
    asyncio.run(test_data_fetching())
    
    print("\n✅ All tests passed! The bot should work correctly.")
