import logging
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from geometron_bot import __main__ as main_module
from geometron_bot.telegram_bot.config import ConfigurationError


def test_main_logs_application_version(monkeypatch, caplog) -> None:
    application = SimpleNamespace(run_polling=Mock())
    monkeypatch.setattr(main_module, "load_config", Mock(return_value=object()))
    monkeypatch.setattr(
        main_module,
        "create_application",
        Mock(return_value=application),
    )
    monkeypatch.setattr(
        main_module,
        "get_application_version",
        Mock(return_value="1.2.3"),
    )

    with caplog.at_level(logging.INFO, logger=main_module.__name__):
        main_module.main()

    startup_records = [
        record
        for record in caplog.records
        if record.name == main_module.__name__
        and record.getMessage().startswith("Starting Geometron bot")
    ]
    assert len(startup_records) == 1
    assert startup_records[0].levelno == logging.INFO
    assert "version=1.2.3" in startup_records[0].getMessage()
    application.run_polling.assert_called_once_with()


def test_application_version_falls_back_when_package_is_not_installed(
    monkeypatch,
) -> None:
    def raise_package_not_found(distribution_name: str) -> str:
        raise main_module.PackageNotFoundError(distribution_name)

    monkeypatch.setattr(main_module, "version", raise_package_not_found)

    assert main_module.get_application_version() == "unknown"


def test_main_stops_before_polling_on_statistics_configuration_error(
    monkeypatch, caplog
) -> None:
    monkeypatch.setattr(main_module, "load_config", Mock(return_value=object()))
    create_application = Mock(
        side_effect=ConfigurationError("STATS_DB_PATH database cannot be opened or initialized.")
    )
    monkeypatch.setattr(main_module, "create_application", create_application)

    with caplog.at_level(logging.ERROR, logger=main_module.__name__), pytest.raises(
        SystemExit
    ) as error:
        main_module.main()

    assert error.value.code == 1
    create_application.assert_called_once()
    assert "STATS_DB_PATH database cannot be opened or initialized." in caplog.text
