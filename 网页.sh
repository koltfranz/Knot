#!/usr/bin/env sh
# 结绳 Knot · 一键打开浏览器界面（本地服务 + 自动打开浏览器）
exec "$(dirname "$0")/knot.sh" serve --open
