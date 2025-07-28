import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.price_fetcher import PriceFetcher


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
