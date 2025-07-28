import pytest
from unittest.mock import patch, MagicMock
import datetime
from src.main import generate_simple_recommendation, nightly_task
from src.mcp_alphaess import execute_mcp_tool
from src.telegram_bot import TelegramBot
import asyncio
import json

@pytest.mark.asyncio
async def test_e2e_simple_recommendation(mocker):
    """E2E test: Simulate flow with simple rule-based recommendation."""

    # Mock external fetches
    mocker.patch("src.price_fetcher.PriceFetcher.fetch_prices_for_date", return_value=[10.0] * 24)
    mocker.patch("src.weather.get_solar_forecast", return_value=[100.0] * 24)
    mocker.patch("src.main.create_price_graph", return_value=b"price_graph")
    mocker.patch("src.main.create_irradiance_graph", return_value=b"irradiance_graph")

    # Mock initial SoC fetch - simulate low battery requiring charging
    mock_execute = mocker.patch("src.main.execute_mcp_tool", side_effect=lambda name, params: {"data": {"soc": 25.0}} if name == "mcp_alpha-ess-mcp_get_last_power_data" else {"success": True})

    # Mock TelegramBot
    mock_bot = MagicMock(spec=TelegramBot)
    
    # Run the nightly task
    await nightly_task(mock_bot)

    # Assertions
    mock_bot.send_recommendation.assert_called_once()
    
    # Check that the telegram message was sent (first argument of send_recommendation call)
    call_args = mock_bot.send_recommendation.call_args[0]
    telegram_message = call_args[0]
    
    # Verify the telegram message contains expected content
    assert "Energy Update for Tomorrow" in telegram_message
    assert "Current Battery: 25%" in telegram_message
    assert "CHARGE" in telegram_message  # Should recommend charging at 25%
    
    # Verify tool call was executed for charging
    mock_execute.assert_any_call(
        "mcp_alpha-ess-mcp_get_last_power_data", {}
    )
    
    # Check that a charging tool call was made (because SoC is 25%, below 30% threshold)
    charging_calls = [call for call in mock_execute.call_args_list 
                     if call[0][0] == "mcp_alpha-ess-mcp_set_battery_charge"]
    assert len(charging_calls) == 1
    
    # Verify charging parameters
    charging_params = charging_calls[0][0][1]
    assert charging_params["enabled"] == True
    assert charging_params["charge_cutoff_soc"] == 100


def test_generate_simple_recommendation_low_battery():
    """Test simple recommendation logic with low battery."""
    soc = 25.0
    prices = [15.0, 12.0, 8.0, 6.0, 10.0, 18.0] * 4  # 24 hours of prices
    irradiance = [0, 0, 0, 0, 0, 100] * 4  # 24 hours of irradiance
    
    rec = generate_simple_recommendation(soc, prices, irradiance)
    
    assert "reasoning" in rec
    assert "telegram_draft" in rec  
    assert "tool_calls" in rec
    assert len(rec["tool_calls"]) == 1  # Should recommend charging
    assert rec["tool_calls"][0]["name"] == "mcp_alpha-ess-mcp_set_battery_charge"
    assert rec["tool_calls"][0]["parameters"]["enabled"] == True


def test_generate_simple_recommendation_high_battery():
    """Test simple recommendation logic with high battery."""
    soc = 80.0
    prices = [15.0, 12.0, 8.0, 6.0, 10.0, 18.0] * 4  # 24 hours of prices
    irradiance = [0, 0, 0, 0, 0, 100] * 4  # 24 hours of irradiance
    
    rec = generate_simple_recommendation(soc, prices, irradiance)
    
    assert "reasoning" in rec
    assert "telegram_draft" in rec
    assert "tool_calls" in rec
    assert len(rec["tool_calls"]) == 0  # Should not recommend charging