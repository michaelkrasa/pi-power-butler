import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.price_fetcher import PriceFetcher, PriceDataNotAvailableError


@pytest.mark.asyncio
async def test_fetch_prices():
    fetcher = PriceFetcher()
    with patch("httpx.AsyncClient.get", new=AsyncMock()) as mock_get:
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": {"dataLine": [{}, {"point": [{"y": "10.0"} for _ in range(24)]}]}
        }
        mock_get.return_value = mock_response
        prices = await fetcher.fetch_prices_for_date(datetime.date(2024, 1, 1))
        assert len(prices) == 24
        assert all(p == 10.0 for p in prices)
        print(prices)


@pytest.mark.asyncio
async def test_fetch_prices_not_available():
    """Test that PriceDataNotAvailableError is raised when prices are not published yet"""
    fetcher = PriceFetcher()
    with patch("httpx.AsyncClient.get", new=AsyncMock()) as mock_get:
        mock_response = MagicMock()
        # Simulate the case where dataLine array is too short (prices not published)
        mock_response.json.return_value = {
            "data": {"dataLine": []}  # Empty dataLine array
        }
        mock_get.return_value = mock_response

        with pytest.raises(PriceDataNotAvailableError) as exc_info:
            await fetcher.fetch_prices_for_date(datetime.date(2024, 1, 1))

        assert "not yet published" in str(exc_info.value)
        assert "3 PM" in str(exc_info.value)


@pytest.mark.asyncio
async def test_fetch_prices_empty_points():
    """Test that PriceDataNotAvailableError is raised when points array is empty"""
    fetcher = PriceFetcher()
    with patch("httpx.AsyncClient.get", new=AsyncMock()) as mock_get:
        mock_response = MagicMock()
        # Simulate the case where dataLine has structure but points array is empty
        mock_response.json.return_value = {
            "data": {"dataLine": [{}, {"point": []}]}  # Empty points array
        }
        mock_get.return_value = mock_response

        with pytest.raises(PriceDataNotAvailableError) as exc_info:
            await fetcher.fetch_prices_for_date(datetime.date(2024, 1, 1))

        assert "not yet published" in str(exc_info.value)


@pytest.mark.asyncio
async def test_fetch_prices_missing_data_field():
    """Test that PriceDataNotAvailableError is raised when data field is missing"""
    fetcher = PriceFetcher()
    with patch("httpx.AsyncClient.get", new=AsyncMock()) as mock_get:
        mock_response = MagicMock()
        # Simulate the case where data field is missing
        mock_response.json.return_value = {
            "axis": {"x": {}, "y": {}}
        }
        mock_get.return_value = mock_response

        with pytest.raises(PriceDataNotAvailableError) as exc_info:
            await fetcher.fetch_prices_for_date(datetime.date(2024, 1, 1))

        assert "not yet published" in str(exc_info.value)
