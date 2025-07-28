import asyncio
import datetime
import structlog
from telegram import Bot
from telegram.ext import Application, CommandHandler, MessageHandler, filters

from src.config import Settings
from src.price_fetcher import PriceFetcher
from src.weather import get_solar_forecast
from src.plotting import create_price_graph, create_irradiance_graph

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
        logger.info("TelegramBot initialized")

    async def start(self, update, context):
        chat_id = update.message.chat_id
        with open("telegram_chat_id.txt", "w") as f:
            f.write(str(chat_id))
        logger.info(f"Bot started by user with chat_id: {chat_id}")
        await update.message.reply_text(f"Welcome to Pi-Power-Butler! Your chat ID {chat_id} has been saved.")

    async def today(self, update, context):
        """Fetch and display today's price and irradiance data"""
        await update.message.reply_text("Fetching today's data...")
        await self._fetch_and_send_data(update, datetime.date.today(), "today")

    async def tomorrow(self, update, context):
        """Fetch and display tomorrow's price and irradiance data"""
        await update.message.reply_text("Fetching tomorrow's data...")
        await self._fetch_and_send_data(update, datetime.date.today() + datetime.timedelta(days=1), "tomorrow")

    async def _fetch_and_send_data(self, update, target_date, day_label):
        """Helper method to fetch and send price and irradiance data"""
        try:
            # Fetch prices
            price_fetcher = PriceFetcher()
            prices = await price_fetcher.fetch_prices_for_date(target_date)
            
            # Fetch irradiance
            irradiance = get_solar_forecast(
                settings.lat, settings.lon, settings.tilt, settings.azimuth
            )
            
            # Generate graphs
            price_graph = create_price_graph(prices)
            irradiance_graph = create_irradiance_graph(irradiance)
            
            # Send data to user
            await update.message.reply_text(f"📊 {day_label.capitalize()}'s Data:")
            
            # Send price graph
            await update.message.reply_photo(
                photo=price_graph,
                caption=f"💰 Electricity prices for {day_label}"
            )
            
            # Send irradiance graph
            await update.message.reply_photo(
                photo=irradiance_graph,
                caption=f"☀️ Solar irradiance forecast for {day_label}"
            )
            
            logger.info(f"Successfully sent {day_label} data to user")
            
        except Exception as e:
            logger.error(f"Error fetching {day_label} data: {e}")
            await update.message.reply_text(f"❌ Error fetching {day_label}'s data: {str(e)}")

    async def handle_message(self, update, context):
        message_text = update.message.text
        chat_id = update.message.chat_id
        logger.info(f"Received message from {chat_id}: {message_text}")
        
        # Put message in queue for the nightly task
        await self.message_queue.put(message_text)
        # Also respond immediately to show the bot is working
        await update.message.reply_text(f"Received your message: {message_text}")

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
