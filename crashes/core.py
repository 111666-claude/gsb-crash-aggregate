"""崩溃上报聚合：按栈指纹聚合计数，并对同一指纹做频率限制。

口径（见 README）：
- 滑动窗口：只统计 [now_ms - window_ms, now_ms) 内接受的上报，等于左边界的算过期。
- 分指纹限额：同一指纹窗口内接受数不超过 rate_limit，超出计入 dropped 并返回 False。
- 幂等：同一 report_id 只接受一次，重复上报返回 False，不计数也不计丢弃。
- 回收：窗口外的时间戳随上报摊还回收；count 是 O(1) 字典查询，不全扫上报表。
"""

from collections import deque


class Crashes:
    """崩溃聚合台账。"""

    def __init__(self, rate_limit=2, window_ms=1000):
        self.rate_limit = rate_limit
        self.window_ms = window_ms
        self.accepted = {}
        self.windows = {}
        self.seen_ids = set()
        self.dropped = 0
        self.scanned = 0

    def _reclaim(self, fingerprint, now_ms):
        """回收该指纹窗口外的时间戳；每条上报最多被回收一次，摊还 O(1)。"""
        dq = self.windows.get(fingerprint)
        if dq is None:
            return
        oldest = now_ms - self.window_ms
        while dq and dq[0] <= oldest:
            dq.popleft()
            self.scanned += 1
        if not dq:
            del self.windows[fingerprint]

    def report(self, report_id, fingerprint, now_ms):
        """上报一次崩溃。重复 report_id 返回 False，不计数也不计丢弃。"""
        if report_id in self.seen_ids:
            return False
        self.seen_ids.add(report_id)
        self._reclaim(fingerprint, now_ms)
        dq = self.windows.setdefault(fingerprint, deque())
        if len(dq) >= self.rate_limit:
            self.dropped += 1
            return False
        dq.append(now_ms)
        self.accepted[fingerprint] = self.accepted.get(fingerprint, 0) + 1
        return True

    def count(self, fingerprint):
        """某个指纹累计接受的次数。O(1) 字典查询，不全扫上报表。"""
        return self.accepted.get(fingerprint, 0)

    def dropped_count(self):
        return self.dropped

    def scanned_count(self):
        return self.scanned
