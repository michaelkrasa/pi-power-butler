import asyncio
import datetime
import time

import structlog
from apscheduler.schedulers.background import BackgroundScheduler

from src.config import Settings
from src.mcp_alphaess import execute_mcp_tool
from src.price_fetcher import PriceFetcher
from src.weather import get_solar_forecast
from src.plotting import create_price_graph, create_irradiance_graph
from src.telegram_bot import TelegramBot

settings = Settings()
logger = structlog.get_logger()


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
    best_solar_end = max(best_solar_hours) if best_solar_hours else 15    # Default to 3pm if no good solar data
    
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

🚗 Tesla Charging Advice:
• 💰 Cheapest grid charging: {charge_start}-{charge_end} (€{best_avg_price:.1f}/MWh avg)
• ☀️ Best solar charging: {best_solar_start:02d}:00-{best_solar_end:02d}:00 (peak sun)"""

    # Create tool calls for charging if needed
    tool_calls = []
    if should_charge:
        tool_calls = [{
            "name": "mcp_alpha-ess-mcp_set_battery_charge",
            "parameters": {
                "enabled": True,
                "dp1_start": charge_start,
                "dp1_end": charge_end,
                "dp2_start": "00:00",  # No second period
                "dp2_end": "00:00",
                "charge_cutoff_soc": 100,
                "serial": None
            }
        }]
    
    return {
        "reasoning": f"Battery at {soc}%. Cheapest 3h window: {charge_start}-{charge_end} (€{best_avg_price:.1f}/MWh avg). Best solar: {best_solar_start:02d}:00-{best_solar_end:02d}:00. {'Charging recommended.' if should_charge else 'No charging needed.'}",
        "telegram_draft": telegram_message,
        "tool_calls": tool_calls
    }


async def nightly_task(bot: TelegramBot):
    logger.info("Starting nightly data pull")

    # Fetch prices
    price_fetcher = PriceFetcher()
    tomorrow = datetime.date.today() + datetime.timedelta(days=1)
    prices = await price_fetcher.fetch_prices_for_date(tomorrow)

    # Fetch irradiance
    irradiance = get_solar_forecast(
        settings.lat, settings.lon, settings.tilt, settings.azimuth
    )

    # Generate graphs
    price_graph = create_price_graph(prices)
    irradiance_graph = create_irradiance_graph(irradiance)

    # Fetch current SoC
    power_data = execute_mcp_tool("mcp_alpha-ess-mcp_get_last_power_data", {})
    # Extract SoC from the nested data structure
    soc = power_data.get("data", {}).get("soc", 0.0)
    logger.info("Current battery state", soc=soc, power_data_keys=list(power_data.keys()))

    # Generate recommendation using simple rule-based logic
    rec = generate_simple_recommendation(soc, prices, irradiance)
    logger.info("Generated recommendation", rec=rec)

    # Send recommendation to Telegram
    await bot.send_recommendation(rec["telegram_draft"], price_graph, irradiance_graph)
    logger.info("Recommendation sent to Telegram")

    # Execute recommended actions automatically (no user interaction needed)
    tool_calls = rec.get("tool_calls", [])

    for call in tool_calls:
        result = execute_mcp_tool(call["name"], call["parameters"])
        logger.info("Executed tool call", call=call, result=result)


async def main():
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


if __name__ == "__main__":
    asyncio.run(main())
