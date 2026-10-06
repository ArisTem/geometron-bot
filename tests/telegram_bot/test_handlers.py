import asyncio
import logging
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from geometron_bot.generation.fractal_tree import FractalTreeParameters, TreeVariant
from geometron_bot.generation.lissajous import LissajousParameters
from geometron_bot.generation.service import (
    FractalTreeGenerationResult,
    LissajousGenerationResult,
    SpirographGenerationResult,
)
from geometron_bot.generation.spirograph import SpirographParameters
from geometron_bot.telegram_bot import handlers
from geometron_bot.telegram_bot.generation_jobs import (
    GENERATION_JOBS_KEY,
    GenerationJobs,
)
from geometron_bot.telegram_bot.handlers import (
    FRACTAL_TREE_SERVICE_KEY,
    IMAGE_COMMANDS,
    LISSAJOUS_SERVICE_KEY,
    PUBLIC_COMMANDS,
    SPIROGRAPH_SERVICE_KEY,
    build_help_text,
    fractal_tree,
    help_command,
    lissajous,
    ping,
    random_image,
    spirograph,
    start,
)
from geometron_bot.telegram_bot.localization import tr


def image_command_message() -> tuple[SimpleNamespace, SimpleNamespace]:
    status = SimpleNamespace(edit_text=AsyncMock(), delete=AsyncMock())
    message = SimpleNamespace(
        reply_photo=AsyncMock(),
        reply_text=AsyncMock(return_value=status),
    )
    return message, status


def image_update(
    message, user_id: int = 1, language_code: str | None = "ru"
) -> SimpleNamespace:
    return SimpleNamespace(
        message=message,
        effective_user=SimpleNamespace(id=user_id, language_code=language_code),
    )


def image_context(services: dict, max_concurrent: int = 2) -> SimpleNamespace:
    tasks = []

    def create_task(coroutine, *, update):
        task = asyncio.create_task(coroutine)
        tasks.append(task)
        return task

    return SimpleNamespace(
        bot_data={**services, GENERATION_JOBS_KEY: GenerationJobs(max_concurrent)},
        application=SimpleNamespace(create_task=create_task),
        tasks=tasks,
    )


def run_image_command(callback, update, context) -> None:
    async def run() -> None:
        await callback(update, context)
        await asyncio.gather(*context.tasks)

    asyncio.run(run())


@pytest.mark.parametrize("language", ["ru", "en"])
def test_start_lists_public_commands(language) -> None:
    message = SimpleNamespace(reply_text=AsyncMock())
    update = image_update(message, language_code=language)

    asyncio.run(start(update, None))

    message.reply_text.assert_awaited_once_with(
        tr(language, "start.text", help_text=build_help_text(language))
    )


@pytest.mark.parametrize("language", ["ru", "en"])
def test_help_lists_public_commands(language) -> None:
    message = SimpleNamespace(reply_text=AsyncMock())
    update = image_update(message, language_code=language)

    asyncio.run(help_command(update, None))

    message.reply_text.assert_awaited_once_with(build_help_text(language))


@pytest.mark.parametrize("language", ["ru", "en"])
def test_help_translates_the_shared_public_command_registry(language) -> None:
    text = build_help_text(language)
    command_lines = [line for line in text.splitlines() if line.startswith("/")]
    assert [line.split(maxsplit=1)[0] for line in command_lines] == [
        f"/{command.name}" for command in PUBLIC_COMMANDS
    ]
    for command, line in zip(PUBLIC_COMMANDS, command_lines, strict=True):
        assert tr(language, command.description_key) in line


@pytest.mark.parametrize("language", ["ru", "en"])
def test_ping_sends_response(language) -> None:
    message = SimpleNamespace(reply_text=AsyncMock())
    update = image_update(message, language_code=language)

    asyncio.run(ping(update, None))

    message.reply_text.assert_awaited_once_with(tr(language, "ping.text"))


def test_start_without_user_replies_in_english() -> None:
    message = SimpleNamespace(reply_text=AsyncMock())
    update = SimpleNamespace(message=message, effective_user=None)
    asyncio.run(start(update, None))
    message.reply_text.assert_awaited_once_with(
        tr("en", "start.text", help_text=build_help_text("en"))
    )


