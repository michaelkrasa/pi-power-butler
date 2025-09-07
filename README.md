# Pi-Power-Butler

Smart energy management bot for solar and battery optimization via Telegram.

## What it does

- Analyzes electricity prices and solar forecasts
- Provides battery charging recommendations
- Shows price graphs (red = you pay, green = you get paid)
- Estimates daily solar production
- Sends daily reports at 6 PM

## Commands

- `T` - Today's energy data
- `M` - Tomorrow's energy data
- `?` - Help

## Setup

1. Install dependencies: `uv install`
2. Copy `.env.example` to `.env` and configure:
   ```env
   TELEGRAM_BOT_TOKEN=your_bot_token
   ALPHA_ESS_APP_ID=your_app_id
   ALPHA_ESS_APP_SECRET=your_app_secret
   LAT=52.5200
   LON=13.4050
   TILT=30
   AZIMUTH=180
   SOLAR_RATIO=0.012529
   TIMEZONE=Europe/Berlin
   ```
3. Run: `uv run src/main.py`

## Background Running

To run the bot in the background (survives terminal closure):

```bash
# Simple background running
./start_bot.sh start

# Or setup as system service (auto-start on boot)
./setup_service.sh
```

See [BACKGROUND_RUNNING.md](BACKGROUND_RUNNING.md) for detailed instructions.

## Features

- SQLite caching for fast responses
- Mobile-optimized graphs
- Alpha ESS battery integration
- Automatic data cleanup