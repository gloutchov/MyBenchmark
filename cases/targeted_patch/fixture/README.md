# PocketLedger

PocketLedger is a tiny in-memory EUR ledger.

## Usage

Create a `Ledger`, add `credit`, `debit`, or `refund` entries, and inspect `balance()`.
CSV imports accept the columns `kind`, `amount`, and optional `note`.

## Behavior Notes

### `balance()` calculation

The balance is calculated as:
- **credits** are added to the total
- **debits** are subtracted from the total
- **refunds** are also subtracted from the total (same as debits)

Example:
```python
ledger = Ledger()
ledger.add_entry(100, "credit")      # balance = 100
ledger.add_entry(30, "debit")        # balance = 70
ledger.add_entry(20, "refund")       # balance = 50
assert ledger.balance() == 50
```

### `add_entry()` validation

The following values are rejected with a `ValueError`:
- **Booleans** (`True`, `False`) - even though `bool` is a subclass of `int` in Python
- **NaN** (Not a Number)
- **Infinity** (`+inf`, `-inf`)
- **Zero or negative numbers**

Example:
```python
ledger = Ledger()
ledger.add_entry(10.5, "credit")     # OK
try:
    ledger.add_entry(True, "credit")  # ValueError: amount must be a number, not a boolean
except ValueError:
    pass
try:
    ledger.add_entry(float('nan'), "credit")  # ValueError: amount must be a finite number
except ValueError:
    pass
```

### `import_csv()` atomicity

CSV imports are **atomic**: if any row is invalid, **no entries are added**.
Invalid rows include:
- Non-numeric amounts
- NaN or infinity values
- Zero or negative amounts
- Invalid kinds (must be `credit`, `debit`, or `refund`)

Example:
```python
ledger = Ledger()
csv_text = "kind,amount,note\ncredit,100,test\ndebit,invalid,coffee\n"
count = ledger.import_csv(csv_text)  # count == 0 (atomic rejection)
assert len(ledger.entries) == 0
```

## Development

```bash
python -m unittest discover -s tests -v
```

### Running specific test groups

```bash
# All tests
python -m unittest discover -s tests -v

# Only regression tests
python -m unittest tests.test_ledger.LedgerTests -v

# Test balance() behavior
python -m unittest tests.test_ledger.LedgerTests::test_balance_subtracts_refund -v
```

## API Reference

### `Ledger.add_entry(amount: float, kind: str, note: str = "") -> Entry`

Add a new entry to the ledger.

**Parameters:**
- `amount`: Positive finite number (not boolean, not NaN/inf)
- `kind`: One of `"credit"`, `"debit"`, or `"refund"`
- `note`: Optional description (default: empty string)

**Returns:** The created `Entry` object.

**Raises:** `ValueError` if amount is invalid or kind is unsupported.

### `Ledger.balance() -> float`

Calculate the current balance of the ledger.

**Returns:** The sum of credits minus debits and refunds.

### `Ledger.import_csv(text: str) -> int`

Import entries from a CSV string.

**Parameters:**
- `text`: CSV text with columns `kind`, `amount`, and optional `note`

**Returns:** Number of successfully imported rows (0 if any row was invalid).

**Note:** This operation is atomic - if any row is invalid, no entries are added.
