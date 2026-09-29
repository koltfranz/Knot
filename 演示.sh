#!/bin/sh
# 一键体验示例账本：复制（已存在则跳过）并直接进入终端界面。
# 鼠标：单击选择 · Ctrl+单击多选 · 滚轮滚动 · 空格标记 · b 批量菜单 · q 退出
exec "$(dirname "$0")/knot.sh" demo --open
