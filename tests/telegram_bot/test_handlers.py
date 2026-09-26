import asyncio
import logging
import re
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from geometron_bot.generation.fractal_tree import FractalTreeParameters, TreeVariant
from geometron_bot.generation.lissajous import LissajousParameters
from geometron_bot.generation.service import (
    FractalTreeGenerationResult,
    LissajousGenerationResult,
    SpirographGenerationResult,
)
from geometron_bot.generation.spirograph import SpirographParameters
from geometron_bot.telegram_bot.handlers import (
    FRACTAL_TREE_SERVICE_KEY,
    GENERATION_ERROR_TEXT,
    GENERATION_STATUS_TEXT,
    LISSAJOUS_SERVICE_KEY,
    PUBLIC_COMMANDS,
    SPIROGRAPH_SERVICE_KEY,
    fractal_tree,
    help_command,
    lissajous,
    ping,
    spirograph,
    start,
)


def extract_command_names(text: str) -> set[str]:
    return set(re.findall(r"^/([a-z][a-z0-9_]*)\b", text, flags=re.MULTILINE))


def public_command_names() -> set[str]:
    return {command.name for command in PUBLIC_COMMANDS}


def image_command_message() -> tuple[SimpleNamespace, SimpleNamespace]:
    status = SimpleNamespace(edit_text=AsyncMock(), delete=AsyncMock())
    message = SimpleNamespace(
        reply_photo=AsyncMock(),
        reply_text=AsyncMock(return_value=status),
    )
    return message, status


def test_start_lists_public_commands() -> None:
    message = SimpleNamespace(reply_text=AsyncMock())
    update = SimpleNamespace(message=message)

    asyncio.run(start(update, None))

    message.reply_text.assert_awaited_once()
    response = message.reply_text.await_args.args[0]
    assert extract_command_names(response) == public_command_names()


def test_help_lists_public_commands() -> None:
    message = SimpleNamespace(reply_text=AsyncMock())
    update = SimpleNamespace(message=message)

    asyncio.run(help_command(update, None))

    message.reply_text.assert_awaited_once()
    response = message.reply_text.await_args.args[0]
    assert extract_command_names(response) == public_command_names()


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
    message, status = image_command_message()

    def generate() -> LissajousGenerationResult:
        message.reply_text.assert_awaited_once_with(GENERATION_STATUS_TEXT)
        return result

    service = SimpleNamespace(generate=Mock(side_effect=generate))
    update = SimpleNamespace(message=message)
    context = SimpleNamespace(bot_data={LISSAJOUS_SERVICE_KEY: service})

    def delete_status() -> None:
        message.reply_photo.assert_awaited_once()

    status.delete.side_effect = delete_status
    with caplog.at_level(logging.INFO, logger=lissajous.__module__):
        asyncio.run(lissajous(update, context))

    service.generate.assert_called_once_with()
    message.reply_text.assert_awaited_once_with(GENERATION_STATUS_TEXT)
    message.reply_photo.assert_awaited_once()
    status.delete.assert_awaited_once()
    status.edit_text.assert_not_awaited()
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
    message, status = image_command_message()
    update = SimpleNamespace(message=message)
    context = SimpleNamespace(bot_data={LISSAJOUS_SERVICE_KEY: service})

    with caplog.at_level(logging.ERROR, logger=lissajous.__module__):
        asyncio.run(lissajous(update, context))

    message.reply_photo.assert_not_awaited()
    message.reply_text.assert_awaited_once_with(GENERATION_STATUS_TEXT)
    status.edit_text.assert_awaited_once_with(GENERATION_ERROR_TEXT)
    status.delete.assert_not_awaited()
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


def test_lissajous_reports_photo_delivery_failure(caplog) -> None:
    result = LissajousGenerationResult(
        image=BytesIO(b"PNG"),
        seed=12345,
        parameters=LissajousParameters(2, 3, 0.5),
    )
    service = SimpleNamespace(generate=Mock(return_value=result))
    message, status = image_command_message()
    message.reply_photo.side_effect = RuntimeError("upload failed")
    context = SimpleNamespace(bot_data={LISSAJOUS_SERVICE_KEY: service})

    with caplog.at_level(logging.ERROR, logger=lissajous.__module__):
        asyncio.run(lissajous(SimpleNamespace(message=message), context))

    message.reply_photo.assert_awaited_once()
    status.edit_text.assert_awaited_once_with(GENERATION_ERROR_TEXT)
    status.delete.assert_not_awaited()
    assert "Lissajous image delivery failed" in caplog.text


def test_spirograph_sends_image_type_seed_and_filename(caplog) -> None:
    image_bytes = b"generated PNG"
    result = SpirographGenerationResult(
        image=BytesIO(image_bytes),
        seed=12345,
        parameters=SpirographParameters("inside", 7, 2, 2.0),
    )
    service = SimpleNamespace(generate=Mock(return_value=result))
    message, _ = image_command_message()
    update = SimpleNamespace(message=message)
    context = SimpleNamespace(bot_data={SPIROGRAPH_SERVICE_KEY: service})

    with caplog.at_level(logging.INFO, logger=spirograph.__module__):
        asyncio.run(spirograph(update, context))

    service.generate.assert_called_once_with()
    message.reply_photo.assert_awaited_once()
    sent = message.reply_photo.await_args.kwargs
    assert sent["photo"].filename == "spirograph-12345.png"
    assert sent["photo"].input_file_content == image_bytes
    assert "внутри" in sent["caption"]
    assert "12345" in sent["caption"]
    assert "duration_ms=" in caplog.text


def test_spirograph_sends_outside_type() -> None:
    result = SpirographGenerationResult(
        image=BytesIO(b"PNG"),
        seed=0,
        parameters=SpirographParameters("outside", 7, 2, 2.0),
    )
    service = SimpleNamespace(generate=Mock(return_value=result))
    message, _ = image_command_message()
    context = SimpleNamespace(bot_data={SPIROGRAPH_SERVICE_KEY: service})

    asyncio.run(spirograph(SimpleNamespace(message=message), context))

    assert "снаружи" in message.reply_photo.await_args.kwargs["caption"]


def test_fractal_tree_sends_image_seed_and_filename(caplog) -> None:
    image_bytes = b"generated PNG"
    result = FractalTreeGenerationResult(
        image=BytesIO(image_bytes),
        seed=12345,
        parameters=FractalTreeParameters(
            depth=9,
            length_ratio=0.7,
            branch_angle=0.4,
            trunk_tilt=0.0,
            angle_jitter=0.0,
            length_jitter=0.0,
            variant=TreeVariant.SYMMETRIC,
        ),
    )
    service = SimpleNamespace(generate=Mock(return_value=result))
    message, _ = image_command_message()
    context = SimpleNamespace(bot_data={FRACTAL_TREE_SERVICE_KEY: service})

    with caplog.at_level(logging.INFO, logger=fractal_tree.__module__):
        asyncio.run(fractal_tree(SimpleNamespace(message=message), context))

    service.generate.assert_called_once_with()
    message.reply_photo.assert_awaited_once()
    sent = message.reply_photo.await_args.kwargs
    assert sent["photo"].filename == "fractal-tree-12345.png"
    assert sent["photo"].input_file_content == image_bytes
    assert sent["caption"] == "Фрактальное дерево\nSeed: 12345"
    assert "seed=12345" in caplog.text
    assert "duration_ms=" in caplog.text
