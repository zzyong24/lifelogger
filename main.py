#!/usr/bin/env python3
"""lifelogger CLI 主入口.

用法:
  python main.py record          # 开始后台录音（持续运行）
  python main.py run             # 手动运行今天的流水线
  python main.py run --date 2026-04-07
  python main.py register <name> <audio_file>  # 注册声纹
  python main.py speakers        # 列出已注册声纹
  python main.py status          # 查看今天录音状态
"""

from __future__ import annotations

import datetime
import logging
import sys
from pathlib import Path

import click
from rich.console import Console

console = Console()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)


@click.group()
def cli():
    """lifelogger — 24小时生活录音 + 声纹识别 + 自动转写"""


@cli.command()
@click.option("--hotkey", is_flag=True, default=False,
              help="热键模式：Ctrl+Shift+R 切换启停，Ctrl+Shift+Q 退出")
@click.option("--toggle-key", default="<ctrl>+<shift>+r",
              help="切换录音热键（默认 Ctrl+Shift+R）")
def record(hotkey: bool, toggle_key: str):
    """启动后台持续录音（每小时切割一个文件）.

    普通模式: 立即开始录音，Ctrl+C 停止。
    热键模式: --hotkey，Ctrl+Shift+R 切换启停，Ctrl+Shift+Q 退出。
    """
    from pipeline.daily_pipeline import load_config
    from recorder.audio_recorder import AudioRecorder

    cfg = load_config()
    recorder = AudioRecorder(
        input_device=cfg["audio"]["input_device"],
        recordings_dir=cfg["storage"]["recordings_dir"],
        chunk_duration=cfg["audio"]["chunk_duration_seconds"],
        sample_rate=cfg["audio"]["sample_rate"],
        channels=cfg["audio"]["channels"],
        audio_format=cfg["audio"]["audio_format"],
        bitrate=cfg["audio"]["bitrate"],
    )

    console.print(f"[cyan]录音设备[/cyan]: {cfg['audio']['input_device']}")
    console.print(f"[cyan]存储目录[/cyan]: {recorder.recordings_dir}")
    console.print(f"[cyan]切割间隔[/cyan]: {cfg['audio']['chunk_duration_seconds'] // 60} 分钟")

    if hotkey:
        import threading
        from recorder.hotkey_controller import HotkeyController

        record_thread: threading.Thread | None = None
        stop_event = threading.Event()

        def _start():
            nonlocal record_thread, stop_event
            stop_event.clear()
            record_thread = threading.Thread(
                target=recorder.run_forever,
                kwargs={"stop_event": stop_event},
                daemon=True,
                name="recorder",
            )
            record_thread.start()

        def _stop():
            nonlocal stop_event
            stop_event.set()

        controller = HotkeyController(
            on_start=_start,
            on_stop=_stop,
            toggle_combo=toggle_key,
        )
        console.print(f"\n[bold yellow]热键模式[/bold yellow]")
        console.print(f"  [cyan]{toggle_key}[/cyan]       切换录音启停")
        console.print(f"  [cyan]Ctrl+Shift+Q[/cyan]  退出\n")
        console.print("[dim]macOS 需要在「系统设置 → 隐私与安全 → 辅助功能」中允许终端[/dim]\n")
        controller.start()  # 阻塞，等热键事件
    else:
        console.print("\n[bold green]开始录音[/bold green]（Ctrl+C 停止）\n")
        recorder.run_forever()


@cli.command()
@click.option("--poll", default=10, help="轮询间隔秒数（默认 10）")
def watch(poll: int):
    """监听录音目录，新文件完成后自动转写写入 Vault（配合 record 同时运行）."""
    from pipeline.daily_pipeline import load_config
    from pipeline.watch_pipeline import watch_and_transcribe

    cfg = load_config()
    console.print(f"[bold cyan]🔍 Watch 模式启动[/bold cyan]")
    console.print(f"  监听目录: [dim]{cfg['storage']['recordings_dir']}[/dim]")
    console.print(f"  Vault 输出: [dim]{cfg['vault']['output_dir']}[/dim]")
    console.print(f"  轮询间隔: {poll}s\n")
    console.print("[dim]新录音完成后自动转写并追加到 Vault（Ctrl+C 停止）[/dim]\n")
    watch_and_transcribe(cfg["storage"]["recordings_dir"], cfg, poll_interval=poll)


