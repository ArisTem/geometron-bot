import asyncio
import logging

from telegram import InputFile, Update
from telegram.ext import ContextTypes

from geometron_bot.generation.service import LissajousGenerationService

logger = logging.getLogger(__name__)

LISSAJOUS_SERVICE_KEY = "lissajous_generation_service"


async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    del context
    if update.message is not None:
        await update.message.reply_text("Бот работает 🟢")


async def lissajous(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Generate and send a Lissajous image with its reproducible seed."""
    if update.message is None:
        return

    try:
        service: LissajousGenerationService = context.bot_data[
            LISSAJOUS_SERVICE_KEY
        ]
        result = await asyncio.to_thread(service.generate)
    except Exception:
        logger.exception("Failed to generate a Lissajous image")
        await update.message.reply_text(
            "Не удалось создать изображение. Попробуйте ещё раз."
        )
        return

    photo = InputFile(
        result.image,
        filename=f"lissajous-{result.seed}.png",
    )
    await update.message.reply_photo(
        photo=photo,
        caption=f"Кривая Лиссажу\nSeed: {result.seed}",
    )


async def handle_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    del update
    logger.error("Unhandled error while processing an update", exc_info=context.error)