def test_lissajous_sends_generated_image_with_seed(caplog) -> None:
    language = "en"
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
        message.reply_text.assert_awaited_once_with(tr(language, "generation.started"))
        return result

    service = SimpleNamespace(generate=Mock(side_effect=generate))
    update = image_update(message, language_code=language)
    context = image_context({LISSAJOUS_SERVICE_KEY: service})

    def delete_status() -> None:
        message.reply_photo.assert_awaited_once()

    status.delete.side_effect = delete_status
    with caplog.at_level(logging.INFO, logger=lissajous.__module__):
        run_image_command(lissajous, update, context)

    service.generate.assert_called_once_with()
    message.reply_text.assert_awaited_once_with(tr(language, "generation.started"))
    message.reply_photo.assert_awaited_once()
    status.delete.assert_awaited_once()
    status.edit_text.assert_not_awaited()
    call_arguments = message.reply_photo.await_args.kwargs
    assert call_arguments["photo"].filename == "lissajous-12345.png"
    assert call_arguments["photo"].input_file_content == image_bytes
    assert call_arguments["caption"] == tr(language, "caption.lissajous", seed=12345)
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
    language = "en"
    service = SimpleNamespace(generate=Mock(side_effect=RuntimeError("render failed")))
    message, status = image_command_message()
    update = image_update(message, language_code=language)
    context = image_context({LISSAJOUS_SERVICE_KEY: service})

    with caplog.at_level(logging.ERROR, logger=lissajous.__module__):
        run_image_command(lissajous, update, context)

    message.reply_photo.assert_not_awaited()
    message.reply_text.assert_awaited_once_with(tr(language, "generation.started"))
    status.edit_text.assert_awaited_once_with(tr(language, "generation.error"))
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
    language = "en"
    result = LissajousGenerationResult(
        image=BytesIO(b"PNG"),
        seed=12345,
        parameters=LissajousParameters(2, 3, 0.5),
    )
    service = SimpleNamespace(generate=Mock(return_value=result))
    message, status = image_command_message()
    message.reply_photo.side_effect = RuntimeError("upload failed")
    context = image_context({LISSAJOUS_SERVICE_KEY: service})

    with caplog.at_level(logging.ERROR, logger=lissajous.__module__):
        run_image_command(lissajous, image_update(message, language_code=language), context)

    message.reply_photo.assert_awaited_once()
    status.edit_text.assert_awaited_once_with(tr(language, "generation.error"))
    status.delete.assert_not_awaited()
    assert "Lissajous image delivery failed" in caplog.text


def test_spirograph_sends_image_type_seed_and_filename(caplog) -> None:
    language = "en"
    image_bytes = b"generated PNG"
    result = SpirographGenerationResult(
        image=BytesIO(image_bytes),
        seed=12345,
        parameters=SpirographParameters("inside", 7, 2, 2.0),
    )
    service = SimpleNamespace(generate=Mock(return_value=result))
    message, _ = image_command_message()
    update = image_update(message, language_code=language)
    context = image_context({SPIROGRAPH_SERVICE_KEY: service})

    with caplog.at_level(logging.INFO, logger=spirograph.__module__):
        run_image_command(spirograph, update, context)

    service.generate.assert_called_once_with()
    message.reply_photo.assert_awaited_once()
    sent = message.reply_photo.await_args.kwargs
    assert sent["photo"].filename == "spirograph-12345.png"
    assert sent["photo"].input_file_content == image_bytes
    assert sent["caption"] == tr(language, "caption.spirograph.inside", seed=12345)
    assert "duration_ms=" in caplog.text


def test_spirograph_sends_outside_type() -> None:
    language = "en"
    result = SpirographGenerationResult(
        image=BytesIO(b"PNG"),
        seed=0,
        parameters=SpirographParameters("outside", 7, 2, 2.0),
    )
    service = SimpleNamespace(generate=Mock(return_value=result))
    message, _ = image_command_message()
    context = image_context({SPIROGRAPH_SERVICE_KEY: service})

    run_image_command(spirograph, image_update(message, language_code=language), context)

    assert message.reply_photo.await_args.kwargs["caption"] == tr(
        language, "caption.spirograph.outside", seed=0
    )


