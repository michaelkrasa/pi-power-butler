import asyncio
import datetime

import structlog
from telegram import Bot
from telegram.ext import Application, CommandHandler, MessageHandler, filters

from src.cache import EnergyDataCache
from src.config import Settings
from src.plotting import create_price_graph, create_irradiance_graph
from src.price_fetcher import PriceFetcher
from src.weather import get_solar_forecast

settings = Settings()
logger = structlog.get_logger()


class TelegramBot:
    def __init__(self):
        self.application = Application.builder().token(settings.telegram_bot_token).build()
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("today", self.today))
        self.application.add_handler(CommandHandler("tomorrow", self.tomorrow))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        self.message_queue = asyncio.Queue()
        self.cache = EnergyDataCache()
        logger.info("TelegramBot initialized")

    async def start(self, update, context):
        chat_id = update.message.chat_id
        with open("telegram_chat_id.txt", "w") as f:
            f.write(str(chat_id))
        logger.info(f"Bot started by user with chat_id: {chat_id}")
        await self._send_help(update, is_welcome=True)

    async def today(self, update, context):
        """Fetch and display today's price and irradiance data (legacy command)"""
        await update.message.reply_text("💡 Pro tip: Just send 'T' next time for faster access!")
        await update.message.reply_text("🔥 Getting today's energy data...")
        await self._fetch_and_send_data(update, datetime.date.today(), "today")

    async def tomorrow(self, update, context):
        """Fetch and display tomorrow's price and irradiance data (legacy command)"""
        await update.message.reply_text("💡 Pro tip: Just send 'M' next time for faster access!")
        await update.message.reply_text("🌅 Getting tomorrow's energy data...")
        await self._fetch_and_send_data(update, datetime.date.today() + datetime.timedelta(days=1), "tomorrow")

    async def _fetch_and_send_data(self, update, target_date, day_label):
        """Helper method to fetch and send price and irradiance data with caching"""
        try:
            # Clean up old cache entries first
            self.cache.cleanup_old_data()

            # Try to get data from cache first
            cached_data = self.cache.get_cached_data(target_date)

            if cached_data:
                # Use cached data
                prices = cached_data['prices']
                irradiance = cached_data['irradiance']

                await update.message.reply_text(f"⚡ {day_label.capitalize()}'s Data:")
                logger.info(f"Using cached data for {day_label}")

            else:
                # Fetch fresh data
                await update.message.reply_text(f"🔄 Fetching fresh {day_label} data...")
                logger.info(f"Starting fresh data fetch for {day_label}")

                try:
                    # Fetch prices
                    logger.info(f"Fetching prices for {target_date}")
                    price_fetcher = PriceFetcher()
                    prices = await price_fetcher.fetch_prices_for_date(target_date)
                    logger.info(f"Successfully fetched {len(prices)} price points for {day_label}")

                    # Fetch irradiance
                    logger.info(f"Fetching irradiance for {target_date} with timezone {settings.timezone}")
                    irradiance = get_solar_forecast(
                        settings.lat, settings.lon, settings.tilt, settings.azimuth, target_date, settings.timezone
                    )
                    logger.info(f"Successfully fetched {len(irradiance)} irradiance points for {day_label}")

                    # Cache the data (no graphs)
                    logger.info(f"Caching data for {target_date}")
                    self.cache.cache_data(target_date, prices, irradiance)
                    logger.info(f"Successfully cached data for {day_label}")

                    await update.message.reply_text(f"📊 {day_label.capitalize()}'s Data:")
                    logger.info(f"Fetched and cached fresh data for {day_label}")

                except Exception as fetch_error:
                    logger.error(f"Error during data fetch for {day_label}: {fetch_error}", exc_info=True)
                    await update.message.reply_text(f"❌ Error fetching {day_label} data: {str(fetch_error)}")
                    return

            # Calculate solar production estimate
            daily_solar_estimate = sum(irradiance) * settings.solar_ratio
            logger.info(f"Calculated solar estimate: {daily_solar_estimate:.1f} kWh for {day_label}")
            
            # Always generate graphs fresh (fast operation)
            logger.info(f"Generating price graph for {day_label}")
            try:
                price_graph = create_price_graph(prices)
                logger.info(f"Successfully generated price graph ({len(price_graph)} bytes)")
            except Exception as e:
                logger.error(f"Error generating price graph: {e}", exc_info=True)
                await update.message.reply_text(f"❌ Error generating price graph: {str(e)}")
                return

            logger.info(f"Generating irradiance graph for {day_label}")
            try:
                irradiance_graph = create_irradiance_graph(irradiance)
                logger.info(f"Successfully generated irradiance graph ({len(irradiance_graph)} bytes)")
            except Exception as e:
                logger.error(f"Error generating irradiance graph: {e}", exc_info=True)
                await update.message.reply_text(f"❌ Error generating irradiance graph: {str(e)}")
                return

            # Send price graph
            logger.info(f"Sending price graph for {day_label}")
            try:
                await update.message.reply_photo(
                    photo=price_graph,
                    caption=f"💰 Electricity prices for {day_label}"
                )
                logger.info(f"Successfully sent price graph for {day_label}")
            except Exception as e:
                logger.error(f"Error sending price graph: {e}", exc_info=True)
                await update.message.reply_text(f"❌ Error sending price graph: {str(e)}")
                return

            # Send irradiance graph
            logger.info(f"Sending irradiance graph for {day_label}")
            try:
                await update.message.reply_photo(
                    photo=irradiance_graph,
                    caption=f"☀️ Solar irradiance forecast for {day_label}\n\n⚡ Expected generation: ~{daily_solar_estimate:.1f} kWh"
                )
                logger.info(f"Successfully sent irradiance graph for {day_label}")
            except Exception as e:
                logger.error(f"Error sending irradiance graph: {e}", exc_info=True)
                await update.message.reply_text(f"❌ Error sending irradiance graph: {str(e)}")
                return

            logger.info(f"Successfully sent {day_label} data to user")

        except Exception as e:
            logger.error(f"Error fetching {day_label} data: {e}")
            await update.message.reply_text(f"❌ Error fetching {day_label}'s data: {str(e)}")

    async def _send_help(self, update, is_welcome=False):
        """Send help infographic with ultra-simple commands"""
        welcome_text = "🎉 **Welcome to Pi-Power-Butler!**\n\n" if is_welcome else ""

        help_message = f"""{welcome_text}⚡ **Super Simple Commands:**

🔥 **T** → Today's energy data
🌅 **M** → Tomorrow's energy data  
❓ **?** → Show this help

📱 **That's it!** Just send one letter and get instant energy insights.

💡 **Pro tip:** Data is cached locally for lightning-fast responses! You'll see solar production estimates and get automatic daily recommendations at 6 PM with charging advice for your battery and car!

🚀 **Try it now:** Send **T** to see today's data!"""

        await update.message.reply_text(help_message, parse_mode='Markdown')

    async def handle_message(self, update, context):
        message_text = update.message.text.strip().upper()
        chat_id = update.message.chat_id
        logger.info(f"Received message from {chat_id}: {message_text}")

        # Ultra-simple single letter commands
        if message_text == 'T':
            await update.message.reply_text("🔥 Getting today's energy data...")
            await self._fetch_and_send_data(update, datetime.date.today(), "today")
        elif message_text == 'M':
            await update.message.reply_text("🌅 Getting tomorrow's energy data...")
            await self._fetch_and_send_data(update, datetime.date.today() + datetime.timedelta(days=1), "tomorrow")
        elif message_text in ['?', 'H', 'HELP']:
            await self._send_help(update)
        else:
            # For any unrecognized input, show help
            await update.message.reply_text("🤔 I didn't understand that. Here's what I can do:")
            await self._send_help(update)

        # Still put message in queue for the nightly task (in case needed)
        await self.message_queue.put(message_text)

    async def send_recommendation(self, recommendation: str, price_graph: bytes, irradiance_graph: bytes):
        try:
            with open("telegram_chat_id.txt", "r") as f:
                chat_id = f.read().strip()
        except FileNotFoundError:
            logger.error("Chat ID not found. Please start the bot with /start first.")
            return

        bot = Bot(settings.telegram_bot_token)
        await bot.send_message(chat_id=chat_id, text=recommendation)
        await bot.send_photo(chat_id=chat_id, photo=price_graph)
        await bot.send_photo(chat_id=chat_id, photo=irradiance_graph)

    async def wait_for_reply(self, timeout: int = 300) -> str | None:
        try:
            return await asyncio.wait_for(self.message_queue.get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None

    async def run_polling(self):
        """Run the bot in polling mode asynchronously"""
        logger.info("Starting Telegram bot polling...")
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling()
        logger.info("Telegram bot polling started successfully")

        try:
            # Keep the bot running
            await asyncio.Event().wait()
        except KeyboardInterrupt:
            logger.info("Stopping Telegram bot...")
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()

    def run_polling_sync(self):
        """Synchronous wrapper for run_polling"""
        asyncio.run(self.run_polling())


async def main():
    bot = TelegramBot()
    await bot.send_recommendation("This is a test recommendation.", b"", b"")
    reply = await bot.wait_for_reply()
    print(f"Received reply: {reply}")


if __name__ == "__main__":
    asyncio.run(main())
