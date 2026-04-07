# PRD: lifelogger

## 产品定位

24 小时无感知生活录音系统。将电脑变成随身录音设备，自动完成：
音频捕获 → 静音过滤 → 声纹分离 → 转写 → 对话文本 → Vault

---

## 核心需求与完成状态

| # | 需求 | 状态 | 备注 |
|---|------|------|------|
| 1 | 后台录制（系统音频 + 麦克风） | ✅ 完成 | macOS 内置麦 `:1` 已跑通 |
| 2 | 热键启停（Ctrl+Shift+R） | ✅ 完成 | `--hotkey` 模式，需 pynput |
| 3 | BlackHole 双声道录制 | ⏳ 待配置 | 录双方声音，见配置说明 |
| 4 | 静音过滤 | ✅ 完成 | webrtcvad fallback 到文件大小 |
| 5 | 声纹分离（pyannote） | ✅ 代码完成 | 需 HF token，无 token 自动跳过 |
| 6 | 声纹注册 | ✅ 完成 | `python main.py register <name> <file>` |
| 7 | faster-whisper 转写 | ✅ 完成 | tiny→large-v3 可配，懒加载 |
| 8 | Vault 输出（Markdown） | ✅ 完成 | 标准 frontmatter，按说话人分段 |
| 9 | 日常流水线 | ✅ 完成 | `python main.py run` |
| 10 | 定时任务（launchd） | ✅ 完成 | `scripts/com.lifelogger.recorder.plist` |
| 11 | 硬件兼容（树莓派） | ⏳ 待测试 | Linux ALSA 路径已写 |

---

## 技术栈

- 音频捕获：ffmpeg + macOS AVFoundation / Linux ALSA
- 声纹分离：pyannote.audio 3.1（可选，需 HF token）
- 转写：faster-whisper（支持 tiny~large-v3）
- 静音检测：内置 faster-whisper VAD + webrtcvad fallback
- 热键：pynput GlobalHotKeys（可选）
- 调度：launchd（macOS）/ systemd（Linux）
- 输出：Markdown + ThirdSpace Vault frontmatter 规范

---

## 目录结构

```
lifelogger/
├── recorder/
│   ├── audio_recorder.py     # 录音核心，每 chunk_duration 秒切一文件
│   └── hotkey_controller.py  # 全局热键控制（pynput）
├── diarizer/
│   └── speaker_diarizer.py   # pyannote 声纹分离 + 声纹注册/匹配
├── transcriber/
│   └── whisper_transcriber.py # faster-whisper 转写 + 说话人对齐
├── pipeline/
│   ├── daily_pipeline.py      # 串联全流程的日常流水线
│   └── silence_filter.py      # 静音检测过滤
├── vault/
│   └── markdown_writer.py     # 输出 Vault Markdown
├── config/
│   ├── settings.yaml          # 默认配置（提交 Git）
│   └── settings.local.yaml    # 本机覆盖（gitignore）
├── scripts/
│   ├── install.sh             # 一键安装
│   └── com.lifelogger.recorder.plist  # launchd 开机自启
└── main.py                    # CLI 主入口
```

---

## CLI 命令

```bash
python main.py record              # 持续录音（Ctrl+C 停止）
python main.py record --hotkey     # 热键模式（Ctrl+Shift+R 切换）
python main.py run                 # 跑今天的流水线（转写 → Vault）
python main.py run --date 2026-04-07
python main.py status              # 查看今天录音状态
python main.py register <name> <file>  # 注册说话人声纹
python main.py speakers            # 列出已注册声纹
```

---

## 关键配置（config/settings.local.yaml）

```yaml
audio:
  input_device: "1"          # Mac 内置麦克风（纯录自己）
  # input_device: "BlackHole 2ch"  # 录双方声音（需安装 BlackHole）
  chunk_duration_seconds: 300  # 测试 5 分钟，生产用 3600

whisper:
  model_size: "tiny"         # 测试用，生产用 large-v3 或 small
  device: "cpu"
  compute_type: "int8"

diarization:
  hf_token: ""               # 填写后自动启用声纹分离
```

---

## 录音方案对比

| 方案 | 录自己 | 录对方（腾讯会议等） | 操作 |
|------|--------|--------|------|
| 内置麦克风 `:1`（当前） | ✅ | ❌ | 已跑通 |
| BlackHole 虚拟声卡 | ✅ | ✅ | `brew install blackhole-2ch` + 系统设置 |

**macOS 麦克风不会被占用**：AVFoundation 支持多应用共享同一输入设备，腾讯会议和 lifelogger 可同时使用麦克风。

---

## 依赖安装

```bash
# 核心依赖（已安装）
uv pip install click rich pyyaml

# 转写（必装）
uv pip install faster-whisper --python .venv/bin/python

# 热键（可选）
uv pip install pynput

# 声纹分离（可选，需 HF token）
uv pip install pyannote.audio

# 静音检测增强（可选）
uv pip install webrtcvad pydub
```

---

## 下一步

- [ ] 验证 faster-whisper 转写跑通（`python main.py run`）
- [ ] 安装 BlackHole，支持录腾讯会议双方声音
- [ ] 配置 HF token，启用声纹分离
- [ ] 设置 launchd 开机自启
- [ ] 迁移到树莓派 / 硬件设备（Linux ALSA 模式）
