# lifelogger — Claude Code 工作指南

## 项目定位

24小时生活录音系统：音频捕获 → 静音过滤 → 声纹分离 → faster-whisper 转写 → Vault Markdown

## 开发环境

```bash
# 激活 venv
source .venv/bin/activate
# 或直接用
.venv/bin/python main.py <command>
```

## CLI 命令速查

| 场景 | 命令 |
|------|------|
| 启动录音（持续） | `python main.py record` |
| 热键模式 | `python main.py record --hotkey` |
| 查看今日录音 | `python main.py status` |
| 运行转写流水线 | `python main.py run` |
| 转写指定日期 | `python main.py run --date 2026-04-07` |
| 试运行（不写Vault） | `python main.py run --dry-run` |
| 注册声纹 | `python main.py register zyongzhu voice.mp3` |
| 查看声纹列表 | `python main.py speakers` |

## 核心模块

| 模块 | 文件 | 说明 |
|------|------|------|
| 录音 | `recorder/audio_recorder.py` | ffmpeg avfoundation/alsa |
| 热键 | `recorder/hotkey_controller.py` | pynput GlobalHotKeys |
| 声纹 | `diarizer/speaker_diarizer.py` | pyannote 3.1 |
| 转写 | `transcriber/whisper_transcriber.py` | faster-whisper |
| 静音 | `pipeline/silence_filter.py` | webrtcvad fallback 文件大小 |
| 流水线 | `pipeline/daily_pipeline.py` | 串联全流程 |
| 输出 | `vault/markdown_writer.py` | Vault Markdown + frontmatter |

## 配置说明

- `config/settings.yaml` — 默认配置（提交 Git）
- `config/settings.local.yaml` — 本机覆盖（gitignore，私有配置放这里）

关键配置项：
```yaml
audio.input_device: "1"              # Mac 内置麦；"BlackHole 2ch" 录双方
audio.chunk_duration_seconds: 300    # 5分钟/段（测试），生产用 3600
whisper.model_size: "tiny"           # 测试；生产用 small 或 large-v3
diarization.hf_token: "hf_xxx"      # 填后自动启用声纹分离
```

## 数据流

```
ffmpeg (avfoundation :1)
    ↓ MP3 文件（每 chunk_duration 秒）
~/Library/Application Support/lifelogger/recordings/YYYYMMDD_HHMMSS.mp3
    ↓ python main.py run
silence_filter → 跳过静音文件
    ↓
SpeakerDiarizer（pyannote，可选）→ 说话人时间段
    ↓
WhisperTranscriber（faster-whisper）→ 文字 + 说话人对齐
    ↓
VaultWriter → ~/vault/space/crafted/work/lifelogs/YYYY-MM-DD_lifelogs.md
```

## 常见问题

**Q: 麦克风被占用？**  
A: 不会，AVFoundation 支持多应用共享同一麦克风。

**Q: 录不到腾讯会议对方声音？**  
A: 需要安装 BlackHole：`bash scripts/setup_blackhole.sh`

**Q: 热键不响应？**  
A: 系统设置 → 隐私与安全 → 辅助功能 → 允许终端/IDE

**Q: 转写很慢？**  
A: 改用 `model_size: "tiny"`（75MB，速度快 10x，准确率略低）

## 开发规范

- 所有模块懒加载（首次使用才导入模型），启动零延迟
- 每个录音文件独立处理，单文件异常不影响整体流水线
- 私有数据（录音/声纹/token）全部 gitignore
- config/settings.local.yaml 覆盖默认配置，不提交 Git
