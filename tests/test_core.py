import unittest

from crashes.core import Crashes


class CrashesTest(unittest.TestCase):
    def test_empty_count(self):
        self.assertEqual(Crashes(2, 1000).count("f1"), 0)

    def test_report_then_count(self):
        book = Crashes(2, 1000)
        book.report("r1", "f1", 0)
        self.assertEqual(book.count("f1"), 1)

    def test_two_fingerprints_are_counted(self):
        book = Crashes(2, 1000)
        book.report("r1", "f1", 0)
        book.report("r2", "f2", 0)
        self.assertEqual(book.count("f2"), 1)

    def test_counters_start_at_zero(self):
        book = Crashes(2, 1000)
        self.assertEqual(book.scanned_count(), 0)
        self.assertEqual(book.dropped_count(), 0)


if __name__ == "__main__":
    unittest.main()