def test_fractal_tree_sends_image_seed_and_filename(caplog) -> None:
    language = "en"
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
    context = image_context({FRACTAL_TREE_SERVICE_KEY: service})

    with caplog.at_level(logging.INFO, logger=fractal_tree.__module__):
        run_image_command(fractal_tree, image_update(message, language_code=language), context)

    service.generate.assert_called_once_with()
    message.reply_photo.assert_awaited_once()
    sent = message.reply_photo.await_args.kwargs
    assert sent["photo"].filename == "fractal-tree-12345.png"
    assert sent["photo"].input_file_content == image_bytes
    assert sent["caption"] == tr(language, "caption.fractal_tree", seed=12345)
    assert "seed=12345" in caplog.text
    assert "duration_ms=" in caplog.text


def test_random_image_dispatches_selected_command(monkeypatch) -> None:
    language = "en"
    selected_command = next(
        command for command in IMAGE_COMMANDS if command.name == "fractal_tree"
    )
    choose = Mock(return_value=selected_command)
    monkeypatch.setattr(handlers.secrets, "choice", choose)

    result = SimpleNamespace(image=BytesIO(b"PNG"), seed=12345)
    service = SimpleNamespace(generate=Mock(return_value=result))
    message, _ = image_command_message()
    context = image_context({FRACTAL_TREE_SERVICE_KEY: service})

    run_image_command(random_image, image_update(message, language_code=language), context)

    choose.assert_called_once_with(IMAGE_COMMANDS)
    service.generate.assert_called_once_with()
    message.reply_photo.assert_awaited_once()
    message.reply_text.assert_awaited_once_with(tr(language, "generation.started"))
    assert message.reply_photo.await_args.kwargs["caption"] == tr(
        language, "caption.fractal_tree", seed=12345
    )


def generation_service() -> SimpleNamespace:
    return SimpleNamespace(
        generate=Mock(
            side_effect=lambda: SimpleNamespace(
                image=BytesIO(b"PNG"),
                seed=12345,
                parameters=SimpleNamespace(pattern_type="inside"),
            )
        )
    )


@pytest.mark.parametrize("repeat", [lissajous, spirograph, fractal_tree, random_image])
def test_repeated_commands_are_rejected_until_generation_finishes(
    monkeypatch, repeat
) -> None:
    async def run() -> None:
        started = asyncio.Event()
        finish = asyncio.Event()

        async def to_thread(generate):
            started.set()
            await finish.wait()
            return generate()

        monkeypatch.setattr(handlers.asyncio, "to_thread", to_thread)
        service = generation_service()
        context = image_context(
            {
                LISSAJOUS_SERVICE_KEY: service,
                SPIROGRAPH_SERVICE_KEY: service,
                FRACTAL_TREE_SERVICE_KEY: service,
            },
            max_concurrent=1,
        )
        first, _ = image_command_message()
        second, _ = image_command_message()

        # Sequential handlers still reject a repeat before the job even starts.
        await asyncio.wait_for(lissajous(image_update(first), context), timeout=2)
        service.generate.assert_not_called()
        await asyncio.wait_for(repeat(image_update(second), context), timeout=2)
        second.reply_text.assert_awaited_once_with(tr("ru", "generation.busy"))
        assert len(context.tasks) == 1

        await asyncio.wait_for(started.wait(), timeout=2)
        assert not context.tasks[0].done()

        finish.set()
        await asyncio.wait_for(context.tasks[0], timeout=2)
        service.generate.assert_called_once_with()
        second.reply_photo.assert_not_awaited()

        # A fresh request becomes eligible after the first image is delivered.
        await lissajous(image_update(second), context)
        await asyncio.wait_for(context.tasks[-1], timeout=2)
        assert service.generate.call_count == 2
        second.reply_photo.assert_awaited_once()

    asyncio.run(run())


