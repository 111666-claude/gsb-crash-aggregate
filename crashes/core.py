"""崩溃上报聚合：按栈指纹聚合计数，并对同一指纹做频率限制。

口径（README 为准）：
- 滑动窗口：限额只统计 `(now_ms - window_ms, now_ms]` 内接受的上报，
  正好等于 `now_ms - window_ms` 的算过期；
- 分指纹限额：每个指纹各自限流，窗口内超出 rate_limit 的丢弃并计入 dropped；
- 幂等：同一个 report_id 只处理一次，重复上报返回 False，不计数也不计丢弃；
- count 为每个指纹累计接受的次数，O(1) 查询，不全扫上报表。

假设上报的 now_ms 单调不减（崩溃上报是时间流），窗口回收摊还 O(1)。
"""

from collections import deque


class Crashes:
    """崩溃聚合台账。"""

    def __init__(self, rate_limit=2, window_ms=1000):
        self.rate_limit = rate_limit
        self.window_ms = window_ms
        self.counts = {}
        self.dropped = 0
        self.scanned = 0
        self._seen_ids = set()
        self._windows = {}

    def report(self, report_id, fingerprint, now_ms):
        """上报一次崩溃；重复 report_id 或超出分指纹限额时返回 False。"""
        if report_id in self._seen_ids:
            return False
        self._seen_ids.add(report_id)
        window = self._windows.get(fingerprint)
        if window is None:
            window = deque()
            self._windows[fingerprint] = window
        floor = now_ms - self.window_ms
        while window and window[0] <= floor:
            window.popleft()
        if len(window) >= self.rate_limit:
            if not window:
                del self._windows[fingerprint]
            self.dropped += 1
            return False
        window.append(now_ms)
        self.counts[fingerprint] = self.counts.get(fingerprint, 0) + 1
        return True

    def count(self, fingerprint):
        """某个指纹累计接受的次数；O(1)，不全扫上报表。"""
        self.scanned += 1
        return self.counts.get(fingerprint, 0)

    def dropped_count(self):
        return self.dropped

    def scanned_count(self):
        return self.scanned
