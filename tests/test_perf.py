"""性能验收：数万条交易规模（开发文档第 14 章）。

默认跑 20,000 笔；用 KNOT_PERF_COUNT 调整，KNOT_PERF_SKIP=1 可跳过。
"""

from __future__ import annotations

import importlib.util
import os
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_bench():
    spec = importlib.util.spec_from_file_location("性能基准", ROOT / "scripts" / "性能基准.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PerformanceTest(unittest.TestCase):
    @unittest.skipIf(os.environ.get("KNOT_PERF_SKIP") == "1", "KNOT_PERF_SKIP=1")
    def test_large_ledger(self) -> None:
        bench = _load_bench()
        count = int(os.environ.get("KNOT_PERF_COUNT", "20000"))
        with tempfile.TemporaryDirectory() as tmp:
            ledger = bench.generate(count, Path(tmp) / "main.knot")
            started = time.perf_counter()
            outcome = bench.benchmark(ledger)
            elapsed = time.perf_counter() - started

        self.assertEqual(outcome["错误数"], 0)
        self.assertGreaterEqual(outcome["交易数"], count)  # 含一笔期初
        # 解析 + 校验 + 报表 + SQL 聚合的总时限（宽松上限，避免 CI 抖动）
        self.assertLess(elapsed, 60.0, f"{count} 笔用时 {elapsed:.1f}s")
        print(
            f"\n性能：[{count} 笔] 解析校验 {outcome['解析与校验（秒）']}s，"
            f"报表查询 {outcome['报表与查询（秒）']}s，总计 {elapsed:.2f}s"
        )


if __name__ == "__main__":
    unittest.main()