def test_different_users_run_concurrently_and_excess_requests_are_not_queued(
    monkeypatch,
) -> None:
    async def run() -> None:
        both_started = asyncio.Event()
        finish = asyncio.Event()
        running = 0

        async def to_thread(generate):
            nonlocal running
            running += 1
            if running == 2:
                both_started.set()
            await finish.wait()
            return generate()

        monkeypatch.setattr(handlers.asyncio, "to_thread", to_thread)
        service = generation_service()
        context = image_context({LISSAJOUS_SERVICE_KEY: service})
        messages = [image_command_message()[0] for _ in range(3)]
        for user_id, (message, language) in enumerate(
            zip(messages, ["ru", "en", "en"], strict=True), start=1
        ):
            await asyncio.wait_for(
                lissajous(image_update(message, user_id, language), context), timeout=2
            )

        messages[2].reply_text.assert_awaited_once_with(tr("en", "generation.capacity"))
        assert len(context.tasks) == 2
        await asyncio.wait_for(both_started.wait(), timeout=2)
        assert all(not task.done() for task in context.tasks)
        finish.set()
        await asyncio.wait_for(asyncio.gather(*context.tasks), timeout=2)
        assert service.generate.call_count == 2
        messages[2].reply_photo.assert_not_awaited()
        for message, language in zip(messages[:2], ["ru", "en"], strict=True):
            message.reply_text.assert_awaited_once_with(tr(language, "generation.started"))
            assert message.reply_photo.await_args.kwargs["caption"] == tr(
                language, "caption.lissajous", seed=12345
            )

        await lissajous(image_update(messages[2], 3), context)
        await asyncio.wait_for(context.tasks[-1], timeout=2)
        assert service.generate.call_count == 3

    asyncio.run(run())


@pytest.mark.parametrize(
    ("callback", "caption_key", "outcome"),
    [
        (lissajous, "caption.lissajous", "success"),
        (spirograph, "caption.spirograph.inside", "success"),
        (fractal_tree, "caption.fractal_tree", "success"),
        (random_image, "caption.lissajous", "success"),
        (lissajous, "caption.lissajous", "render_error"),
        (lissajous, "caption.lissajous", "delivery_error"),
    ],
)
def test_generation_keeps_accepted_language_and_next_request_uses_new_language(
    monkeypatch, callback, caption_key, outcome
) -> None:
    async def run() -> None:
        started = asyncio.Event()
        finish = asyncio.Event()

        async def to_thread(generate):
            started.set()
            await finish.wait()
            return generate()

        monkeypatch.setattr(handlers.asyncio, "to_thread", to_thread)
        monkeypatch.setattr(handlers.secrets, "choice", lambda commands: commands[0])
        service = generation_service()
        context = image_context(
            {
                LISSAJOUS_SERVICE_KEY: service,
                SPIROGRAPH_SERVICE_KEY: service,
                FRACTAL_TREE_SERVICE_KEY: service,
            }
        )
        first, status = image_command_message()
        update = image_update(first, language_code="ru-RU")
        if outcome == "render_error":
            service.generate.side_effect = RuntimeError("render failed")
        elif outcome == "delivery_error":
            first.reply_photo.side_effect = RuntimeError("upload failed")

        await callback(update, context)
        # Even changes before the scheduled task starts cannot affect its language.
        update.effective_user.language_code = "en-US"
        await asyncio.wait_for(started.wait(), timeout=2)
        first.reply_text.assert_awaited_once_with(tr("ru", "generation.started"))

        # The same user can already get help and a busy reply in the new language.
        help_message, _ = image_command_message()
        await help_command(image_update(help_message, language_code="en-US"), context)
        help_message.reply_text.assert_awaited_once_with(build_help_text("en"))
        busy_message, _ = image_command_message()
        await callback(image_update(busy_message, language_code="en-US"), context)
        busy_message.reply_text.assert_awaited_once_with(tr("en", "generation.busy"))

        finish.set()
        await asyncio.wait_for(context.tasks[0], timeout=2)
        if outcome == "success":
            assert first.reply_photo.await_args.kwargs["caption"] == tr(
                "ru", caption_key, seed=12345
            )
            status.edit_text.assert_not_awaited()
        else:
            status.edit_text.assert_awaited_once_with(tr("ru", "generation.error"))

        service.generate.side_effect = generation_service().generate.side_effect
        next_message, _ = image_command_message()
        await callback(image_update(next_message, language_code="en-US"), context)
        await asyncio.wait_for(context.tasks[-1], timeout=2)
        next_message.reply_text.assert_awaited_once_with(tr("en", "generation.started"))
        assert next_message.reply_photo.await_args.kwargs["caption"] == tr(
            "en", caption_key, seed=12345
        )

    asyncio.run(run())


