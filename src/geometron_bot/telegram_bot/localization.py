"""Validated package catalogs and explicit, per-call translation."""

import json
from functools import cache
from importlib.resources import files
from string import Formatter

from telegram import Update

from geometron_bot.telegram_bot.config import ConfigurationError
from geometron_bot.telegram_bot.languages import DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES


class CatalogError(ConfigurationError):
    """Raised when the bundled localization catalogs are invalid."""


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate key: {key!r}.")
        result[key] = value
    return result


def _parameters(template: str) -> set[str]:
    parameters = set()
    for _, field, format_spec, conversion in Formatter().parse(template):
        if field is None:
            continue
        if not field.isidentifier():
            raise ValueError("Only simple named fields are supported.")
        if "{" in format_spec or "}" in format_spec:
            raise ValueError("Nested format fields are not supported.")
        if conversion not in (None, "s", "r", "a"):
            raise ValueError("Unsupported field conversion.")
        parameters.add(field)
    return parameters


def _read_catalog(language: str) -> tuple[dict[str, str], dict[str, set[str]]]:
    name = f"{language}.json"
    try:
        source = (
            files(__package__).joinpath("locales", name).read_text(encoding="utf-8")
        )
        catalog = json.loads(source, object_pairs_hook=_unique_object)
    except (OSError, UnicodeError, ValueError) as error:
        raise CatalogError(
            f"Could not load localization catalog {name}: {error}"
        ) from error

    if not isinstance(catalog, dict):
        raise CatalogError(f"Localization catalog {name} must be a JSON object.")

    parameters = {}
    for key, value in catalog.items():
        if not isinstance(value, str) or not value.strip():
            raise CatalogError(
                f"Localization catalog {name}, key {key!r}: expected a nonempty string."
            )
        try:
            parameters[key] = _parameters(value)
        except ValueError as error:
            raise CatalogError(
                f"Localization catalog {name}, key {key!r}: {error}"
            ) from error
    return catalog, parameters


@cache
def _load_catalogs() -> dict[str, dict[str, str]]:
    catalogs = {}
    parameters = {}
    for language in SUPPORTED_LANGUAGES:
        catalogs[language], parameters[language] = _read_catalog(language)

    default_keys = catalogs[DEFAULT_LANGUAGE].keys()
    for language in SUPPORTED_LANGUAGES:
        if catalogs[language].keys() != default_keys:
            missing = sorted(default_keys - catalogs[language].keys())
            extra = sorted(catalogs[language].keys() - default_keys)
            raise CatalogError(
                f"Localization catalog {language}.json has different keys from "
                f"{DEFAULT_LANGUAGE}.json: missing={missing}, extra={extra}."
            )
        for key in default_keys:
            if parameters[language][key] != parameters[DEFAULT_LANGUAGE][key]:
                raise CatalogError(
                    f"Localization catalog {language}.json, key {key!r}: "
                    f"parameters differ from {DEFAULT_LANGUAGE}.json."
                )
    return catalogs


def initialize_localization() -> None:
    """Load and validate all catalogs before the application starts polling."""
    _load_catalogs()


def get_telegram_language(update: Update) -> str:
    """Resolve the current update's language without retaining user state."""
    user = update.effective_user
    language_code = user.language_code if user is not None else None
    if not language_code:
        return DEFAULT_LANGUAGE
    language = language_code.lower().split("-", 1)[0]
    return language if language in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE


def tr(language: str, key: str, **values: object) -> str:
    catalogs = _load_catalogs()
    default = catalogs[DEFAULT_LANGUAGE]
    selected = catalogs.get(language, default)
    template = selected.get(key)
    if template is None:
        template = default[key]
    return template.format(**values)
