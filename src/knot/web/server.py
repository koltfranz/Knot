"""本地 Web 服务：ThreadingHTTPServer + 中文路由 + SSE 变更推送。"""

from __future__ import annotations

import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from knot.core.normalize import KnotError
from knot.web.service import LedgerService

STATIC_DIR = Path(__file__).resolve().parent / "static"
MIME = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
}

PUBLIC_PATHS = ("/", "/index.html", "/app.js", "/style.css")


def _json_bytes(payload) -> bytes:
    return json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    server_version = "Knot"
    protocol_version = "HTTP/1.1"
    service: LedgerService
    quiet: bool = False

    # ---------- 路由 ----------

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        query = {key: values[-1] for key, values in parse_qs(parsed.query).items()}
        try:
            if path == "/api/变更":
                if not self._authorized(query):
                    self._json({"错误": "未授权"}, status=401)
                    return
                self._sse()
                return
            if path.startswith("/api/"):
                if not self._authorized(query):
                    self._json({"错误": "未授权"}, status=401)
                    return
                self._api(path, query)
                return
            self._static(path)
        except KnotError as exc:
            self._json({"错误": str(exc)}, status=400)
        except BrokenPipeError:
            return
        except Exception as exc:
            self._json({"错误": f"服务端异常：{exc}"}, status=500)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            self._json({"错误": "请求体不是合法 JSON"}, status=400)
            return
        try:
            if not self._authorized(payload):
                self._json({"错误": "未授权"}, status=401)
                return
            self._write(path, payload)
        except KnotError as exc:
            self._json({"错误": str(exc)}, status=400)
        except Exception as exc:
            self._json({"错误": f"服务端异常：{exc}"}, status=500)

    def _api(self, path: str, query: dict) -> None:
        if path == "/api/概览":
            self._json(self.service.index())
        elif path == "/api/流水":
            self._json(self.service.transactions(query))
        elif path == "/api/余额":
            self._json(self.service.balances(query))
        elif path == "/api/科目":
            self._json(self.service.accounts(query))
        elif path == "/api/别名":
            self._json(self.service.aliases(query))
        elif path == "/api/待分类":
            self._json(self.service.uncategorized(query))
        elif path == "/api/预算":
            self._json(self.service.budgets(query))
        elif path.startswith("/api/报表/"):
            self._json(self.service.report(path.split("/", 3)[3], query))
        elif path.startswith("/api/图表/"):
            self._json(self.service.chart(path.split("/", 3)[3], query))
        else:
            self._json({"错误": f"未知接口：{path}"}, status=404)

    def _write(self, path: str, payload: dict) -> None:
        if path in ("/api/记一笔", "/api/add"):
            self._json(self.service.add_entry(payload))
        elif path in ("/api/归类", "/api/classify"):
            self._json(self.service.classify(payload))
        elif path in ("/api/导入预览", "/api/import/preview"):
            self._json(self.service.import_preview(payload))
        elif path in ("/api/导入", "/api/import"):
            self._json(self.service.import_apply(payload))
        else:
            self._json({"错误": f"未知写接口：{path}"}, status=404)

    # ---------- 响应 ----------

    def _authorized(self, source: dict) -> bool:
        if not self.service.token:
            return True
        header = self.headers.get("X-Knot-Token") if self.headers else None
        return self.service.token in (
            header,
            source.get("口令"),
            source.get("token"),
        )

    def _json(self, payload, status: int = 200) -> None:
        body = _json_bytes(payload)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _static(self, path: str) -> None:
        relative = "index.html" if path in ("/", "") else path.lstrip("/")
        candidate = (STATIC_DIR / relative).resolve()
        if not str(candidate).startswith(str(STATIC_DIR)) or not candidate.is_file():
            self.send_error(404, "Not Found")
            return
        body = candidate.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", MIME.get(candidate.suffix, "application/octet-stream"))
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _sse(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        try:
            for change in self.service.watch():
                payload = json.dumps(change, ensure_ascii=False)
                self.wfile.write(f"data: {payload}\n\n".encode())
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            return

    def log_message(self, format: str, *args) -> None:
        if not self.quiet:
            sys.stderr.write(f"[knot] {self.address_string()} {format % args}\n")


def create_server(
    ledger: Path,
    host: str = "127.0.0.1",
    port: int = 5000,
    token: str | None = None,
    quiet: bool = False,
) -> ThreadingHTTPServer:
    if host not in ("127.0.0.1", "localhost", "::1") and not token:
        raise KnotError("绑定非本机地址时必须设置 --口令（且不建议暴露到公网）")

    handler = type(
        "KnotHandler", (Handler,), {"service": LedgerService(ledger, token), "quiet": quiet}
    )
    server = ThreadingHTTPServer((host, port), handler)
    server.daemon_threads = True
    return server


def start_background(
    ledger: Path,
    host: str = "127.0.0.1",
    port: int = 0,
    token: str | None = None,
    quiet: bool = True,
) -> tuple[ThreadingHTTPServer, threading.Thread, str]:
    server = create_server(ledger, host, port, token, quiet)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    actual_port = server.server_address[1]
    return server, thread, f"http://{host}:{actual_port}"
