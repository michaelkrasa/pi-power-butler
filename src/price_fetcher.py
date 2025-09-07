import datetime
import logging

import backoff
import httpx


class PriceDataNotAvailableError(Exception):
    """Raised when price data is not yet available for the requested date"""
    pass


class PriceFetcher:
    PRICE_URL = "https://www.ote-cr.cz/en/short-term-markets/electricity/day-ahead-market/@@chart-data?report_date="

    def __init__(self):
        self.timeout = httpx.Timeout(10.0, connect=60.0)

    @backoff.on_exception(
        backoff.expo,
        (httpx.RequestError, httpx.HTTPStatusError, httpx.ReadTimeout),
        max_time=120,
    )
    async def get_request_with_backoff(self, url: str) -> httpx.Response:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response

    async def fetch_prices_for_date(self, date: datetime.date) -> list[float]:
        url_date = date.strftime("%Y-%m-%d")
        url = self.PRICE_URL + url_date
        logging.info(f"Fetching prices from URL: {url}")

        try:
            logging.info(f"Making HTTP request for date: {url_date}")
            response = await self.get_request_with_backoff(url)
            logging.info(f"Received response with status: {response.status_code}")

            logging.info("Parsing JSON response")
            json_data = response.json()
            prices = self.get_prices_from_json(json_data)
            logging.info(f"Successfully parsed {len(prices)} price points")
            return prices

        except (httpx.RequestError, httpx.HTTPStatusError) as exc:
            logging.error(
                f"Failed to fetch data from {exc.request.url!r} after retries: {exc}"
            )
            raise
        except PriceDataNotAvailableError as e:
            logging.warning(f"Price data not available for {url_date}: {e}")
            # Re-raise with a more user-friendly message
            raise PriceDataNotAvailableError(
                f"Tomorrow's electricity prices are not yet published. "
                f"Prices are typically available around 3 PM. Please try again later."
            )
        except Exception as e:
            logging.error(f"An unexpected error occurred: {e}", exc_info=True)
            raise

    @staticmethod
    def get_prices_from_json(prices_json: dict) -> list[float]:
        try:
            # Check if the data structure is as expected
            if "data" not in prices_json:
                raise PriceDataNotAvailableError("No 'data' field found in price response")

            if "dataLine" not in prices_json["data"]:
                raise PriceDataNotAvailableError("No 'dataLine' field found in price response")

            data_line = prices_json["data"]["dataLine"]

            # Check if dataLine has at least 2 elements (index 0 and 1)
            if len(data_line) < 2:
                raise PriceDataNotAvailableError("Price data not yet available - dataLine array is too short")

            # Check if the second element (index 1) has the expected structure
            if "point" not in data_line[1]:
                raise PriceDataNotAvailableError("Price data not yet available - no 'point' field in dataLine[1]")

            points = data_line[1]["point"]

            # Check if points array is empty
            if not points:
                raise PriceDataNotAvailableError("Price data not yet available - points array is empty")

            # Extract prices from the points
            prices = []
            for point in points:
                if "y" not in point:
                    raise PriceDataNotAvailableError("Price data not yet available - missing 'y' field in point data")
                prices.append(float(point["y"]))

            return prices

        except (KeyError, IndexError, TypeError) as e:
            # Handle any structural issues with the JSON
            raise PriceDataNotAvailableError(f"Price data not yet available - unexpected data structure: {str(e)}")
        except ValueError as e:
            # Handle conversion errors
            raise PriceDataNotAvailableError(f"Price data not yet available - invalid price values: {str(e)}")
