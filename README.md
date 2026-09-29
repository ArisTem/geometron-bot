# Geometron

Geometron is a Telegram bot for generating images with mathematical algorithms.
It generates deterministic Lissajous curves, spirograph patterns, and fractal trees
with varied color palettes, and reports the seed that determines each image's
geometry and colors.

## Requirements

- Python 3.14 or newer
- uv 0.12 or newer
- A Telegram bot token from [BotFather](https://t.me/BotFather)

## Installation

Clone the repository and install the project and development dependencies:

```bash
uv sync
```

## Configuration

Create a local environment file from the example:

```bash
cp .env.example .env
```

Set the token in `.env`:

```env
TELEGRAM_BOT_TOKEN=your-token-here
```

The `.env` file is ignored by Git.

### Usage statistics

To enable statistics, set an absolute path to a persistent SQLite file and a
random HMAC key in `.env`:

```env
STATS_DB_PATH=/path/to/stats.sqlite3
STATS_HMAC_KEY=your-random-secret
```

The parent directory must exist and be writable by the bot. Keep the same
database and key across restarts; changing the key breaks deduplication. An
empty `STATS_DB_PATH` disables statistics and does not require a key.

Each new private message counts toward the sender's UTC day, including commands
and media. DAU and MAU use UTC calendar days and months; the current periods are
partial. History starts when statistics are enabled. The `daily_activity` table
has `day_utc` and HMAC-SHA256 `user_digest` columns, with a unique pair as its
primary key. It stores no open Telegram IDs or message content.

Query the database directly:

```sql
-- Total unique users
SELECT COUNT(DISTINCT user_digest) AS total_unique FROM daily_activity;

-- DAU by UTC day
SELECT day_utc, COUNT(*) AS dau
FROM daily_activity
GROUP BY day_utc
ORDER BY day_utc;

-- MAU by UTC calendar month
SELECT substr(day_utc, 1, 7) AS month_utc,
       COUNT(DISTINCT user_digest) AS mau
FROM daily_activity
GROUP BY substr(day_utc, 1, 7)
ORDER BY month_utc;
```

## Running the bot

```bash
uv run geometron-bot
```

Available commands:

- `/start` introduces the bot and shows its available commands.
- `/lissajous` generates a new Lissajous image and shows its seed.
- `/spirograph` generates a new spirograph pattern and shows its type and seed.
- `/fractal_tree` generates a new fractal tree and shows its seed.
- `/random` generates a randomly selected image from the available image types.
- `/help` shows the current list of available commands.

The bot publishes these commands to Telegram's command menu when it starts.
The diagnostic `/ping` command is also available, but is intentionally hidden
from the public command list.

Stop the bot with `Ctrl+C`. The application shuts down gracefully through
python-telegram-bot's polling lifecycle.

## Development checks

```bash
uv run pytest
uv run ruff check .
```

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).
