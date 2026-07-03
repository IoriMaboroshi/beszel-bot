# Beszel Bot

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A Telegram bot for interactive server monitoring via [Beszel](https://github.com/henrygd/beszel) — a lightweight Docker monitoring platform. View cluster overview, system details, resource rankings, alerts, and Docker container stats directly from Telegram.

## Features

- 🖥 **Cluster Overview** — See all monitored servers at a glance with CPU, RAM, disk, load, and uptime
- 📊 **System Details** — Drill into individual servers for detailed metrics including network and agent version
- 🏆 **Top Rankings** — Rank servers by CPU, memory, or disk usage with visual progress bars
- 🔔 **Alert History** — View recent alerts from your Beszel instance
- 🐳 **Docker Monitoring** — View container status, CPU, memory, and network usage across all servers
- 📈 **Historical Charts** — Generate CPU/memory trend charts with matplotlib (dark theme, Chinese labels)
- 📋 **Daily Briefing** — Automated daily report at 08:00 CST with server status, anomaly containers, and alerts
- 🔄 **Inline Refresh** — One-tap refresh buttons directly in chat
- 🔐 **Access Control** — Restrict bot usage to specific Telegram user IDs
- 🐳 **Docker Ready** — Deploy with a single `docker-compose up` command

## Available Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message |
| `/help` | Show all available commands |
| `/all` | Overview of all monitored servers |
| `/status <name>` | Detailed info for a specific server |
| `/top cpu` | CPU usage ranking |
| `/top mem` | Memory usage ranking |
| `/top disk` | Disk usage ranking |
| `/containers` | Docker container list |
| `/containers <server>` | Containers for a specific server |
| `/ctop cpu` | Container CPU ranking |
| `/ctop mem` | Container memory ranking |
| `/chart container cpu <name> [server]` | Container CPU trend chart |
| `/chart container mem <name> [server]` | Container memory trend chart |
| `/chart server cpu [server]` | Server CPU aggregation trend |
| `/proc [server]` | Container detailed ranking with network IO |
| `/briefing` | Manual daily briefing |
| `/alerts` | Recent alert history |
| `/refresh` | Refresh data (same as /all) |

## Setup

### Prerequisites

- Python 3.12+
- A running [Beszel](https://github.com/henrygd/beszel) instance
- A Telegram bot token (create via [@BotFather](https://t.me/BotFather))

### Docker (Recommended)

1. Clone the repository:

```bash
git clone https://github.com/IoriMaboroshi/beszel-bot.git
cd beszel-bot
```

2. Copy and edit the environment file:

```bash
cp .env.example .env
```

3. Edit `.env` with your actual values (see [Configuration](#configuration) below).

4. Build and run:

```bash
docker-compose up -d --build
```

### Manual (without Docker)

```bash
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your values
python bot.py
```

## Configuration

Edit your `.env` file with the following values:

```env
# Your Beszel instance URL
BESZEL_URL=http://your-beszel-url:8090

# Beszel login credentials
BESZEL_USER=your_beszel_email
BESZEL_PASS=your_beszel_password

# Telegram bot token (from @BotFather)
BOT_TOKEN=your_bot_token_here

# Comma-separated Telegram user IDs allowed to use the bot
# Leave empty to allow all users
ALLOWED_USERS=your_telegram_user_id

# Chat ID for daily briefing (optional)
# Get this by sending a message to your bot and checking the update
BRIEFING_CHAT_ID=your_chat_id
```

## Tech Stack

- **[aiogram](https://github.com/aiogram/aiogram)** — Async Telegram Bot framework
- **[aiohttp](https://github.com/aio-libs/aiohttp)** — Async HTTP client for Beszel API
- **[matplotlib](https://matplotlib.org/)** — Chart generation for historical trends
- **[APScheduler](https://apscheduler.readthedocs.io/)** — Task scheduling for daily briefings
- **[Beszel](https://github.com/henrygd/beszel)** — Lightweight Docker server monitoring

## License

[MIT](LICENSE)