@click.option("--dry-run", is_flag=True, help="试运行，不写入 Vault")
@click.option("--config", "-c", default=None, help="配置文件路径")
def run(date: str | None, dry_run: bool, config: str | None):
    """运行日常流水线（声纹分离 + 转写 + 写入 Vault）."""
    from pipeline.daily_pipeline import run_pipeline

    target_date = datetime.date.fromisoformat(date) if date else datetime.date.today()
    stats = run_pipeline(date=target_date, config_path=config, dry_run=dry_run)

    console.print("\n[bold]统计[/bold]")
    for k, v in stats.items():
        console.print(f"  {k}: [cyan]{v}[/cyan]")


@cli.command()
@click.argument("name")
@click.argument("audio_file", type=click.Path(exists=True))
@click.option("--overwrite", is_flag=True, help="覆盖已有声纹")
def register(name: str, audio_file: str, overwrite: bool):
    """注册说话人声纹.

    NAME: 说话人名称（如 zyongzhu）
    AUDIO_FILE: 包含该说话人声音的音频文件（建议 30 秒以上纯人声）
    """
    from pipeline.daily_pipeline import load_config
    from diarizer.speaker_diarizer import SpeakerDiarizer
    import os

    cfg = load_config()
    hf_token = cfg["diarization"].get("hf_token", "") or os.environ.get("HF_TOKEN", "")

    if not hf_token:
        console.print("[red]错误: 未配置 HuggingFace token[/red]")
        console.print("在 config/settings.local.yaml 中设置 diarization.hf_token")
        console.print("或设置环境变量 HF_TOKEN")
        sys.exit(1)

    diarizer = SpeakerDiarizer(
        hf_token=hf_token,
        speakers_dir=cfg["storage"]["speakers_dir"],
    )

    console.print(f"注册声纹: [cyan]{name}[/cyan] ← [green]{audio_file}[/green]")
    diarizer.register_speaker(name, audio_file, overwrite=overwrite)
    console.print(f"[bold green]✅ 声纹注册完成: {name}[/bold green]")


@cli.command()
def speakers():
    """列出已注册的说话人声纹."""
    from pipeline.daily_pipeline import load_config
    from diarizer.speaker_diarizer import SpeakerDiarizer
    import os

    cfg = load_config()
    hf_token = cfg["diarization"].get("hf_token", "") or os.environ.get("HF_TOKEN", "")

    diarizer = SpeakerDiarizer(
        hf_token=hf_token or "placeholder",
        speakers_dir=cfg["storage"]["speakers_dir"],
    )
    names = diarizer.list_speakers()

    if not names:
        console.print("[yellow]还没有注册任何声纹[/yellow]")
        console.print("使用 [cyan]python main.py register <name> <audio_file>[/cyan] 注册")
    else:
        console.print(f"\n[bold]已注册声纹 ({len(names)} 个)[/bold]")
        for n in names:
            console.print(f"  • [cyan]{n}[/cyan]")


@cli.command()
@click.option("--date", "-d", default=None, help="查看日期 YYYY-MM-DD（默认今天）")
def status(date: str | None):
    """查看录音状态（文件数、总大小）."""
    from pipeline.daily_pipeline import load_config
    from recorder.audio_recorder import AudioRecorder

    cfg = load_config()
    recorder = AudioRecorder(
        recordings_dir=cfg["storage"]["recordings_dir"],
        audio_format=cfg["audio"]["audio_format"],
    )

    target_date = datetime.date.fromisoformat(date) if date else datetime.date.today()
    files = recorder.list_recordings(target_date)

    total_size = sum(f.stat().st_size for f in files) / 1024 / 1024

    console.print(f"\n[bold]{target_date} 录音状态[/bold]")
    console.print(f"  文件数: [cyan]{len(files)}[/cyan]")
    console.print(f"  总大小: [cyan]{total_size:.1f} MB[/cyan]")
    console.print(f"  存储目录: [dim]{recorder.recordings_dir}[/dim]")

    if files:
        console.print("\n  文件列表:")
        for f in files:
            size_kb = f.stat().st_size / 1024
            console.print(f"    [dim]{f.name}[/dim] ({size_kb:.0f} KB)")


if __name__ == "__main__":
    cli()
