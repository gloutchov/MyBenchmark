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
        # Reject booleans (bool is subclass of int in Python)
        if isinstance(amount, bool):
            raise ValueError("amount must be a number, not a boolean")
        # Reject NaN and infinity
        import math
        if math.isnan(amount) or math.isinf(amount):
            raise ValueError("amount must be a finite number")
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
            elif entry.kind == "debit" or entry.kind == "refund":
                total -= entry.amount
        return total

    def import_csv(self, text: str) -> int:
        """Import entries from CSV. Atomic: if any row is invalid, no entries are added."""
        lines = text.strip().splitlines()
        if not lines:
            return 0
        reader = csv.DictReader(lines)
        # First pass: validate all rows before adding any
        valid_rows = []
        has_invalid_row = False
        for i, row in enumerate(reader):
            try:
                amount_str = row["amount"]
                kind = row["kind"]
                note = row.get("note", "")
                # Check for invalid string representations first (before float conversion)
                if amount_str.lower() in ("nan", "+inf", "-inf", "inf"):
                    raise ValueError("amount must be a finite number")
                # Convert to float and validate
                amount = float(amount_str)
                # Reject booleans (bool is subclass of int in Python) - check after float conversion
                if isinstance(amount, bool):
                    raise ValueError("amount must be a number, not a boolean")
                if amount <= 0:
                    raise ValueError("amount must be a positive number")
                if kind not in {"credit", "debit", "refund"}:
                    raise ValueError("unsupported entry kind")
                valid_rows.append((i + 1, row))  # (line_number, row)
            except Exception as e:
                # Invalid row - mark that we have an invalid row
                has_invalid_row = True
        # If any row was invalid, don't add any entries (atomic behavior)
        if has_invalid_row:
            return 0
        # Second pass: add only valid rows atomically
        for _, row in valid_rows:
            self.add_entry(float(row["amount"]), row["kind"], row.get("note", ""))
        return len(valid_rows)
