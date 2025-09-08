import asyncio
import datetime

import structlog
from alphaess.alphaess import alphaess
from apscheduler.schedulers.background import BackgroundScheduler

from src.cache import EnergyDataCache
from src.config import Settings
from src.plotting import create_price_graph, create_irradiance_graph
from src.price_fetcher import PriceFetcher, PriceDataNotAvailableError
from src.telegram_bot import TelegramBot
from src.weather import get_solar_forecast

settings = Settings()
logger = structlog.get_logger()

# Global alphaess client and serial number
alpha_client = None
alpha_serial = None


async def initialize_alphaess():
    """Initialize the alphaess client and get the system serial number."""
    global alpha_client, alpha_serial
    
    try:
        alpha_client = alphaess(appID=settings.alpha_ess_app_id, appSecret=settings.alpha_ess_app_secret)
        
        # Get the system list to find the serial number
        ess_list = await alpha_client.getESSList()
        if not ess_list or len(ess_list) == 0:
            logger.error("No ESS systems found!")
            return False
        
        # Use the first system's serial number
        alpha_serial = ess_list[0].get('sysSn')
        if not alpha_serial:
            logger.error("No serial number found in ESS list!")
            return False
        
        if len(ess_list) > 1:
            logger.warning(f"Multiple ESS systems found ({len(ess_list)}), using first one: {alpha_serial}")
        
        logger.info(f"Initialized AlphaESS client with serial: {alpha_serial}")
        return True
        
    except Exception as e:
        logger.error(f"Error initializing AlphaESS: {e}")
        return False


def generate_simple_recommendation(
        soc: float, prices: list[float], irradiance: list[float]
) -> dict:
    """Generate a simple rule-based recommendation for battery charging."""

    # Find the cheapest 3-hour window for charging
    min_price = min(prices)
    max_price = max(prices)
    avg_price = sum(prices) / len(prices)

    # Find cheapest 3-hour consecutive window
    best_start_hour = 0
    best_avg_price = float('inf')

    for start_hour in range(22):  # Can start up to hour 20 for 3-hour window
        window_prices = prices[start_hour:start_hour + 3]
        window_avg = sum(window_prices) / len(window_prices)
        if window_avg < best_avg_price:
            best_avg_price = window_avg
            best_start_hour = start_hour

    # Find best solar hours (highest irradiance)
    max_irradiance = max(irradiance)
    best_solar_hours = [i for i, irr in enumerate(irradiance) if irr > max_irradiance * 0.7]  # Hours with >70% of peak irradiance
    best_solar_start = min(best_solar_hours) if best_solar_hours else 12  # Default to noon if no good solar data
    best_solar_end = max(best_solar_hours) if best_solar_hours else 15  # Default to 3pm if no good solar data

    # Calculate expected solar generation (calibrated estimate)
    daily_solar_estimate = sum(irradiance) * settings.solar_ratio  # Calibrated from July 2025 data

    # Decision logic
    should_charge = False
    charge_start = f"{best_start_hour:02d}:00"
    charge_end = f"{(best_start_hour + 3) % 24:02d}:00"

    # Charge if:
    # 1. Battery is below 30% OR
    # 2. Battery is below 60% AND prices are particularly cheap (below 70% of average)
    if soc < 30 or (soc < 60 and best_avg_price < avg_price * 0.7):
        should_charge = True

    # Create telegram message
    telegram_message = f"""🔋 Energy Update for Tomorrow

💰 Electricity Prices:
• Min: €{min_price:.1f}/MWh at {prices.index(min_price):02d}:00
• Max: €{max_price:.1f}/MWh at {prices.index(max_price):02d}:00
• Average: €{avg_price:.1f}/MWh

☀️ Solar Forecast: ~{daily_solar_estimate:.1f} kWh expected

🔋 Current Battery: {soc:.0f}%

⚡ Recommendation:
{"✅ CHARGE " + charge_start + "-" + charge_end + " (cheapest window)" if should_charge else "⏸️ No charging needed - sufficient battery level"}

🚗 Car Charging Advice:
• 💰 Cheapest grid charging: {charge_start}-{charge_end} (€{best_avg_price:.1f}/MWh avg)
• ☀️ Best solar charging: {best_solar_start:02d}:00-{best_solar_end:02d}:00 (peak sun)"""

    return {
        "reasoning": telegram_message,
        "telegram_draft": telegram_message
    }


