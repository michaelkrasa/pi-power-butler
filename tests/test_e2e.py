"""
End-to-end tests for the Pi Power Butler bot.

These tests verify the complete data flow from API calls to bot responses,
including caching, graph generation, and Telegram bot functionality.
"""

import pytest
import asyncio
import datetime
import tempfile
import os
from unittest.mock import patch, MagicMock, AsyncMock
from src.config import Settings
from src.price_fetcher import PriceFetcher
from src.weather import get_solar_forecast
from src.cache import EnergyDataCache
from src.plotting import create_price_graph, create_irradiance_graph
from src.telegram_bot import TelegramBot
from src.main import generate_simple_recommendation


class TestE2EDataFlow:
    """Test the complete data fetching and processing flow."""
    
    @pytest.fixture
    def temp_cache_db(self):
        """Create a temporary cache database for testing."""
        with tempfile.NamedTemporaryFile(suffix='.sqlite', delete=False) as f:
            temp_db = f.name
        
        # Override the cache database path by monkeypatching the class
        original_init = EnergyDataCache.__init__
        def mock_init(self, db_path=".cache.sqlite"):
            original_init(self, temp_db)
        EnergyDataCache.__init__ = mock_init
        
        yield temp_db
        
        # Cleanup
        EnergyDataCache.__init__ = original_init
        if os.path.exists(temp_db):
            os.unlink(temp_db)
    
    @pytest.mark.asyncio
    async def test_fresh_data_fetch_flow(self, temp_cache_db):
        """Test complete flow with fresh data (no cache)."""
        settings = Settings()
        target_date = datetime.date.today()
        
        # Initialize cache
        cache = EnergyDataCache()
        cache.cleanup_old_data()
        
        # Ensure no cached data
        cached_data = cache.get_cached_data(target_date)
        assert cached_data is None, "Cache should be empty for fresh data test"
        
        # Test price fetching
        price_fetcher = PriceFetcher()
        prices = await price_fetcher.fetch_prices_for_date(target_date)
        
        assert len(prices) == 24, f"Expected 24 price points, got {len(prices)}"
        assert all(isinstance(p, (int, float)) for p in prices), "All prices should be numeric"
        
        # Test irradiance fetching
        irradiance = get_solar_forecast(
            settings.lat, settings.lon, settings.tilt, settings.azimuth, 
            target_date, settings.timezone
        )
        
        assert len(irradiance) == 24, f"Expected 24 irradiance points, got {len(irradiance)}"
        assert all(isinstance(i, (int, float)) for i in irradiance), "All irradiance values should be numeric"
        assert all(i >= 0 for i in irradiance), "All irradiance values should be non-negative"
        
        # Test caching
        cache.cache_data(target_date, prices, irradiance)
        cached_data = cache.get_cached_data(target_date)
        
        assert cached_data is not None, "Data should be cached after storing"
        assert cached_data['prices'] == prices, "Cached prices should match original"
        assert cached_data['irradiance'] == irradiance, "Cached irradiance should match original"
        
        # Test graph generation
        price_graph = create_price_graph(prices)
        irradiance_graph = create_irradiance_graph(irradiance)
        
        assert isinstance(price_graph, bytes), "Price graph should be bytes"
        assert isinstance(irradiance_graph, bytes), "Irradiance graph should be bytes"
        assert len(price_graph) > 1000, "Price graph should be substantial"
        assert len(irradiance_graph) > 1000, "Irradiance graph should be substantial"
        
        # Test solar production calculation
        daily_solar_estimate = sum(irradiance) * settings.solar_ratio
        assert daily_solar_estimate > 0, "Solar estimate should be positive"
        assert isinstance(daily_solar_estimate, (int, float)), "Solar estimate should be numeric"
    
    @pytest.mark.asyncio
    async def test_cached_data_flow(self, temp_cache_db):
        """Test flow with cached data."""
        settings = Settings()
        target_date = datetime.date.today()
        
        # Initialize cache and store test data
        cache = EnergyDataCache()
        cache.cleanup_old_data()
        
        test_prices = [10.0, 15.0, 20.0] * 8  # 24 prices
        test_irradiance = [0.0, 50.0, 100.0] * 8  # 24 irradiance values
        
        cache.cache_data(target_date, test_prices, test_irradiance)
        
        # Test retrieving cached data
        cached_data = cache.get_cached_data(target_date)
        assert cached_data is not None, "Should retrieve cached data"
        assert cached_data['prices'] == test_prices, "Cached prices should match"
        assert cached_data['irradiance'] == test_irradiance, "Cached irradiance should match"
        
        # Test graph generation from cached data
        price_graph = create_price_graph(cached_data['prices'])
        irradiance_graph = create_irradiance_graph(cached_data['irradiance'])
        
        assert isinstance(price_graph, bytes), "Price graph should be bytes"
        assert isinstance(irradiance_graph, bytes), "Irradiance graph should be bytes"
    
    def test_cache_cleanup(self, temp_cache_db):
        """Test cache cleanup removes old data."""
        cache = EnergyDataCache()
        
        # Add data for yesterday, today, and tomorrow
        yesterday = datetime.date.today() - datetime.timedelta(days=1)
        today = datetime.date.today()
        tomorrow = datetime.date.today() + datetime.timedelta(days=1)
        
        cache.cache_data(yesterday, [1.0] * 24, [1.0] * 24)
        cache.cache_data(today, [2.0] * 24, [2.0] * 24)
        cache.cache_data(tomorrow, [3.0] * 24, [3.0] * 24)
        
        # Cleanup should remove yesterday's data
        cache.cleanup_old_data()
        
        assert cache.get_cached_data(yesterday) is None, "Yesterday's data should be removed"
        assert cache.get_cached_data(today) is not None, "Today's data should remain"
        assert cache.get_cached_data(tomorrow) is not None, "Tomorrow's data should remain"
    
    def test_simple_recommendation_logic(self):
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
        
        # Test high battery scenario
    soc = 80.0
        rec = generate_simple_recommendation(soc, prices, irradiance)
        
        # With 80% SoC, should not recommend charging
        assert "No charging needed" in rec["telegram_draft"], "Should not recommend charging at 80% SoC"
    
    @pytest.mark.asyncio
    async def test_telegram_bot_integration(self, temp_cache_db):
        """Test Telegram bot integration with mocked bot."""
        # Mock the Telegram bot
        mock_bot = MagicMock(spec=TelegramBot)
        mock_bot.send_message = AsyncMock()
        
        # Create a real bot instance for testing
        bot = TelegramBot()
        bot.bot = mock_bot
        
        # Test the bot's data fetching and sending
        target_date = datetime.date.today()
        
        # Mock the cache to return test data
        with patch.object(bot.cache, 'get_cached_data', return_value=None):
            with patch.object(bot.cache, 'cache_data'):
                with patch('src.price_fetcher.PriceFetcher.fetch_prices_for_date', 
                          return_value=[10.0] * 24):
                    with patch('src.weather.get_solar_forecast', 
                              return_value=[100.0] * 24):
                        with patch('src.plotting.create_price_graph', 
                                  return_value=b"price_graph"):
                            with patch('src.plotting.create_irradiance_graph', 
                                      return_value=b"irradiance_graph"):
                                
                                # Test the bot's data fetching method
                                await bot._fetch_and_send_data(mock_bot, target_date, "today")
                                
                                # Verify the bot sent messages
                                assert mock_bot.send_message.call_count >= 1, "Bot should send at least one message"


