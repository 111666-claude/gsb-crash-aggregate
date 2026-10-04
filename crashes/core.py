"""崩溃上报聚合：按栈指纹聚合计数，并对同一指纹做频率限制。

缺陷：频率窗口从不滑动、限额不分指纹（按全局历史次数算）、report_id 不幂等、
被丢弃的上报也计数、每次查询全扫上报表。
"""


class Crashes:
    """崩溃聚合台账。"""

    def __init__(self, rate_limit=2, window_ms=1000):
        self.rate_limit = rate_limit
        self.window_ms = window_ms
        self.counts = {}
        self.reports = []
        self.dropped = 0
        self.scanned = 0

    def report(self, report_id, fingerprint, now_ms):
        """上报一次崩溃。缺陷：按全局历史次数限流、report_id 不幂等。"""
        if len(self.reports) >= self.rate_limit:
            self.dropped += 1
            return False
        self.reports.append((report_id, fingerprint, now_ms))
        self.counts[fingerprint] = self.counts.get(fingerprint, 0) + 1
        return True

    def count(self, fingerprint):
        """某个指纹累计接受的次数。缺陷：全扫上报表。"""
        self.scanned += len(self.reports)
        return self.counts.get(fingerprint, 0)

    def dropped_count(self):
        return self.dropped

    def scanned_count(self):
        return self.scanned
