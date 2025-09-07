# Running Pi-Power-Butler in Background

This guide shows how to run the bot in the background so it continues running even after closing the terminal.

## Quick Start (Simple Method)

Use the provided startup script:

```bash
# Start the bot in background
./start_bot.sh start

# Check if it's running
./start_bot.sh status

# View logs
./start_bot.sh logs

# Stop the bot
./start_bot.sh stop

# Restart the bot
./start_bot.sh restart
```

## System Service (Advanced Method)

For automatic startup on boot and better system integration:

```bash
# Setup as systemd service
./setup_service.sh

# Start the service
systemctl --user start pi-power-butler

# Check status
systemctl --user status pi-power-butler

# View logs
journalctl --user -u pi-power-butler -f
```

## Logs

- **Simple method**: Logs are saved to `logs/bot_YYYYMMDD.log`
- **Service method**: Logs are in systemd journal

## Troubleshooting

If the bot won't start:

1. Check your `.env` file is configured correctly
2. Make sure all dependencies are installed: `uv install`
3. Test manually first: `uv run src/main.py`
4. Check logs for error messages

## Manual Background Running

If you prefer to run manually:

```bash
# Run in background with nohup
nohup uv run src/main.py > bot.log 2>&1 &

# Find the process ID
ps aux | grep "src/main.py"

# Stop the process (replace PID with actual process ID)
kill PID
```
