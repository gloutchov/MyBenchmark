"""PocketLedger domain model."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from io import StringIO


@dataclass(frozen=True)
class Entry:
    amount: float
    kind: str
    note: str = ""


class Ledger:
    def __init__(self) -> None:
        self._entries: list[Entry] = []

    @property
    def entries(self) -> tuple[Entry, ...]:
        return tuple(self._entries)

    def add_entry(self, amount: float, kind: str, note: str = "") -> Entry:
        if amount <= 0:
            raise ValueError("amount must be a positive number")
        if kind not in {"credit", "debit", "refund"}:
            raise ValueError("unsupported entry kind")
        entry = Entry(float(amount), kind, note)
        self._entries.append(entry)
        return entry

    def balance(self) -> float:
        total = 0.0
        for entry in self._entries:
            if entry.kind == "credit":
                total += entry.amount
            elif entry.kind == "debit":
                total -= entry.amount
        return total

    def import_csv(self, text: str) -> int:
        reader = csv.DictReader(StringIO(text))
        count = 0
        for row in reader:
            self.add_entry(float(row["amount"]), row["kind"], row.get("note", ""))
            count += 1
        return count
