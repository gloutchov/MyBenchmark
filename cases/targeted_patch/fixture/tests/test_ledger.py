import sys
import unittest
from pathlib import Path
import math

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pocketledger import Ledger


class LedgerTests(unittest.TestCase):
    def test_credit_and_debit_balance(self):
        ledger = Ledger()
        ledger.add_entry(20, "credit")
        ledger.add_entry(3.5, "debit")
        self.assertEqual(16.5, ledger.balance())

    def test_rejects_non_positive_amount(self):
        with self.assertRaises(ValueError):
            Ledger().add_entry(0, "credit")

    def test_imports_csv(self):
        ledger = Ledger()
        count = ledger.import_csv("kind,amount,note\ncredit,4,coffee\n")
        self.assertEqual(1, count)
        self.assertEqual(4, ledger.balance())

    # Regression tests for balance() - must subtract both debit and refund
    def test_balance_subtracts_refund(self):
        """balance() must subtract both debit and refund entries."""
        ledger = Ledger()
        ledger.add_entry(100, "credit")
        ledger.add_entry(20, "debit")
        ledger.add_entry(30, "refund")
        # balance = 100 - 20 - 30 = 50
        self.assertEqual(50, ledger.balance())

    def test_balance_with_only_refund(self):
        """balance() must subtract refund entries."""
        ledger = Ledger()
        ledger.add_entry(100, "credit")
        ledger.add_entry(25, "refund")
        self.assertEqual(75, ledger.balance())

    def test_balance_with_only_debit(self):
        """balance() must subtract debit entries."""
        ledger = Ledger()
        ledger.add_entry(100, "credit")
        ledger.add_entry(25, "debit")
        self.assertEqual(75, ledger.balance())

    def test_balance_with_credit_debit_refund(self):
        """balance() with all three kinds."""
        ledger = Ledger()
        ledger.add_entry(100, "credit")
        ledger.add_entry(30, "debit")
        ledger.add_entry(20, "refund")
        # balance = 100 - 30 - 20 = 50
        self.assertEqual(50, ledger.balance())

    # Regression tests for add_entry() - must reject booleans and NaN/inf
    def test_add_entry_rejects_boolean_true(self):
        """add_entry() must reject boolean True."""
        with self.assertRaises(ValueError):
            Ledger().add_entry(True, "credit")

    def test_add_entry_rejects_boolean_false(self):
        """add_entry() must reject boolean False."""
        with self.assertRaises(ValueError):
            Ledger().add_entry(False, "credit")

    def test_add_entry_rejects_nan(self):
        """add_entry() must reject NaN."""
        with self.assertRaises(ValueError):
            Ledger().add_entry(float('nan'), "credit")

    def test_add_entry_rejects_pos_inf(self):
        """add_entry() must reject positive infinity."""
        with self.assertRaises(ValueError):
            Ledger().add_entry(float('inf'), "credit")

    def test_add_entry_rejects_neg_inf(self):
        """add_entry() must reject negative infinity."""
        with self.assertRaises(ValueError):
            Ledger().add_entry(float('-inf'), "credit")

    def test_add_entry_accepts_valid_float(self):
        """add_entry() accepts valid finite positive floats."""
        ledger = Ledger()
        entry = ledger.add_entry(10.5, "credit")
        self.assertEqual("credit", entry.kind)
        self.assertEqual(10.5, entry.amount)

    # Regression tests for import_csv() - must be atomic
    def test_import_csv_atomic_invalid_row(self):
        """import_csv() must be atomic: if any row is invalid, no entries are added."""
        ledger = Ledger()
        csv_text = "kind,amount,note\ncredit,100,test\ndebit,invalid,coffee\n"
        count = ledger.import_csv(csv_text)
        # Should reject the entire import due to invalid row
        self.assertEqual(0, count)
        self.assertEqual(0, len(ledger.entries))

    def test_import_csv_atomic_nan_row(self):
        """import_csv() must be atomic when a row contains NaN."""
        ledger = Ledger()
        csv_text = "kind,amount,note\ncredit,100,test\ndebit,nan,coffee\n"
        count = ledger.import_csv(csv_text)
        self.assertEqual(0, count)
        self.assertEqual(0, len(ledger.entries))

    def test_import_csv_atomic_inf_row(self):
        """import_csv() must be atomic when a row contains infinity."""
        ledger = Ledger()
        csv_text = "kind,amount,note\ncredit,100,test\ndebit,inf,coffee\n"
        count = ledger.import_csv(csv_text)
        self.assertEqual(0, count)
        self.assertEqual(0, len(ledger.entries))

    def test_import_csv_atomic_negative_amount(self):
        """import_csv() must be atomic when a row has negative amount."""
        ledger = Ledger()
        csv_text = "kind,amount,note\ncredit,100,test\ndebit,-5,coffee\n"
        count = ledger.import_csv(csv_text)
        self.assertEqual(0, count)
        self.assertEqual(0, len(ledger.entries))

    def test_import_csv_atomic_invalid_kind(self):
        """import_csv() must be atomic when a row has invalid kind."""
        ledger = Ledger()
        csv_text = "kind,amount,note\ncredit,100,test\ntransfer,50,coffee\n"
        count = ledger.import_csv(csv_text)
        self.assertEqual(0, count)
        self.assertEqual(0, len(ledger.entries))

    def test_import_csv_atomic_mixed_valid_invalid(self):
        """import_csv() must be atomic: valid rows before invalid are not added."""
        ledger = Ledger()
        csv_text = "kind,amount,note\ncredit,100,test\ndebit,20,coffee\nrefund,invalid,bad\ncredit,50,ok\n"
        count = ledger.import_csv(csv_text)
        # Should reject entire import due to invalid row
        self.assertEqual(0, count)
        self.assertEqual(0, len(ledger.entries))

    def test_import_csv_atomic_all_valid(self):
        """import_csv() accepts all valid rows."""
        ledger = Ledger()
        csv_text = "kind,amount,note\ncredit,100,test\ndebit,20,coffee\nrefund,30,bad\n"
        count = ledger.import_csv(csv_text)
        self.assertEqual(3, count)
        # balance = 100 - 20 - 30 = 50
        self.assertEqual(50, ledger.balance())

    def test_import_csv_empty(self):
        """import_csv() handles empty input."""
        ledger = Ledger()
        count = ledger.import_csv("")
        self.assertEqual(0, count)

    def test_import_csv_only_header(self):
        """import_csv() handles header-only CSV."""
        ledger = Ledger()
        csv_text = "kind,amount,note\n"
        count = ledger.import_csv(csv_text)
        self.assertEqual(0, count)


if __name__ == "__main__":
    unittest.main()
