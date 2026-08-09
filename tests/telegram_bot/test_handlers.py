import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from geometron_bot.telegram_bot.handlers import ping


def test_ping_sends_response() -> None:
    message = SimpleNamespace(reply_text=AsyncMock())
    update = SimpleNamespace(message=message)

    asyncio.run(ping(update, None))

    message.reply_text.assert_awaited_once()

    response = message.reply_text.await_args.args[0]
    assert isinstance(response, str)
    assert response.strip()
