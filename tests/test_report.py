from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import date
from decimal import Decimal
from pathlib import Path

from knot.cli.main import main
from knot.core.book import build
from knot.core.chart import (
    KIND_BAR,
    KIND_HEATMAP,
    KIND_LINE,
    KIND_PIE,
    KIND_TREEMAP,
    ChartSeries,
    ChartSpec,
    downsample,
    render_svg,
    spec_calendar_heatmap,
    spec_category_treemap,
    spec_expense_pie,
    spec_monthly_flow,
    spec_net_worth,
)
from knot.core.model import Options
from knot.core.parser import Parser
from knot.core.report import (
    balance_over_time,
    category_trend,
    expense_by_category,
    monthly_flow,
    net_worth_trend,
    render_monthly_flow,
    render_summary,
)

LEDGER = """option "strict" "off"

2026-01-01 open 资产:现金 CNY
2026-01-01 open 收入:工资 CNY
2026-01-01 open 费用:餐饮:外卖
2026-01-01 open 费用:交通
2026-01-01 open 权益:期初

2026-01-01 * "期初"
  资产:现金     10,000.00 CNY
  权益:期初

2026-01-15 * "工资"  收入:工资  -8,000.00 CNY  @ 资产:现金
2026-01-20 * "外卖"  费用:餐饮:外卖  50.00 CNY  @ 资产:现金
2026-02-10 * "工资"  收入:工资  -8,000.00 CNY  @ 资产:现金
2026-02-11 * "地铁"  费用:交通  30.00 CNY  @ 资产:现金
2026-02-12 * "外卖"  费用:餐饮:外卖  70.00 CNY  @ 资产:现金
2026-03-05 * "外卖"  费用:餐饮:外卖  90.00 CNY  @ 资产:现金
"""


def sample_book():
    directives, _diags = Parser(LEDGER, "test.knot").parse()
    book, _book_diags = build(directives, Options(strict="off"), {"test.knot": LEDGER.splitlines()})
    return book


class ReportTest(unittest.TestCase):
    def test_monthly_flow(self) -> None:
        rows = monthly_flow(sample_book())
        self.assertEqual([row["月份"] for row in rows], ["2026-01", "2026-02", "2026-03"])
        self.assertEqual(rows[0]["收入"], Decimal("8000.00"))
        self.assertEqual(rows[0]["支出"], Decimal("50.00"))
        self.assertEqual(rows[0]["净额"], Decimal("7950.00"))
        self.assertEqual(rows[1]["支出"], Decimal("100.00"))
        self.assertEqual(rows[2]["净额"], Decimal("-90.00"))

    def test_monthly_flow_range(self) -> None:
        rows = monthly_flow(sample_book(), date(2026, 2, 1), date(2026, 2, 28))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["月份"], "2026-02")

    def test_net_worth_trend(self) -> None:
        rows = net_worth_trend(sample_book())
        self.assertEqual(rows[0]["CNY"], Decimal("17950.00"))
        self.assertEqual(rows[1]["CNY"], Decimal("25850.00"))
        self.assertEqual(rows[2]["CNY"], Decimal("25760.00"))

    def test_expense_by_category(self) -> None:
        rows = expense_by_category(sample_book(), depth=2)
        self.assertEqual(rows[0], ("费用:餐饮", Decimal("210.00")))
        self.assertEqual(rows[1], ("费用:交通", Decimal("30.00")))

    def test_category_trend_and_balance(self) -> None:
        book = sample_book()
        trend = category_trend(book, "费用:餐饮")
        self.assertEqual(
            [row["金额"] for row in trend], [Decimal("50.00"), Decimal("70.00"), Decimal("90.00")]
        )

        balances = balance_over_time(book, "资产:现金")
        self.assertEqual([row["余额"] for row in balances][-1], Decimal("25760.00"))

    def test_renderers(self) -> None:
        text = render_monthly_flow(monthly_flow(sample_book()))
        self.assertIn("2026-01", text)
        self.assertIn("8,000.00", text)
        self.assertIn("交易数", render_summary(sample_book().summary()))


