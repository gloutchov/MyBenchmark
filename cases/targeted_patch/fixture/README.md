# PocketLedger

PocketLedger is a tiny in-memory EUR ledger.

## Usage

Create a `Ledger`, add `credit`, `debit`, or `refund` entries, and inspect `balance()`.
CSV imports accept the columns `kind`, `amount`, and optional `note`.

## Development

```bash
python -m unittest discover -s tests -v
```
