# PRD: lifelogger

## 产品定位

24 小时无感知生活录音系统。将电脑变成随身录音设备，自动完成：
音频捕获 → 静音过滤 → 声纹分离 → 转写 → 对话文本 → Vault

## 核心需求

1. **后台录制**：捕获系统音频 + 麦克风，每小时切割一个文件
2. **声纹分离**：自动区分多个说话人（pyannote.audio）
3. **声纹注册**：支持注册已知说话人，自动识别「你是谁」
4. **转写**：faster-whisper 中文优先，输出带说话人标签的对话文本
5. **Vault 输出**：生成标准 Markdown，写入 vault/daily-notes/
6. **定时流水线**：每天凌晨自动跑，清理 7 天前原始录音
7. **硬件兼容**：支持树莓派 / 专用硬件设备（将来）

## 技术栈

- 音频捕获：ffmpeg + BlackHole（macOS）/ ALSA（Linux）
- 声纹分离：pyannote.audio 3.1
- 转写：faster-whisper（large-v3）
- 静音检测：pydub / webrtcvad
- 调度：launchd（macOS）/ systemd（Linux）
- 输出：Markdown → Vault

## 目录结构

```
lifelogger/
├── recorder/         # 音频捕获模块
├── diarizer/         # 声纹分离模块
├── transcriber/      # 转写模块
├── pipeline/         # 日常流水线
├── vault/            # Vault 输出模块
├── speakers/         # 声纹特征存储
├── config/           # 配置文件
├── scripts/          # 部署脚本（launchd plist 等）
└── tests/
```
