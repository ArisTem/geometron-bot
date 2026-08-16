import asyncio
import logging
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from geometron_bot.generation.lissajous import LissajousParameters
from geometron_bot.generation.service import LissajousGenerationResult
from geometron_bot.telegram_bot.handlers import (
    LISSAJOUS_SERVICE_KEY,
    lissajous,
    ping,
)


def test_ping_sends_response() -> None:
    message = SimpleNamespace(reply_text=AsyncMock())
    update = SimpleNamespace(message=message)

    asyncio.run(ping(update, None))

    message.reply_text.assert_awaited_once()

    response = message.reply_text.await_args.args[0]
    assert isinstance(response, str)
    assert response.strip()


def test_lissajous_sends_generated_image_with_seed(caplog) -> None:
    image_bytes = b"generated PNG"
    result = LissajousGenerationResult(
        image=BytesIO(image_bytes),
        seed=12345,
        parameters=LissajousParameters(
            frequency_x=2,
            frequency_y=3,
            phase_shift=0.5,
        ),
    )
    service = SimpleNamespace(generate=Mock(return_value=result))
    message = SimpleNamespace(reply_photo=AsyncMock(), reply_text=AsyncMock())
    update = SimpleNamespace(message=message)
    context = SimpleNamespace(bot_data={LISSAJOUS_SERVICE_KEY: service})

    with caplog.at_level(logging.INFO, logger=lissajous.__module__):
        asyncio.run(lissajous(update, context))

    service.generate.assert_called_once_with()
    message.reply_text.assert_not_awaited()
    message.reply_photo.assert_awaited_once()
    call_arguments = message.reply_photo.await_args.kwargs
    assert call_arguments["photo"].filename == "lissajous-12345.png"
    assert call_arguments["photo"].input_file_content == image_bytes
    assert "12345" in call_arguments["caption"]
    generation_records = [
        record
        for record in caplog.records
        if record.name == lissajous.__module__
        and record.getMessage().startswith("Lissajous image generated")
    ]
    assert len(generation_records) == 1
    assert generation_records[0].levelno == logging.INFO
    assert "seed=12345" in generation_records[0].getMessage()
    assert "duration_ms=" in generation_records[0].getMessage()


def test_lissajous_reports_generation_failure(caplog) -> None:
    service = SimpleNamespace(generate=Mock(side_effect=RuntimeError("render failed")))
    message = SimpleNamespace(reply_photo=AsyncMock(), reply_text=AsyncMock())
    update = SimpleNamespace(message=message)
    context = SimpleNamespace(bot_data={LISSAJOUS_SERVICE_KEY: service})

    with caplog.at_level(logging.ERROR, logger=lissajous.__module__):
        asyncio.run(lissajous(update, context))

    message.reply_photo.assert_not_awaited()
    message.reply_text.assert_awaited_once()
    error_records = [
        record
        for record in caplog.records
        if record.name == lissajous.__module__
        and record.getMessage().startswith("Lissajous generation failed")
    ]
    assert len(error_records) == 1
    error_record = error_records[0]
    assert error_record.levelno == logging.ERROR
    assert "duration_ms=" in error_record.getMessage()
    assert "error_type=RuntimeError" in error_record.getMessage()
    assert error_record.exc_info is not None
