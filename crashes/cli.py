"""命令行入口：跑崩溃聚合样例。"""

import argparse

from .core import Crashes


def build_parser():
    parser = argparse.ArgumentParser(prog="crash-aggregate", description="崩溃上报聚合")
    parser.add_argument("--sample", default="window", help="window / scope / dup / scan")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.sample == "window":
        book = Crashes(rate_limit=2, window_ms=1000)
        book.report("r1", "f1", 0)
        book.report("r2", "f1", 0)
        second = book.report("r3", "f1", 5000)
        print("second=%s count=%d" % (str(second).lower(), book.count("f1")))
    elif args.sample == "scope":
        book = Crashes(rate_limit=2, window_ms=1000)
        book.report("r1", "f1", 0)
        book.report("r2", "f1", 0)
        second = book.report("r3", "f2", 0)
        print("second=%s count=%d" % (str(second).lower(), book.count("f2")))
    elif args.sample == "dup":
        book = Crashes(rate_limit=10, window_ms=1000)
        book.report("r1", "f1", 0)
        second = book.report("r1", "f1", 10)
        print("second=%s count=%d" % (str(second).lower(), book.count("f1")))
    elif args.sample == "scan":
        book = Crashes(rate_limit=1000000, window_ms=1000)
        for index in range(3000):
            book.report("r-%d" % index, "f-%d" % index, index)
        for _ in range(3000):
            book.count("f-0")
        print("scanned=%d" % book.scanned_count())
    else:
        raise SystemExit("需要 --sample window|scope|dup|scan")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