def test_user_remains_busy_during_image_delivery() -> None:
    async def run() -> None:
        uploading = asyncio.Event()
        finish = asyncio.Event()

        async def upload(**kwargs):
            uploading.set()
            await finish.wait()

        service = generation_service()
        context = image_context({LISSAJOUS_SERVICE_KEY: service})
        first, _ = image_command_message()
        first.reply_photo.side_effect = upload
        await asyncio.wait_for(lissajous(image_update(first), context), timeout=2)
        await asyncio.wait_for(uploading.wait(), timeout=2)
        repeat, _ = image_command_message()
        await asyncio.wait_for(lissajous(image_update(repeat), context), timeout=2)
        repeat.reply_text.assert_awaited_once_with(tr("ru", "generation.busy"))
        service.generate.assert_called_once_with()
        finish.set()
        await asyncio.wait_for(context.tasks[0], timeout=2)

    asyncio.run(run())


@pytest.mark.parametrize(
    "failure", ["status", "render", "delivery", "report", "cleanup"]
)
def test_failures_release_user_and_global_capacity(failure) -> None:
    async def run() -> None:
        service = generation_service()
        context = image_context({LISSAJOUS_SERVICE_KEY: service}, max_concurrent=1)
        message, status = image_command_message()
        error = RuntimeError("temporary failure")
        if failure == "status":
            message.reply_text.side_effect = error
        elif failure in {"render", "report"}:
            service.generate.side_effect = error
            if failure == "report":
                status.edit_text.side_effect = error
        elif failure == "delivery":
            message.reply_photo.side_effect = error
        else:
            status.delete.side_effect = error

        await lissajous(image_update(message), context)
        await asyncio.gather(*context.tasks, return_exceptions=True)

        context.bot_data[LISSAJOUS_SERVICE_KEY] = generation_service()
        retry, _ = image_command_message()
        await lissajous(image_update(retry), context)
        await context.tasks[-1]
        retry.reply_photo.assert_awaited_once()

    asyncio.run(run())


def test_cancellation_before_job_starts_releases_capacity() -> None:
    async def run() -> None:
        service = generation_service()
        context = image_context({LISSAJOUS_SERVICE_KEY: service}, max_concurrent=1)
        message, _ = image_command_message()
        await lissajous(image_update(message), context)
        task = context.tasks[0]
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        service.generate.assert_not_called()

        await lissajous(image_update(message), context)
        await context.tasks[-1]
        message.reply_photo.assert_awaited_once()

    asyncio.run(run())


def test_failed_task_registration_releases_capacity() -> None:
    async def run() -> None:
        service = generation_service()
        context = image_context({LISSAJOUS_SERVICE_KEY: service}, max_concurrent=1)
        create_task = context.application.create_task
        context.application.create_task = Mock(
            side_effect=RuntimeError("scheduling failed")
        )
        message, _ = image_command_message()
        with pytest.raises(RuntimeError, match="scheduling failed"):
            await lissajous(image_update(message), context)
        service.generate.assert_not_called()

        context.application.create_task = create_task
        await lissajous(image_update(message), context)
        await context.tasks[-1]
        message.reply_photo.assert_awaited_once()

    asyncio.run(run())


@pytest.mark.parametrize(
    "callback", [lissajous, spirograph, fractal_tree, random_image]
)
def test_updates_without_message_do_not_start_jobs(callback) -> None:
    context = image_context({})
    asyncio.run(callback(SimpleNamespace(message=None), context))
    assert context.tasks == []


def test_updates_without_user_do_not_start_jobs() -> None:
    service = generation_service()
    context = image_context({LISSAJOUS_SERVICE_KEY: service})
    message, _ = image_command_message()
    asyncio.run(
        lissajous(SimpleNamespace(message=message, effective_user=None), context)
    )
    assert context.tasks == []
    message.reply_text.assert_not_awaited()
