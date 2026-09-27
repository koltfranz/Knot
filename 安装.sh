#!/bin/sh
# 结绳 Knot 正式安装（macOS / Linux）
#
# 用法：
#   sh ./安装.sh
#   sh ./安装.sh --prefix ~/.local/share/knot --no-path -y
#   sh ./安装.sh --from knot-ledger          # 从 PyPI 安装（发布后可用）
#
# 安装后：新开终端即可使用全局命令 knot（knot --version / knot create / knot open）。
# 卸载：sh ./卸载.sh（不会删除账本文件）。
set -eu

PREFIX="${HOME}/.local/share/knot"
SOURCE=""
ADD_PATH=1
ASSUME_YES=0
BIN_DIR="${HOME}/.local/bin"
PROFILE="${HOME}/.profile"
MARKER_START="# >>> knot installer >>>"
MARKER_END="# <<< knot installer <<<"

usage() {
    cat <<'EOF'
结绳 Knot 安装脚本
  --prefix, --前缀 DIR    安装目录（默认 ~/.local/share/knot）
  --from,   --来源 TARGET pip 安装目标（默认脚本所在目录）
  --no-path, --不写PATH   不修改 ~/.profile
  -y, --yes               不提问
  -h, --help              显示帮助
EOF
}

while [ $# -gt 0 ]; do
    case "$1" in
        --prefix|--前缀)
            PREFIX="$2"
            shift 2
            ;;
        --from|--来源)
            SOURCE="$2"
            shift 2
            ;;
        --no-path|--不写PATH)
            ADD_PATH=0
            shift
            ;;
        -y|--yes)
            ASSUME_YES=1
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "未知参数：$1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
if [ -z "$SOURCE" ]; then
    SOURCE="$SCRIPT_DIR"
fi

echo "结绳 Knot 安装脚本"
echo "  安装目录：$PREFIX"
echo "  安装来源：$SOURCE"
if [ "$ASSUME_YES" -eq 0 ]; then
    printf "继续安装？(y/N) "
    read -r answer || answer=""
    case "$answer" in
        y|Y|yes|YES|是) ;;
        *)
            echo "已取消。"
            exit 0
            ;;
    esac
fi

PY=""
for candidate in python3 python; do
    if command -v "$candidate" >/dev/null 2>&1; then
        if "$candidate" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)'; then
            PY="$candidate"
            break
        fi
    fi
done
if [ -z "$PY" ]; then
    echo "错误：未找到 Python 3.11 或更高版本，请先安装。" >&2
    exit 2
fi

mkdir -p "$PREFIX"
if [ -x "$PREFIX/venv/bin/python" ]; then
    echo "复用已存在的虚拟环境（重复执行安装即升级）"
else
    echo "创建虚拟环境：$PREFIX/venv"
    "$PY" -m venv "$PREFIX/venv"
fi
VENV_PY="$PREFIX/venv/bin/python"

echo "安装 knot-ledger ..."
"$VENV_PY" -m pip install --quiet --upgrade pip
"$VENV_PY" -m pip install --quiet --upgrade "$SOURCE"

ENTRY="$PREFIX/venv/bin/knot"
if [ ! -x "$ENTRY" ]; then
    echo "错误：安装后未找到 $ENTRY，安装可能不完整。" >&2
    exit 2
fi

mkdir -p "$BIN_DIR"
if [ -e "$BIN_DIR/knot" ] && [ ! -L "$BIN_DIR/knot" ]; then
    echo "错误：$BIN_DIR/knot 已存在且不是本安装器创建的链接，请先手动处理。" >&2
    exit 2
fi
ln -sf "$ENTRY" "$BIN_DIR/knot"
echo "已创建命令链接：$BIN_DIR/knot"

if [ "$ADD_PATH" -eq 1 ]; then
    if grep -qF "$MARKER_START" "$PROFILE" 2>/dev/null; then
        echo "PATH 条目已存在：$PROFILE"
    else
        {
            echo ""
            echo "$MARKER_START"
            echo 'export PATH="$HOME/.local/bin:$PATH"'
            echo "$MARKER_END"
        } >> "$PROFILE"
        echo "已把 ~/.local/bin 写入 $PROFILE（重开终端或 source 后生效）"
    fi
else
    echo "按 --no-path 跳过 PATH 修改；可直接调用 $BIN_DIR/knot"
fi

VERSION=$("$ENTRY" --version 2>/dev/null || echo "knot")
cat > "$PREFIX/install.json" <<EOF
{
  "版本": "$VERSION",
  "来源": "$SOURCE",
  "安装目录": "$PREFIX",
  "命令目录": "$BIN_DIR",
  "安装时间": "$(date '+%Y-%m-%d %H:%M:%S')"
}
EOF

echo "运行自检 ..."
if ! "$ENTRY" 自检; then
    echo "警告：自检未全部通过，请按上方提示处理。"
fi

echo ""
echo "安装完成：$VERSION"
echo "  新开终端后可直接使用："
echo "    knot --version"
echo "    knot create 我的账本      # 新建账本（默认内容可直接改）"
echo "    knot open 我的账本        # 打开终端界面（鼠标可点选 / Ctrl+单击多选）"
echo "    knot 示例                 # 复制示例账本（演示全部功能与 7 种图表）"
echo "  卸载：sh $SCRIPT_DIR/卸载.sh（不会删除账本文件）"