class TestE2EIntegration:
    """Integration tests for the complete system."""
    
    @pytest.mark.asyncio
    async def test_complete_bot_flow_simulation(self):
        """Simulate the complete bot flow without external dependencies."""
        # This test simulates what happens when a user sends "T" to the bot
        
        # Mock all external dependencies
        with patch('src.price_fetcher.PriceFetcher.fetch_prices_for_date', 
                  return_value=[10.0, 15.0, 20.0] * 8) as mock_prices:
            with patch('src.weather.get_solar_forecast', 
                      return_value=[0.0, 50.0, 100.0] * 8) as mock_weather:
                with patch('src.plotting.create_price_graph', 
                          return_value=b"price_graph_bytes") as mock_price_graph:
                    with patch('src.plotting.create_irradiance_graph', 
                              return_value=b"irradiance_graph_bytes") as mock_irradiance_graph:
                        
                        # Test the complete flow
                        settings = Settings()
                        target_date = datetime.date.today()
                        
                        # Simulate cache miss
                        cache = EnergyDataCache()
                        cache.cleanup_old_data()
                        
                        # Fetch data (mocked)
                        prices = await PriceFetcher().fetch_prices_for_date(target_date)
                        irradiance = get_solar_forecast(
                            settings.lat, settings.lon, settings.tilt, settings.azimuth,
                            target_date, settings.timezone
                        )
                        
                        # Cache data
                        cache.cache_data(target_date, prices, irradiance)
                        
                        # Generate graphs (mocked)
                        price_graph = create_price_graph(prices)
                        irradiance_graph = create_irradiance_graph(irradiance)
                        
                        # Verify all components worked
                        assert len(prices) == 24, "Should have 24 price points"
                        assert len(irradiance) == 24, "Should have 24 irradiance points"
                        assert isinstance(price_graph, bytes), "Price graph should be bytes"
                        assert isinstance(irradiance_graph, bytes), "Irradiance graph should be bytes"
                        
                        # Verify mocks were called
                        mock_prices.assert_called_once()
                        mock_weather.assert_called_once()
                        mock_price_graph.assert_called_once()
                        mock_irradiance_graph.assert_called_once()
    
    def test_timezone_handling(self):
        """Test that timezone is properly handled in API calls."""
        settings = Settings()
        target_date = datetime.date.today()
        
        # Test that timezone is passed correctly to weather API
        with patch('src.weather.openmeteo_requests.Client') as mock_client:
            mock_response = MagicMock()
            mock_response.hourly().global_tilted_irradiance().values = [100.0] * 24
            mock_client.return_value.weather_api.return_value = [mock_response]
            
            # This should not raise an exception
            result = get_solar_forecast(
                settings.lat, settings.lon, settings.tilt, settings.azimuth,
                target_date, settings.timezone
            )
            
            assert len(result) == 24, "Should return 24 irradiance values"
            
            # Verify the API was called with timezone parameter
            mock_client.return_value.weather_api.assert_called_once()
            call_args = mock_client.return_value.weather_api.call_args
            assert 'timezone' in call_args[1]['params'], "API call should include timezone parameter"
            assert call_args[1]['params']['timezone'] == settings.timezone, "Timezone should match settings"