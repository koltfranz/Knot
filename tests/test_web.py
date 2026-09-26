from __future__ import annotations

import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from knot.core.normalize import KnotError
from knot.web.server import create_server
from knot.web.service import LedgerService


def _url(base: str, path: str) -> str:
    """中文路径需按 URL 规则转义（浏览器会自动做，测试需显式）。"""
    return base + urllib.parse.quote(path, safe="/?=&")


LEDGER = """option "strict" "off"

2026-01-01 open 资产:现金 CNY
2026-01-01 open 权益:期初

2026-01-01 * "期初"
  资产:现金     1,000.00 CNY
  权益:期初

2026-01-20 * "外卖"  费用:餐饮:外卖  50.00 CNY  @ 资产:现金
2026-02-10 * "工资"  收入:工资  -8,000.00 CNY  @ 资产:现金
"""


def get(url: str, token: str | None = None):
    request = urllib.request.Request(url)
    if token:
        request.add_header("X-Knot-Token", token)
    with urllib.request.urlopen(request, timeout=5) as response:
        return response.status, json.loads(response.read().decode("utf-8"))


def post(url: str, payload: dict, token: str | None = None):
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    if token:
        request.add_header("X-Knot-Token", token)
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


class ServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.ledger = Path(self._tmp.name) / "main.knot"
        self.ledger.write_text(LEDGER, encoding="utf-8")
        self.service = LedgerService(self.ledger)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_index(self) -> None:
        payload = self.service.index()
        self.assertEqual(payload["交易数"], 3)
        self.assertEqual(payload["错误"], 0)
        self.assertIn("币种", payload)

    def test_transactions_and_filters(self) -> None:
        payload = self.service.transactions({"月": "2026-01"})
        self.assertEqual(payload["共"], 2)
        payload = self.service.transactions({"科目": "费用:餐饮"})
        self.assertEqual(payload["共"], 1)

    def test_balances_tree(self) -> None:
        payload = self.service.balances({})
        names = [row["科目"] for row in payload["树"]]
        self.assertIn("资产", names)
        self.assertIn("资产:现金", names)
        self.assertEqual(payload["科目"]["资产:现金"]["CNY"], "8,950.00")

    def test_accounts_with_trend(self) -> None:
        payload = self.service.accounts({})
        row = next(item for item in payload["科目"] if item["科目"] == "资产:现金")
        self.assertEqual(row["趋势"], ["950.00", "8,950.00"])

    def test_reports(self) -> None:
        sheet = self.service.report("资产负债表", {})["数据"]
        self.assertTrue(sheet["平衡"])
        self.assertEqual(str(sheet["资产合计"]), "8950.00")
        self.assertEqual(str(sheet["负债权益合计"]), "8950.00")
        income = self.service.report("利润表", {})["数据"]
        self.assertEqual(income["净利润"].__str__(), "7950.00")
        cash = self.service.report("现金流量表", {})["数据"]
        self.assertEqual(cash["经营"].__str__(), "7950.00")
        self.assertEqual(cash["筹资"].__str__(), "1000.00")

    def test_charts(self) -> None:
        spec = self.service.chart("净资产", {})
        self.assertEqual(spec["类型"], "line")
        spec = self.service.chart("分类", {})
        self.assertEqual(spec["类型"], "pie")
        spec = self.service.chart("日历", {"年": "2026"})
        self.assertEqual(spec["类型"], "heatmap")

    def test_aliases(self) -> None:
        payload = self.service.aliases({})
        self.assertTrue(any(row["别名"] == "招行" for row in payload["别名"]))

    def test_add_entry_and_cache_invalidation(self) -> None:
        before = self.service.index()["交易数"]
        result = self.service.add_entry(
            {
                "金额": "38",
                "科目": "餐饮",
                "来自": "现金",
                "摘要": "午饭",
                "日期": "2026-03-01",
            }
        )
        self.assertIn("已记入", result)
        self.assertEqual(self.service.index()["交易数"], before + 1)
        self.assertEqual(self.service.transactions({"月": "2026-03"})["共"], 1)

    def test_uncategorized_and_classify(self) -> None:
        self.service.add_entry(
            {"金额": "12", "科目": "费用:待分类", "来自": "现金", "日期": "2026-03-02"}
        )
        payload = self.service.uncategorized({})
        self.assertEqual(payload["合计笔数"], 1)

        target = self.service.add_entry(
            {
                "金额": "20",
                "科目": "费用:待分类",
                "来自": "现金",
                "日期": "2026-03-03",
                "收款方": "星巴克",
            }
        )
        self.assertTrue(target["已记入"].endswith(".knot"))
        result = self.service.classify({"收款方": "星巴克", "科目": "费用:餐饮:咖啡"})
        self.assertGreaterEqual(result["已归类"], 1)
        text = Path(result["文件"][0]).read_text(encoding="utf-8")
        self.assertIn("费用:餐饮:咖啡", text)

    def test_import_preview_and_apply(self) -> None:
        data = Path(__file__).resolve().parents[1] / "schema" / "测试数据" / "导入" / "微信.csv"
        preview = self.service.import_preview({"来源": "微信", "文件": [str(data)]})
        self.assertFalse(preview["已写入"])
        self.assertEqual(preview["结果"][0]["可导入"], 5)

        applied = self.service.import_apply({"来源": "微信", "文件": [str(data)]})
        self.assertTrue(applied["已写入"])
        again = self.service.import_preview({"来源": "微信", "文件": [str(data)]})
        self.assertEqual(again["结果"][0]["可导入"], 0)
        self.assertEqual(again["结果"][0]["重复"], 5)

    def test_unknown_report_raises(self) -> None:
        with self.assertRaises(KnotError):
            self.service.report("不存在", {})


class ServerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        cls.ledger = Path(cls._tmp.name) / "main.knot"
        cls.ledger.write_text(LEDGER, encoding="utf-8")
        cls.server = create_server(cls.ledger, port=0, quiet=True)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()
        cls._tmp.cleanup()

    def test_index_page(self) -> None:
        with urllib.request.urlopen(f"{self.base}/", timeout=5) as response:
            html = response.read().decode("utf-8")
        self.assertEqual(response.status, 200)
        self.assertIn("结绳 Knot", html)
        self.assertIn("记一笔", html)

    def test_static_assets(self) -> None:
        for path in ("/app.js", "/style.css"):
            with urllib.request.urlopen(f"{self.base}{path}", timeout=5) as response:
                body = response.read().decode("utf-8")
            self.assertEqual(response.status, 200)
            self.assertTrue(body)

    def test_api_endpoints(self) -> None:
        for path, key in (
            ("/api/概览", "交易数"),
            ("/api/流水", "流水"),
            ("/api/余额", "树"),
            ("/api/科目", "科目"),
            ("/api/别名", "别名"),
            ("/api/待分类", "待分类"),
            ("/api/报表/资产负债表", "数据"),
            ("/api/图表/净资产", "系列"),
        ):
            status, payload = get(_url(self.base, path))
            self.assertEqual(status, 200, path)
            self.assertIn(key, payload, path)

    def test_post_entry(self) -> None:
        status, payload = post(
            _url(self.base, "/api/记一笔"),
            {
                "金额": "9.9",
                "科目": "餐饮",
                "来自": "现金",
                "日期": "2026-04-01",
                "摘要": "测试",
            },
        )
        self.assertEqual(status, 200)
        self.assertIn("已记入", payload)

    def test_unknown_api_404(self) -> None:
        try:
            get(_url(self.base, "/api/不存在"))
            self.fail("应当返回 404")
        except urllib.error.HTTPError as exc:
            self.assertEqual(exc.code, 404)

    def test_traversal_blocked(self) -> None:
        try:
            with urllib.request.urlopen(f"{self.base}/../pyproject.toml", timeout=5) as response:
                self.assertEqual(response.status, 404)
        except urllib.error.HTTPError as exc:
            self.assertIn(exc.code, (400, 404))

    def test_sse_first_event(self) -> None:
        with urllib.request.urlopen(_url(self.base, "/api/变更"), timeout=15) as response:
            self.assertIn("text/event-stream", response.headers.get("Content-Type"))
            # 触发一次变更，等待推送
            self.ledger.write_text(
                LEDGER + '\n2026-05-01 * "追加"  费用:餐饮  1.00 CNY  @ 资产:现金\n',
                encoding="utf-8",
            )
            chunk = response.readline().decode("utf-8")
        self.assertTrue(chunk.startswith("data:"))
        self.assertIn("事件", chunk)

    def test_token_required_when_configured(self) -> None:
        server = create_server(self.ledger, port=0, token="s3cret", quiet=True)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_address[1]}"
        try:
            try:
                get(_url(base, "/api/概览"))
                self.fail("未带口令应当 401")
            except urllib.error.HTTPError as exc:
                self.assertEqual(exc.code, 401)
            status, payload = get(_url(base, "/api/概览"), token="s3cret")
            self.assertEqual(status, 200)
            self.assertIn("交易数", payload)
            status, payload = get(_url(base, "/api/概览?口令=s3cret"))
            self.assertEqual(status, 200)
        finally:
            server.shutdown()
            server.server_close()

    def test_public_host_requires_token(self) -> None:
        with self.assertRaises(KnotError):
            create_server(self.ledger, host="0.0.0.0", port=0)


if __name__ == "__main__":
    unittest.main()
