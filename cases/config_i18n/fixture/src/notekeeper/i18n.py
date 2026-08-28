"""Localization and theme resolution."""

from __future__ import annotations


STRINGS = {
    "en": {
        "title": "NoteKeeper",
        "saved": "Note saved",
    }
}


def resolve_language(language: str, system_locale: str | None) -> str:
    return "en" if language == "auto" else language


def resolve_theme(theme: str, system_dark: bool) -> str:
    return "light" if theme == "auto" else theme


def translate(key: str, language: str) -> str:
    return STRINGS[language][key]
