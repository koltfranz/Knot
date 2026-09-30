#!/bin/sh
# 结绳 Knot 一键卸载（macOS / Linux）
#
# 只清理安装目录（独立虚拟环境）与命令链接、~/.profile 中的 PATH 条目，
# 不依赖 Python，也不会删除任何账本文件。
#
# 用法：
#   sh ./卸载.sh
#   sh ./卸载.sh --prefix ~/.local/share/knot --dry-run -y
set -eu

PREFIX="${HOME}/.local/share/knot"
BIN_DIR="${HOME}/.local/bin"
PROFILE="${HOME}/.profile"
MARKER_START="# >>> knot installer >>>"
MARKER_END="# <<< knot installer <<<"
ASSUME_YES=0
DRY_RUN=0

usage() {
    cat <<'EOF'
结绳 Knot 卸载脚本
  --prefix, --前缀 DIR   安装目录（默认 ~/.local/share/knot）
  --dry-run, --试运行    只打印将执行的动作
  -y, --yes              不提问
  -h, --help             显示帮助
EOF
}

while [ $# -gt 0 ]; do
    case "$1" in
        --prefix|--前缀)
            PREFIX="$2"
            shift 2
            ;;
        --dry-run|--试运行)
            DRY_RUN=1
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

if [ -f "$PREFIX/install.json" ]; then
    recorded=$(sed -n 's/.*"命令目录": *"\([^"]*\)".*/\1/p' "$PREFIX/install.json" | head -n 1)
    version=$(sed -n 's/.*"版本": *"\([^"]*\)".*/\1/p' "$PREFIX/install.json" | head -n 1)
    if [ -n "$recorded" ]; then
        BIN_DIR="$recorded"
    fi
    echo "找到安装记录：${version:-未知}（命令目录 $BIN_DIR）"
else
    echo "未找到安装记录（install.json），按默认路径清理：$PREFIX"
fi

ledger_count=$(find "$PREFIX" -name '*.knot' 2>/dev/null | wc -l | tr -d ' ' || true)
echo "将清理："
echo "  命令链接：$BIN_DIR/knot"
echo "  安装目录：$PREFIX"
echo "  PATH 条目：$PROFILE（标记块）"
echo "账本数据通常不在这里；如安装在别处的账本不会被删除。"
if [ "${ledger_count:-0}" -gt 0 ]; then
    echo "注意：安装目录内发现 ${ledger_count} 个 .knot 账本文件，卸载会一并删除："
    find "$PREFIX" -name '*.knot' 2>/dev/null | head -n 5 | sed 's/^/  /'
    echo "如需保留，请先移动到其它目录再卸载。"
fi
if [ "$ASSUME_YES" -eq 0 ]; then
    printf "确认卸载？(y/N) "
    read -r answer || answer=""
    case "$answer" in
        y|Y|yes|YES|是) ;;
        *)
            echo "已取消。"
            exit 0
            ;;
    esac
fi

if [ "$DRY_RUN" -eq 1 ]; then
    echo "（试运行）未做任何修改。"
    exit 0
fi

if [ -L "$BIN_DIR/knot" ]; then
    target=$(readlink "$BIN_DIR/knot" || echo "")
    case "$target" in
        "$PREFIX"/*)
            rm -f "$BIN_DIR/knot"
            echo "已删除命令链接：$BIN_DIR/knot"
            ;;
        *)
            echo "跳过：$BIN_DIR/knot 指向 $target（不是本安装器创建的）"
            ;;
    esac
elif [ -e "$BIN_DIR/knot" ]; then
    echo "跳过：$BIN_DIR/knot 不是符号链接，请手动处理"
fi

if [ -f "$PROFILE" ] && grep -qF "$MARKER_START" "$PROFILE"; then
    awk -v start="$MARKER_START" -v end="$MARKER_END" '
        $0 == start { skip = 1; next }
        $0 == end { skip = 0; next }
        !skip { print }
    ' "$PROFILE" > "$PROFILE.knot-uninstall"
    mv "$PROFILE.knot-uninstall" "$PROFILE"
    echo "已移除 $PROFILE 中的 PATH 标记块"
fi

if [ "$(uname -s)" = "Darwin" ]; then
    APP_DIR="${HOME}/Applications/结绳 Knot.app"
    if [ -d "$APP_DIR" ]; then
        rm -rf "$APP_DIR"
        echo "已删除入口：$APP_DIR"
    fi
else
    DESKTOP_FILE="${HOME}/.local/share/applications/knot.desktop"
    if [ -f "$DESKTOP_FILE" ]; then
        rm -f "$DESKTOP_FILE"
        echo "已删除入口：$DESKTOP_FILE"
    fi
fi

if [ -d "$PREFIX" ]; then
    rm -rf "$PREFIX"
    echo "已删除安装目录：$PREFIX"
else
    echo "安装目录不存在，跳过：$PREFIX"
fi

echo "卸载完成。账本文件未受影响。"
