"""Stable presentation helper unrelated to planning decisions."""


def format_summary(selected: list[str], value: int) -> str:
    return f"{', '.join(selected)} | value={value}"