async def nightly_task(bot: TelegramBot):
    logger.info("Starting nightly data pull")

    cache = EnergyDataCache()
    tomorrow = datetime.date.today() + datetime.timedelta(days=1)

    # Clean up old cache entries
    cache.cleanup_old_data()

    # Try to get tomorrow's data from cache first
    cached_data = cache.get_cached_data(tomorrow)

    if cached_data:
        # Use cached data
        prices = cached_data['prices']
        irradiance = cached_data['irradiance']
        logger.info("Using cached data for nightly recommendation")
    else:
        # Fetch fresh data
        logger.info("Fetching fresh data for nightly recommendation")

        try:
            # Fetch prices
            price_fetcher = PriceFetcher()
            prices = await price_fetcher.fetch_prices_for_date(tomorrow)

            # Fetch irradiance
            irradiance = get_solar_forecast(
                settings.lat, settings.lon, settings.tilt, settings.azimuth, tomorrow, settings.timezone
            )

            # Cache the data for future use (no graphs)
            cache.cache_data(tomorrow, prices, irradiance)

        except PriceDataNotAvailableError as e:
            logger.warning(f"Price data not available for nightly task: {e}")
            # Send a notification to the user about the unavailable data
            await bot.send_recommendation(
                "⏰ Tomorrow's electricity prices are not yet published.\n\n"
                "Prices are typically available around 3 PM. The nightly recommendation will be generated once prices are available.",
                None, None
            )
            return
        except Exception as e:
            logger.error(f"Error during nightly data fetch: {e}", exc_info=True)
            # Send error notification
            await bot.send_recommendation(
                f"❌ Error generating nightly recommendation: {str(e)}",
                None, None
            )
            return

    # Always generate graphs fresh (fast operation)
    price_graph = create_price_graph(prices)
    irradiance_graph = create_irradiance_graph(irradiance)

    # Fetch current SoC
    if not alpha_client or not alpha_serial:
        logger.error("AlphaESS not initialized, cannot fetch battery state")
        await bot.send_recommendation(
            "❌ Error: AlphaESS system not initialized. Cannot fetch battery state.",
            None, None
        )
        return
    
    power_data = await alpha_client.getLastPowerData(alpha_serial)
    # Extract SoC from the nested data structure
    soc = power_data.get("data", {}).get("soc", 0.0)
    logger.info("Current battery state", soc=soc, power_data_keys=list(power_data.keys()))

    # Generate recommendation using simple rule-based logic
    rec = generate_simple_recommendation(soc, prices, irradiance)
    logger.info("Generated recommendation", rec=rec)

    # Send recommendation to Telegram
    await bot.send_recommendation(rec["telegram_draft"], price_graph, irradiance_graph)
    logger.info("Recommendation sent to Telegram")


async def main():
    # Initialize AlphaESS client first
    logger.info("Initializing AlphaESS client...")
    if not await initialize_alphaess():
        logger.error("Failed to initialize AlphaESS client. Exiting.")
        return
    
    bot = TelegramBot()

    scheduler = BackgroundScheduler()
    scheduler.add_job(lambda: asyncio.run(nightly_task(bot)), 'cron', hour=18, minute=0)
    scheduler.start()
    logger.info("Scheduler started")

    try:
        logger.info("Starting Telegram bot polling...")
        await bot.run_polling()
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        logger.info("Scheduler shut down.")
    finally:
        # Clean up alphaess client session
        if alpha_client and hasattr(alpha_client, 'session') and alpha_client.session:
            await alpha_client.session.close()
            logger.info("AlphaESS client session closed.")


if __name__ == "__main__":
    asyncio.run(main())
