import sys
import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
