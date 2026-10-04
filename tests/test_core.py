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


import random


class SlidingWindowTest(unittest.TestCase):
    def test_window_slides_and_rate_limit_resets(self):
        book = Crashes(2, 1000)
        self.assertTrue(book.report("r1", "f1", 0))
        self.assertTrue(book.report("r2", "f1", 0))
        self.assertFalse(book.report("r3", "f1", 500))
        self.assertTrue(book.report("r4", "f1", 5000))
        self.assertEqual(book.count("f1"), 3)
        self.assertEqual(book.dropped_count(), 1)

    def test_boundary_timestamp_is_expired(self):
        book = Crashes(1, 1000)
        self.assertTrue(book.report("r1", "f1", 0))
        self.assertTrue(book.report("r2", "f1", 1000))
        self.assertEqual(book.dropped_count(), 0)

    def test_rate_limit_is_per_fingerprint(self):
        book = Crashes(1, 1000)
        self.assertTrue(book.report("r1", "f1", 0))
        self.assertFalse(book.report("r2", "f1", 1))
        self.assertTrue(book.report("r3", "f2", 1))
        self.assertEqual(book.count("f1"), 1)
        self.assertEqual(book.count("f2"), 1)
        self.assertEqual(book.dropped_count(), 1)


class IdempotencyTest(unittest.TestCase):
    def test_duplicate_report_id_accepted_once(self):
        book = Crashes(10, 1000)
        self.assertTrue(book.report("r1", "f1", 0))
        self.assertFalse(book.report("r1", "f1", 10))
        self.assertEqual(book.count("f1"), 1)
        self.assertEqual(book.dropped_count(), 0)

    def test_dropped_report_id_retry_not_counted_twice(self):
        book = Crashes(1, 1000)
        self.assertTrue(book.report("r1", "f1", 0))
        self.assertFalse(book.report("r2", "f1", 1))
        self.assertFalse(book.report("r2", "f1", 2))
        self.assertEqual(book.dropped_count(), 1)
        self.assertEqual(book.count("f1"), 1)


class QueryCostTest(unittest.TestCase):
    def test_scanned_does_not_depend_on_report_volume(self):
        book = Crashes(1000000, 1000)
        for index in range(3000):
            book.report("r-%d" % index, "f-%d" % index, index)
        before = book.scanned_count()
        for _ in range(3000):
            book.count("f-0")
        self.assertEqual(book.scanned_count() - before, 3000)

    def test_large_volume_stays_amortized_constant(self):
        book = Crashes(3, 100)
        total = 200000
        for index in range(total):
            book.report("r-%d" % index, "f-%d" % (index % 10), index)
        accepted = sum(book.count("f-%d" % fingerprint) for fingerprint in range(10))
        self.assertEqual(accepted + book.dropped_count(), total)


class DeterminismTest(unittest.TestCase):
    def test_same_sequence_same_result(self):
        def run():
            book = Crashes(2, 50)
            outcomes = []
            for index in range(500):
                outcomes.append(book.report("r-%d" % (index % 100), "f-%d" % (index % 5), index * 7))
            counts = [book.count("f-%d" % fingerprint) for fingerprint in range(5)]
            return outcomes, counts, book.dropped_count()

        self.assertEqual(run(), run())


class _Reference:
    """「滑动窗口 + 分指纹限额 + 幂等」的直接实现（全量扫描，仅供比对）。"""

    def __init__(self, rate_limit, window_ms):
        self.rate_limit = rate_limit
        self.window_ms = window_ms
        self.seen = set()
        self.accepted = []
        self.dropped = 0

    def report(self, report_id, fingerprint, now_ms):
        if report_id in self.seen:
            return False
        self.seen.add(report_id)
        in_window = sum(
            1
            for _, other, timestamp in self.accepted
            if other == fingerprint and timestamp > now_ms - self.window_ms
        )
        if in_window >= self.rate_limit:
            self.dropped += 1
            return False
        self.accepted.append((report_id, fingerprint, now_ms))
        return True

    def count(self, fingerprint):
        return sum(1 for _, other, _ in self.accepted if other == fingerprint)

    def dropped_count(self):
        return self.dropped


class ReferenceCheckTest(unittest.TestCase):
    def test_matches_reference_implementation(self):
        rng = random.Random(20261004)
        for _ in range(200):
            rate_limit = rng.randint(1, 4)
            window_ms = rng.randint(10, 200)
            book = Crashes(rate_limit, window_ms)
            reference = _Reference(rate_limit, window_ms)
            now_ms = 0
            nonce = 0
            report_ids = []
            for _ in range(rng.randint(20, 120)):
                now_ms += rng.randint(0, 30)
                fingerprint = "f-%d" % rng.randint(0, 4)
                if report_ids and rng.random() < 0.3:
                    report_id = rng.choice(report_ids)
                else:
                    report_id = "r-%d" % nonce
                    nonce += 1
                    report_ids.append(report_id)
                self.assertEqual(
                    book.report(report_id, fingerprint, now_ms),
                    reference.report(report_id, fingerprint, now_ms),
                )
                self.assertEqual(book.count(fingerprint), reference.count(fingerprint))
                self.assertEqual(book.dropped_count(), reference.dropped_count())