class ChartDataTest(unittest.TestCase):
    def test_specs(self) -> None:
        book = sample_book()
        flow = spec_monthly_flow(book)
        self.assertEqual(flow.kind, KIND_BAR)
        self.assertEqual(len(flow.series), 2)
        self.assertEqual(len(flow.labels), 3)

        net = spec_net_worth(book)
        self.assertEqual(net.kind, KIND_LINE)
        self.assertEqual(net.series[0].values[-1], Decimal("25760.00"))

        pie = spec_expense_pie(book)
        self.assertEqual(pie.kind, KIND_PIE)
        self.assertEqual(pie.labels[0], "费用:餐饮")

        treemap = spec_category_treemap(book)
        self.assertEqual(treemap.kind, KIND_TREEMAP)

        heat = spec_calendar_heatmap(book, 2026)
        self.assertEqual(heat.kind, KIND_HEATMAP)
        self.assertEqual(len(heat.labels), 4)

    def test_downsample(self) -> None:
        labels = [f"2026-{i:03d}" for i in range(1000)]
        values = [Decimal(i) for i in range(1000)]
        new_labels, new_values = downsample(labels, values, limit=100)
        self.assertLessEqual(len(new_values), 100)
        self.assertEqual(len(new_labels), len(new_values))


class SvgTest(unittest.TestCase):
    def test_bar_svg(self) -> None:
        svg = render_svg(spec_monthly_flow(sample_book()))
        self.assertTrue(svg.startswith("<svg"))
        self.assertIn("月度收支", svg)
        self.assertIn("<rect", svg)
        self.assertIn("8,000.00", svg)

    def test_line_svg(self) -> None:
        svg = render_svg(spec_net_worth(sample_book()))
        self.assertIn("<polyline", svg)
        self.assertIn("净资产趋势", svg)

    def test_pie_svg(self) -> None:
        svg = render_svg(spec_expense_pie(sample_book()))
        self.assertIn("<path", svg)
        self.assertIn("费用:餐饮", svg)

    def test_treemap_svg(self) -> None:
        svg = render_svg(spec_category_treemap(sample_book()))
        self.assertIn("<rect", svg)
        self.assertIn("支出分类面积", svg)

    def test_heatmap_svg(self) -> None:
        svg = render_svg(spec_calendar_heatmap(sample_book(), 2026))
        self.assertIn("2026 年消费日历", svg)
        self.assertIn("<rect", svg)

    def test_empty_data(self) -> None:
        empty = ChartSpec(kind=KIND_PIE, title="空", labels=[], series=[ChartSeries("支出", [])])
        self.assertIn("<svg", render_svg(empty))
        self.assertIn("暂无数据", render_svg(empty))


class ReportCommandTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.ledger = Path(self._tmp.name) / "main.knot"
        self.ledger.write_text(LEDGER, encoding="utf-8")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _run(self, *argv: str) -> tuple[int, str]:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = main(["--账本", str(self.ledger), *argv])
        return code, buffer.getvalue()

    def test_report_summary(self) -> None:
        code, output = self._run("报")
        self.assertEqual(code, 0)
        self.assertIn("交易数", output)

    def test_report_monthly_json(self) -> None:
        code, output = self._run("报", "收支", "--json")
        self.assertEqual(code, 0)
        payload = json.loads(output)
        self.assertEqual(payload[0]["月份"], "2026-01")
        self.assertEqual(payload[0]["收入"], "8,000.00")

    def test_report_category(self) -> None:
        code, output = self._run("报", "分类")
        self.assertEqual(code, 0)
        self.assertIn("费用:餐饮", output)

    def test_report_account(self) -> None:
        code, output = self._run("报", "科目", "--科目", "餐饮")
        self.assertEqual(code, 0)
        self.assertIn("费用:餐饮", output)

    def test_report_account_requires_target(self) -> None:
        code, _output = self._run("报", "科目")
        self.assertEqual(code, 2)

    def test_chart_to_file(self) -> None:
        target = Path(self._tmp.name) / "图.svg"
        code, output = self._run("图", "支出", "--按", "分类", "--月", "2026-02", "-o", str(target))
        self.assertEqual(code, 0)
        self.assertTrue(target.exists())
        self.assertIn("<svg", target.read_text(encoding="utf-8"))
        self.assertIn("已生成图表", output)

    def test_chart_json(self) -> None:
        code, output = self._run("图", "净资产", "--json")
        self.assertEqual(code, 0)
        payload = json.loads(output)
        self.assertEqual(payload["类型"], "line")

    def test_chart_heatmap_by_year(self) -> None:
        code, output = self._run("图", "日历", "--年", "2026")
        self.assertEqual(code, 0)
        self.assertIn("2026 年消费日历", output)

    def test_chart_unknown_topic(self) -> None:
        code, _output = self._run("图", "不存在")
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
