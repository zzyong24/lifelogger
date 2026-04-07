#!/usr/bin/env bash
# 一键安装 launchd 任务
# - com.lifelogger.recorder: 开机自启录音
# - com.lifelogger.pipeline: 每晚 23:00 转写

set -e
SCRIPTS_DIR="$(cd "$(dirname "$0")" && pwd)"
AGENTS_DIR="$HOME/Library/LaunchAgents"

echo "📦 安装 lifelogger launchd 任务..."

# 录音守护进程
cp "$SCRIPTS_DIR/com.lifelogger.recorder.plist" "$AGENTS_DIR/"
launchctl unload "$AGENTS_DIR/com.lifelogger.recorder.plist" 2>/dev/null || true
launchctl load "$AGENTS_DIR/com.lifelogger.recorder.plist"
echo "✅ 录音守护进程已安装（开机自启）"

# 每晚转写
cp "$SCRIPTS_DIR/com.lifelogger.pipeline.plist" "$AGENTS_DIR/"
launchctl unload "$AGENTS_DIR/com.lifelogger.pipeline.plist" 2>/dev/null || true
launchctl load "$AGENTS_DIR/com.lifelogger.pipeline.plist"
echo "✅ 每晚转写任务已安装（每天 23:00）"

echo ""
echo "查看日志:"
echo "  tail -f /tmp/lifelogger-recorder.log   # 录音日志"
echo "  tail -f /tmp/lifelogger-pipeline.log   # 转写日志"
echo ""
echo "卸载:"
echo "  launchctl unload ~/Library/LaunchAgents/com.lifelogger.recorder.plist"
echo "  launchctl unload ~/Library/LaunchAgents/com.lifelogger.pipeline.plist"
