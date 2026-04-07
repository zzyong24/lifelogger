#!/bin/bash
# lifelogger 一键安装脚本（macOS）
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "🎙 lifelogger 安装脚本"
echo "项目目录: $PROJECT_DIR"
echo ""

# ── 检查依赖 ──────────────────────────────────────────────────────────

echo "📦 检查系统依赖..."

# Python
if ! command -v python3 &>/dev/null; then
    echo "❌ 需要 Python 3.10+"
    echo "安装: brew install python@3.12"
    exit 1
fi
PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "✅ Python $PYTHON_VERSION"

# ffmpeg
if ! command -v ffmpeg &>/dev/null; then
    echo "⚠️  ffmpeg 未安装，正在安装..."
    brew install ffmpeg
fi
echo "✅ ffmpeg"

# BlackHole（macOS 虚拟声卡）
if ! system_profiler SPAudioDataType 2>/dev/null | grep -q "BlackHole"; then
    echo ""
    echo "⚠️  BlackHole 虚拟声卡未安装"
    echo "安装命令: brew install blackhole-2ch"
    echo ""
    echo "安装后还需配置："
    echo "  1. 系统偏好设置 → 声音 → 音频设备"
    echo "  2. 点击左下角 + → 创建「多输出设备」"
    echo "  3. 勾选: 内置扬声器 + BlackHole 2ch"
    echo "  4. 将「多输出设备」设为系统输出"
    echo ""
    read -p "是否现在安装 BlackHole? [y/N] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        brew install blackhole-2ch
        echo "✅ BlackHole 安装完成，请按上述步骤配置声音设置"
    fi
fi

# ── 创建虚拟环境 ──────────────────────────────────────────────────────

echo ""
echo "🐍 创建 Python 虚拟环境..."
cd "$PROJECT_DIR"
python3 -m venv .venv
source .venv/bin/activate

echo "📦 安装 Python 依赖..."
pip install -q --upgrade pip
pip install -q -r requirements.txt

# ── 初始化目录 ────────────────────────────────────────────────────────

echo ""
echo "📁 初始化目录..."
mkdir -p "$HOME/Library/Application Support/lifelogger/recordings"
mkdir -p "$HOME/.lifelogger/speakers"
mkdir -p "$PROJECT_DIR/config"

# 复制配置文件（如果不存在）
if [ ! -f "$PROJECT_DIR/config/settings.local.yaml" ]; then
    cp "$PROJECT_DIR/config/settings.yaml" "$PROJECT_DIR/config/settings.local.yaml"
    echo "✅ 已创建 config/settings.local.yaml，请编辑填入 HF_TOKEN"
fi

# ── 安装 launchd（可选）──────────────────────────────────────────────

echo ""
read -p "是否安装开机自启（launchd）? [y/N] " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    PLIST_SRC="$SCRIPT_DIR/com.lifelogger.recorder.plist"
    PLIST_DST="$HOME/Library/LaunchAgents/com.lifelogger.recorder.plist"

    # 替换路径占位符
    sed "s|/PATH/TO/lifelogger|$PROJECT_DIR|g" "$PLIST_SRC" > "$PLIST_DST"

    launchctl load "$PLIST_DST"
    echo "✅ launchd 已安装，开机自动录音"
    echo "查看录音日志: tail -f /tmp/lifelogger.out.log"
fi

# ── 完成 ─────────────────────────────────────────────────────────────

echo ""
echo "✅ 安装完成！"
echo ""
echo "下一步："
echo "  1. 编辑 config/settings.local.yaml，填写 HuggingFace token"
echo "     申请地址: https://huggingface.co/settings/tokens"
echo "     需要同意 pyannote 模型协议: https://huggingface.co/pyannote/speaker-diarization-3.1"
echo ""
echo "  2. 注册你的声纹（需要 30 秒以上的纯人声音频）:"
echo "     python main.py register zyongzhu /path/to/your_voice.mp3"
echo ""
echo "  3. 开始录音:"
echo "     python main.py record"
echo ""
echo "  4. 手动跑流水线（转写今天的录音）:"
echo "     python main.py run"
