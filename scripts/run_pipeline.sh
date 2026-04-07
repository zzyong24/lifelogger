#!/usr/bin/env bash
# launchd 调用的包装脚本，确保工作目录和路径正确
PROJ="/Users/zyongzhu/workbase/github/lifelogger"
cd "$PROJ"
exec "$PROJ/.venv/bin/python" "$PROJ/main.py" run
