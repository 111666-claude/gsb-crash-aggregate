import random
import unittest

from crashes.core import Crashes


class ReferenceCrashes:
    """直观参考实现：滑动窗口 + 分指纹限额 + 幂等。"""

    def __init__(self, rate_limit, window_ms):
        self.rate_limit = rate_limit
        self.window_ms = window_ms
        self.seen_ids = set()
        self.accepted = []
        self.dropped = 0

    def report(self, report_id, fingerprint, now_ms):
        if report_id in self.seen_ids:
            return False
        self.seen_ids.add(report_id)
        oldest = now_ms - self.window_ms
        in_window = [
            ts
            for _, fp, ts in self.accepted
            if fp == fingerprint and oldest < ts <= now_ms
        ]
        if len(in_window) >= self.rate_limit:
            self.dropped += 1
            return False
        self.accepted.append((report_id, fingerprint, now_ms))
        return True

    def count(self, fingerprint):
        return sum(1 for _, fp, _ in self.accepted if fp == fingerprint)


class SlidingWindowTest(unittest.TestCase):
    def test_window_slides_and_old_reports_expire(self):
        book = Crashes(rate_limit=2, window_ms=1000)
        self.assertTrue(book.report("r1", "f1", 0))
        self.assertTrue(book.report("r2", "f1", 0))
        self.assertFalse(book.report("r3", "f1", 500))
        self.assertTrue(book.report("r4", "f1", 1001))
        self.assertEqual(book.count("f1"), 3)
        self.assertEqual(book.dropped_count(), 1)

    def test_report_exactly_on_boundary_is_expired(self):
        book = Crashes(rate_limit=1, window_ms=1000)
        self.assertTrue(book.report("r1", "f1", 1000))
        self.assertTrue(book.report("r2", "f1", 2000))
        self.assertEqual(book.count("f1"), 2)


class PerFingerprintLimitTest(unittest.TestCase):
    def test_limit_is_scoped_per_fingerprint(self):
        book = Crashes(rate_limit=2, window_ms=1000)
        self.assertTrue(book.report("r1", "f1", 0))
        self.assertTrue(book.report("r2", "f1", 0))
        self.assertTrue(book.report("r3", "f2", 0))
        self.assertFalse(book.report("r4", "f1", 0))
        self.assertEqual(book.count("f1"), 2)
        self.assertEqual(book.count("f2"), 1)
        self.assertEqual(book.dropped_count(), 1)

    def test_limit_reapplies_after_window_expires(self):
        book = Crashes(rate_limit=2, window_ms=1000)
        self.assertTrue(book.report("r1", "f1", 0))
        self.assertTrue(book.report("r2", "f1", 0))
        self.assertFalse(book.report("r3", "f1", 500))
        self.assertTrue(book.report("r4", "f1", 1000))
        self.assertTrue(book.report("r5", "f1", 1001))
        self.assertEqual(book.count("f1"), 4)
        self.assertEqual(book.dropped_count(), 1)


class IdempotencyTest(unittest.TestCase):
    def test_duplicate_report_id_ignored(self):
        book = Crashes(rate_limit=10, window_ms=1000)
        self.assertTrue(book.report("r1", "f1", 0))
        self.assertFalse(book.report("r1", "f1", 10))
        self.assertEqual(book.count("f1"), 1)
        self.assertEqual(book.dropped_count(), 0)

    def test_duplicate_of_dropped_report_neither_counts_nor_drops(self):
        book = Crashes(rate_limit=1, window_ms=1000)
        self.assertTrue(book.report("r1", "f1", 0))
        self.assertFalse(book.report("r2", "f1", 0))
        self.assertFalse(book.report("r2", "f1", 0))
        self.assertEqual(book.count("f1"), 1)
        self.assertEqual(book.dropped_count(), 1)


class QueryCostTest(unittest.TestCase):
    def test_scanned_does_not_grow_with_query_count(self):
        book = Crashes(rate_limit=1_000_000, window_ms=1000)
        for index in range(3000):
            book.report("r-%d" % index, "f-%d" % index, index)
        for _ in range(3000):
            book.count("f-0")
        self.assertLessEqual(book.scanned_count(), 3000)

    def test_scanned_is_amortized_per_report(self):
        book = Crashes(rate_limit=1, window_ms=1000)
        total = 5000
        for index in range(total):
            book.report("r-%d" % index, "f1", index * 1000)
        for _ in range(total):
            book.count("f1")
        self.assertLessEqual(book.scanned_count(), total)
        self.assertEqual(book.count("f1"), total)


class DeterminismTest(unittest.TestCase):
    def test_same_sequence_gives_same_results(self):
        events = [
            ("r1", "f1", 0),
            ("r2", "f1", 0),
            ("r1", "f1", 5),
            ("r3", "f1", 500),
            ("r4", "f2", 600),
            ("r5", "f1", 1000),
            ("r6", "f1", 1001),
        ]
        first = Crashes(rate_limit=2, window_ms=1000)
        second = Crashes(rate_limit=2, window_ms=1000)
        results1 = [first.report(*event) for event in events]
        results2 = [second.report(*event) for event in events]
        self.assertEqual(results1, results2)
        for fingerprint in ("f1", "f2"):
            self.assertEqual(first.count(fingerprint), second.count(fingerprint))
        self.assertEqual(first.dropped_count(), second.dropped_count())


class DifferentialTest(unittest.TestCase):
    def test_matches_reference_on_random_scenarios(self):
        rng = random.Random(20261004)
        for _ in range(200):
            rate_limit = rng.randint(1, 4)
            window_ms = rng.randint(100, 2000)
            actual = Crashes(rate_limit, window_ms)
            reference = ReferenceCrashes(rate_limit, window_ms)

            id_pool = list(range(rng.randint(1, 12)))
            fingerprints = ["f%d" % i for i in range(rng.randint(1, 4))]
            now_ms = 0
            for _ in range(rng.randint(1, 80)):
                now_ms += rng.randint(0, 2500)
                report_id = "id-%d" % rng.choice(id_pool)
                fingerprint = rng.choice(fingerprints)
                self.assertEqual(
                    actual.report(report_id, fingerprint, now_ms),
                    reference.report(report_id, fingerprint, now_ms),
                )

            for fingerprint in fingerprints:
                self.assertEqual(actual.count(fingerprint), reference.count(fingerprint))
            self.assertEqual(actual.dropped_count(), reference.dropped)


if __name__ == "__main__":
    unittest.main()
