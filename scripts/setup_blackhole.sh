#!/usr/bin/env bash
# BlackHole 安装 + 多输出设备配置脚本
# 执行后重启录音即可录到腾讯会议双方声音
set -e

echo "🎙 BlackHole 安装向导"
echo "----------------------"

# 1. 安装 BlackHole
if system_profiler SPAudioDataType 2>/dev/null | grep -q "BlackHole"; then
    echo "✅ BlackHole 已安装，跳过"
else
    echo "📦 安装 BlackHole 2ch..."
    brew install blackhole-2ch
    echo "✅ BlackHole 安装完成"
fi

# 2. 提示用户手动配置多输出设备
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📋 接下来需要手动操作（30秒）："
echo ""
echo "  1. 打开「音频 MIDI 设置」（或运行下方命令）"
echo "  2. 点击左下角「+」→「创建多输出设备」"
echo "  3. 勾选：MacBook Air扬声器 + BlackHole 2ch"
echo "  4. 右键该设备 → 「用于声音输出」"
echo ""
echo "  这样：声音照常从扬声器播出，同时 BlackHole 录一份"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 打开音频 MIDI 设置
open -a "Audio MIDI Setup"

echo ""
echo "设置完成后，修改 config/settings.local.yaml："
echo ""
echo "  audio:"
echo "    input_device: \"BlackHole 2ch\"  # 改这一行"
echo ""

# 3. 列出当前音频设备，确认 BlackHole 可见
echo "当前可用音频输入设备："
ffmpeg -f avfoundation -list_devices true -i "" 2>&1 | grep -E "audio|AVFoundation" || true
