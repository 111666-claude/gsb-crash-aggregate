# crash-aggregate

崩溃上报聚合：按栈指纹聚合计数，并对同一指纹做频率限制，只用 Python 标准库。

```
python3 -m crashes.cli --sample window
python3 -m crashes.cli --sample scope
python3 -m crashes.cli --sample dup
python3 -m crashes.cli --sample scan
python3 -m unittest discover -s tests -v
```

## 口径（README 为准）

- **滑动窗口**：只统计 `[now_ms - window_ms, now_ms)` 内接受过的上报，正好等于窗口边界的算过期。
- **分指纹限额**：同一个指纹在窗口内接受的上报数不超过 `rate_limit`，超出的丢弃并计入 `dropped`，
  `report` 返回 False；不同指纹各算各的。
- **幂等**：同一个 `report_id` 只接受一次，重复上报返回 False，不计数也不计丢弃。
- **回收与不变量**：窗口外的上报必须回收，`count` 只反映窗口内接受的次数；同一串上报重复执行结果相同。
- **查询代价**：`count` 不许全扫上报表，`scanned_count()` 不随上报总数乘查询次数增长。
- **规模**：200 万条上报、每秒 10 万次上报与查询，单次摊还 O(1)。

## 输出契约（不改格式）

```
second=.. count=..
scanned=..
```

## 目录

```
crashes/core.py   滑动窗口、分指纹限额与幂等
crashes/cli.py    命令行入口
tests/            unittest 用例
```
