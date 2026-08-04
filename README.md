# Geometron

Geometron is a Telegram bot for generating images with mathematical algorithms.
The current foundation provides an asynchronous `/ping` command and is ready for
future image-generation features.

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

## Running the bot

```bash
uv run geometron-bot
```

Send `/ping` to verify that the bot is running and responding to commands.

Stop the bot with `Ctrl+C`. The application shuts down gracefully through
python-telegram-bot's polling lifecycle.

## Development checks

```bash
uv run pytest
uv run ruff check .
```

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).
