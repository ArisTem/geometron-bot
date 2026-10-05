import json
from unittest.mock import Mock

import pytest

from geometron_bot.telegram_bot import app, localization
from geometron_bot.telegram_bot.config import Config
from geometron_bot.telegram_bot.localization import (
    CatalogError,
    initialize_localization,
    tr,
)


@pytest.fixture(autouse=True)
def uncached_catalogs():
    localization._load_catalogs.cache_clear()
    yield
    localization._load_catalogs.cache_clear()


@pytest.fixture
def catalog_files(tmp_path, monkeypatch):
    locales = tmp_path / "locales"
    locales.mkdir()
    resource_files = Mock(return_value=tmp_path)
    monkeypatch.setattr(localization, "files", resource_files)

    def write(ru='{"message": "Привет {name}"}', en='{"message": "Hello {name}"}'):
        (locales / "ru.json").write_text(ru, encoding="utf-8")
        (locales / "en.json").write_text(en, encoding="utf-8")
        return locales

    write()
    return write, resource_files


@pytest.mark.parametrize(
    ("language", "expected"),
    [("ru", "Привет Alice"), ("en", "Hello Alice")],
)
def test_translation_selects_language_and_formats_parameters(
    catalog_files, language, expected
):
    assert tr(language, "message", name="Alice") == expected


@pytest.mark.parametrize("language", ["de", "", "ru-RU", "EN"])
def test_unknown_language_falls_back_to_english(catalog_files, language):
    assert tr(language, "message", name="Alice") == "Hello Alice"


def test_alternating_languages_does_not_change_other_translations(catalog_files):
    assert tr("ru", "message", name="Alice") == "Привет Alice"
    assert tr("en", "message", name="Alice") == "Hello Alice"
    assert tr("ru", "message", name="Alice") == "Привет Alice"


def test_missing_translation_uses_english_catalog(monkeypatch):
    monkeypatch.setattr(
        localization, "_load_catalogs", lambda: {"ru": {}, "en": {"message": "Hello {name}"}}
    )
    assert tr("ru", "message", name="Geometron") == "Hello Geometron"


def test_unknown_key_is_an_implementation_error(catalog_files):
    with pytest.raises(KeyError, match="missing.key"):
        tr("ru", "missing.key")


def test_missing_template_parameter_is_an_implementation_error(catalog_files):
    with pytest.raises(KeyError, match="name"):
        tr("ru", "message")


def test_catalogs_are_loaded_only_once(catalog_files):
    write, resource_files = catalog_files
    initialize_localization()
    assert tr("ru", "message", name="Geometron") == "Привет Geometron"
    assert tr("en", "message", name="Geometron") == "Hello Geometron"
    write(ru="broken JSON", en="broken JSON")
    initialize_localization()
    assert tr("en", "message", name="Geometron") == "Hello Geometron"
    assert resource_files.call_count == 2


def test_package_resources_work_outside_repository(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    initialize_localization()
    assert tr("ru", "ping.text").strip()
    assert tr("en", "caption.fractal_tree", seed=0).strip()


@pytest.mark.parametrize(
    ("source", "error"),
    [
        ("{", "Could not load"),
        ('{"message": "one", "message": "two"}', "Duplicate key"),
        ("[]", "JSON object"),
        ("null", "JSON object"),
        ('{"message": null}', "nonempty string"),
        ('{"message": 42}', "nonempty string"),
        ('{"message": {}}', "nonempty string"),
        ('{"message": ""}', "nonempty string"),
        ('{"message": "  \\n"}', "nonempty string"),
        ('{"other": "Hello {name}"}', "different keys"),
        ('{"message": "Hello {seed}"}', "parameters differ"),
        ('{"message": "Hello {}"}', "simple named fields"),
        ('{"message": "Hello {0}"}', "simple named fields"),
        ('{"message": "Hello {name.first}"}', "simple named fields"),
        ('{"message": "Hello {name[0]}"}', "simple named fields"),
        ('{"message": "Hello {name:{width}}"}', "Nested format fields"),
        ('{"message": "Hello {name!z}"}', "Unsupported field conversion"),
        ('{"message": "Hello {name"}', "expected"),
    ],
)
@pytest.mark.parametrize("language", ["ru", "en"])
def test_invalid_catalogs_fail_initialization(catalog_files, source, error, language):
    write, _ = catalog_files
    write(**{language: source})
    with pytest.raises(CatalogError, match=error) as raised:
        initialize_localization()
    assert f"{language}.json" in str(raised.value)


def test_missing_catalog_fails_initialization(catalog_files):
    write, _ = catalog_files
    locales = write()
    (locales / "en.json").unlink()
    with pytest.raises(CatalogError, match="en.json"):
        initialize_localization()


def test_non_utf8_catalog_fails_initialization(catalog_files):
    write, _ = catalog_files
    locales = write()
    (locales / "ru.json").write_bytes(b"\xff")
    with pytest.raises(CatalogError, match="ru.json"):
        initialize_localization()


def test_parameter_order_repetition_and_escaped_braces_are_supported(catalog_files):
    write, _ = catalog_files
    write(
        ru=json.dumps({"message": "{{Seed}}: {seed:04d}; {name}; {seed}"}),
        en=json.dumps({"message": "{name}; {{Seed}}: {seed:04d}"}),
    )
    assert tr("ru", "message", seed=42, name="Geometron") == (
        "{Seed}: 0042; Geometron; 42"
    )
    assert tr("en", "message", seed=42, name="Geometron") == (
        "Geometron; {Seed}: 0042"
    )


def test_invalid_catalog_stops_application_before_statistics_or_telegram(
    catalog_files, tmp_path, monkeypatch
):
    write, _ = catalog_files
    write(ru="broken JSON")
    application = Mock()
    monkeypatch.setattr(app, "Application", application)
    database = tmp_path / "stats.sqlite3"
    with pytest.raises(CatalogError, match="ru.json"):
        app.create_application(Config("123:test-token", database, "secret"))
    application.builder.assert_not_called()
    assert not database.exists()
