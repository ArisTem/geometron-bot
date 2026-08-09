import logging

from geometron_bot.telegram_bot.app import create_application
from geometron_bot.telegram_bot.config import ConfigurationError, load_config


def configure_logging() -> None:
    logging.basicConfig(
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        level=logging.INFO,
    )


def main() -> None:
    configure_logging()
    logger = logging.getLogger(__name__)

    try:
        config = load_config()
    except ConfigurationError as error:
        logger.error("%s", error)
        raise SystemExit(1) from error

    application = create_application(config)
    logger.info("Starting Geometron bot")
    application.run_polling()
    logger.info("Geometron bot stopped")


if __name__ == "__main__":
    main()
