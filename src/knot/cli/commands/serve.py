from __future__ import annotations

import sys
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
    p.set_defaults(func=run)


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

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print()
    finally:
        server.shutdown()
        server.server_close()
    return 0
