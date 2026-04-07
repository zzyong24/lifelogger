#!/usr/bin/env python3
"""一键验证 lifelogger 各模块是否就绪."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from rich.console import Console
from rich.table import Table

console = Console()


def check(name: str, fn) -> tuple[bool, str]:
    try:
        msg = fn()
        return True, msg or "OK"
    except Exception as e:
        return False, str(e)


checks = [
    ("ffmpeg", lambda: __import__("subprocess").check_output(
        ["ffmpeg", "-version"], capture_output=True).returncode == 0 or "ok"),

    ("click", lambda: __import__("click").__version__),
    ("rich", lambda: __import__("rich").__version__),
    ("pyyaml", lambda: __import__("yaml").__version__),

    ("faster-whisper", lambda: __import__("faster_whisper").__version__),

    ("pynput (热键，可选)", lambda: __import__("pynput").__version__),

    ("webrtcvad (静音检测，可选)", lambda: __import__("webrtcvad") or "ok"),

    ("pyannote (声纹分离，可选)", lambda: __import__("pyannote.audio") or "ok"),

    ("录音目录", lambda: (
        Path("~/Library/Application Support/lifelogger/recordings")
        .expanduser().mkdir(parents=True, exist_ok=True) or "可写"
    )),

    ("配置文件", lambda: (
        Path("config/settings.yaml").exists() and "settings.yaml 存在"
    )),

    ("本地配置", lambda: (
        "settings.local.yaml 存在" if Path("config/settings.local.yaml").exists()
        else "⚠️ 未创建（复制 settings.yaml 为 settings.local.yaml 后修改）"
    )),

    ("Vault 输出目录", lambda: (
        __import__("yaml").safe_load(
            Path("config/settings.local.yaml").read_text()
            if Path("config/settings.local.yaml").exists()
            else Path("config/settings.yaml").read_text()
        ).get("vault", {}).get("output_dir", "未配置")
    )),
]

table = Table(title="lifelogger 环境检查", show_header=True)
table.add_column("组件", style="cyan")
table.add_column("状态")
table.add_column("详情", style="dim")

all_ok = True
critical_fail = False

for name, fn in checks:
    ok, msg = check(name, fn)
    is_optional = "可选" in name
    if not ok and not is_optional:
        all_ok = False
        critical_fail = True
    status = "✅" if ok else ("⚠️" if is_optional else "❌")
    table.add_row(name, status, msg[:60])

console.print(table)

if critical_fail:
    console.print("\n[red bold]❌ 有必要依赖未就绪，请先安装后再运行[/red bold]")
    console.print("\n[yellow]安装命令:[/yellow]")
    console.print("  uv pip install faster-whisper --python .venv/bin/python")
    console.print("  uv pip install pynput  # 热键（可选）")
    sys.exit(1)
else:
    console.print("\n[green bold]✅ 环境就绪，可以运行:[/green bold]")
    console.print("  .venv/bin/python main.py record        # 开始录音")
    console.print("  .venv/bin/python main.py record --hotkey  # 热键模式")
    console.print("  .venv/bin/python main.py run           # 转写今天录音")
