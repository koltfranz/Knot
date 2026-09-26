from __future__ import annotations

import sys
import threading
import webbrowser
from pathlib import Path

from knot.cli.ansi import GREEN, YELLOW, style
from knot.core.normalize import KnotError
from knot.web.server import create_server

BANNER = """结绳 Knot 本地服务已启动
  地址：{url}
  账本：{ledger}
  {token_hint}
  提示：本服务仅供本机使用，请勿直接暴露到公网。按 Ctrl+C 停止。"""


def add_parser(sub) -> None:
    p = sub.add_parser("serve", aliases=["服务"], help="启动本地 Web 服务")
    p.add_argument("--端口", "--port", dest="port", type=int, default=5000, metavar="端口")
    p.add_argument("--host", dest="host", default="127.0.0.1", metavar="地址")
    p.add_argument(
        "--口令",
        "--token",
        dest="token",
        default=None,
        metavar="口令",
        help="绑定非本机地址时必须设置",
    )
    p.add_argument("--静默", dest="quiet", action="store_true", help="不打印访问日志")
    p.add_argument(
        "--打开浏览器",
        "--open",
        dest="open_browser",
        action="store_true",
        default=None,
        help="启动后自动打开浏览器",
    )
    p.add_argument(
        "--不打开浏览器",
        "--no-open",
        dest="no_open_browser",
        action="store_true",
        help="即使处于交互终端也不打开浏览器",
    )
    p.set_defaults(func=run)


def should_open_browser(args) -> bool:
    """默认行为：交互式终端下自动打开浏览器；显式开关优先。"""
    if getattr(args, "no_open_browser", False):
        return False
    if getattr(args, "open_browser", None):
        return True
    return sys.stdin.isatty()


def open_browser_later(url: str, delay: float = 0.6) -> threading.Timer:
    timer = threading.Timer(delay, webbrowser.open, args=(url,))
    timer.daemon = True
    timer.start()
    return timer


def run(args) -> int:
    ledger = Path(args.ledger)
    try:
        server = create_server(
            ledger, host=args.host, port=args.port, token=args.token, quiet=args.quiet
        )
    except OSError as exc:
        raise KnotError(f"无法监听 {args.host}:{args.port}：{exc}") from exc

    host = args.host if args.host not in ("0.0.0.0", "::") else "127.0.0.1"
    url = f"http://{host}:{server.server_address[1]}/"
    token_hint = "口令：已启用（请求需带 口令）" if args.token else "口令：未启用（仅本机可访问）"
    print(style(BANNER.format(url=url, ledger=ledger, token_hint=token_hint), GREEN))
    if args.host in ("0.0.0.0", "::"):
        print(style("警告：已绑定所有网卡，请确保处于可信内网。", YELLOW), file=sys.stderr)

    if should_open_browser(args):
        # 口令只随打开请求带给浏览器，不打印到终端
        open_browser_later(url + (f"?口令={args.token}" if args.token else ""))
        print(style("已尝试在默认浏览器中打开（--不打开浏览器 可关闭该行为）", GREEN))

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print()
    finally:
        server.shutdown()
        server.server_close()
    return 0
