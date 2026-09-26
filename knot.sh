#!/usr/bin/env sh
# 结绳 Knot 一键启动：自动准备环境后运行 CLI；不带参数进入菜单
set -e
cd "$(dirname "$0")"

PY=""
for candidate in python3 python; do
    if command -v "$candidate" >/dev/null 2>&1; then
        PY="$candidate"
        break
    fi
done
if [ -z "$PY" ]; then
    echo "未找到 Python，请先安装 Python 3.11 或更高版本。" >&2
    exit 2
fi

if [ ! -x ".venv/bin/python" ]; then
    echo "首次运行：创建虚拟环境并安装（仅此一次，需要联网）..."
    "$PY" -m venv .venv
    .venv/bin/python -m pip install --quiet --upgrade pip
    .venv/bin/python -m pip install --quiet -e .
fi

if [ "$#" -eq 0 ]; then
    exec .venv/bin/python -m knot 菜单
fi
exec .venv/bin/python -m knot "$@"
