# lifelogger

> 24小时无感知生活录音 · 声纹识别 · 自动转写 → Vault

将电脑变成随身录音设备。后台持续捕获系统音频和麦克风，每天自动转写并按说话人区分，输出对话文本到 Vault。

---

## 架构

```
BlackHole（捕获系统音频 + 麦克风混合）
         ↓
    AudioRecorder（每小时切割一个 MP3）
         ↓
    SilenceFilter（跳过无语音文件）
         ↓
    SpeakerDiarizer（pyannote 声纹分离 + 声纹库匹配）
         ↓
    WhisperTranscriber（faster-whisper 转写）
         ↓
    VaultWriter（生成 Markdown → vault/lifelogs/）
```

---

## 快速开始

### 1. 安装

```bash
git clone https://github.com/zzyong24/lifelogger
cd lifelogger
bash scripts/install.sh
```

### 2. 配置

```bash
# 编辑本地配置（不进 git）
cp config/settings.yaml config/settings.local.yaml
```

必填项：
- `diarization.hf_token`：HuggingFace token
  - 申请：https://huggingface.co/settings/tokens
  - 需同意协议：https://huggingface.co/pyannote/speaker-diarization-3.1

- `vault.output_dir`：你的 Vault 路径（如 `~/vault/space/crafted/work/lifelogs`）

### 3. 注册声纹

```bash
# 录一段 30 秒以上的纯人声，注册为已知说话人
python main.py register zyongzhu /path/to/your_voice.mp3
python main.py register 张三 /path/to/zhangsan.mp3
```

### 4. 开始录音

```bash
# 手动启动（前台）
python main.py record

# 开机自启（后台，安装 launchd）
# install.sh 中选择 y 即可
```

### 5. 手动跑流水线

```bash
# 处理今天的录音
python main.py run

# 处理指定日期
python main.py run --date 2026-04-07

# 试运行（不写 Vault）
python main.py run --dry-run
```

---

## CLI 命令

| 命令 | 说明 |
|------|------|
| `python main.py record` | 启动后台录音 |
| `python main.py run` | 运行今天的流水线 |
| `python main.py run --date YYYY-MM-DD` | 处理指定日期 |
| `python main.py register <name> <file>` | 注册说话人声纹 |
| `python main.py speakers` | 列出已注册声纹 |
| `python main.py status` | 查看今天录音状态 |

---

## 输出示例

```markdown
# 2026-04-07 生活录音

**zyongzhu** `09:12`
我们来看一下这个接口的设计

**张三** `09:12`
这里的 workspace_id 需要校验吗

**zyongzhu** `09:13`
需要，用 secret_key 做签名验证
```

---

## macOS 音频配置

1. 安装 BlackHole：`brew install blackhole-2ch`
2. 系统偏好设置 → 声音 → 点击左下角 `+` → 创建「多输出设备」
3. 勾选：内置扬声器 + BlackHole 2ch
4. 将「多输出设备」设为系统默认输出
5. `config/settings.local.yaml` 中 `audio.input_device: "BlackHole 2ch"`

---

## 硬件部署（树莓派 / 专用设备）

修改 `config/settings.local.yaml`：

```yaml
audio:
  input_device: "default"   # 或 "hw:1,0"（ALSA 设备）

whisper:
  model_size: "small"       # 资源受限时用 small 或 base
  device: "cpu"
  compute_type: "int8"
```

Linux 定时任务：

```bash
# crontab -e
30 23 * * * cd /path/to/lifelogger && .venv/bin/python main.py run >> /tmp/lifelogger-pipeline.log 2>&1
```

---

## 目录结构

```
lifelogger/
├── main.py               # CLI 主入口
├── requirements.txt
├── config/
│   ├── settings.yaml     # 默认配置
│   └── settings.local.yaml  # 本地配置（不进 git）
├── recorder/             # 音频捕获
├── diarizer/             # 声纹分离 + 识别
├── transcriber/          # Whisper 转写
├── vault/                # Vault 输出
├── pipeline/             # 流水线 + 静音过滤
└── scripts/
    ├── install.sh
    └── com.lifelogger.recorder.plist  # launchd 配置
```

---

## License

MIT
