"""日常流水线 — 每天定时运行，处理当天所有录音.

流程：
1. 找到今天所有录音文件
2. 静音过滤（跳过无语音文件）
3. 声纹分离
4. 转写
5. 写入 Vault
6. 清理过期录音
"""

from __future__ import annotations

import datetime
import logging
from pathlib import Path

import yaml
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

logger = logging.getLogger(__name__)
console = Console()


def load_config(config_path: str | Path | None = None) -> dict:
    """加载配置文件（settings.yaml + settings.local.yaml 合并）."""
    project_root = Path(__file__).parent.parent
    base = project_root / "config" / "settings.yaml"
    local = project_root / "config" / "settings.local.yaml"

    if config_path:
        base = Path(config_path)

    with open(base, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    if local.exists():
        with open(local, encoding="utf-8") as f:
            local_cfg = yaml.safe_load(f) or {}
        # 深度合并
        _deep_merge(cfg, local_cfg)

    return cfg


def _deep_merge(base: dict, override: dict) -> None:
    for k, v in override.items():
        if k in base and isinstance(base[k], dict) and isinstance(v, dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v


def run_pipeline(
    date: datetime.date | None = None,
    config_path: str | Path | None = None,
    dry_run: bool = False,
) -> dict:
    """运行日常流水线.

    Args:
        date: 处理日期（默认今天）
        config_path: 配置文件路径
        dry_run: 试运行，不实际写入 Vault

    Returns:
        运行统计字典
    """
    date = date or datetime.date.today()
    cfg = load_config(config_path)

    console.print(f"\n[bold cyan]🎙 lifelogger 日常流水线[/bold cyan]")
    console.print(f"处理日期: [green]{date}[/green]")

    # ── 初始化各模块 ──────────────────────────────────────────────────

    from recorder.audio_recorder import AudioRecorder
    from pipeline.silence_filter import filter_recordings
    from diarizer.speaker_diarizer import SpeakerDiarizer
    from transcriber.whisper_transcriber import WhisperTranscriber
    from vault.markdown_writer import VaultWriter

    recorder = AudioRecorder(
        recordings_dir=cfg["storage"]["recordings_dir"],
        audio_format=cfg["audio"]["audio_format"],
    )

    hf_token = cfg["diarization"].get("hf_token", "")
    import os
    hf_token = hf_token or os.environ.get("HF_TOKEN", "")

    diarizer = SpeakerDiarizer(
        hf_token=hf_token,
        speakers_dir=cfg["storage"]["speakers_dir"],
        match_threshold=cfg["diarization"]["speaker_match_threshold"],
        min_speakers=cfg["diarization"]["min_speakers"],
        max_speakers=cfg["diarization"]["max_speakers"],
    ) if hf_token else None

    transcriber = WhisperTranscriber(
        model_size=cfg["whisper"]["model_size"],
        device=cfg["whisper"]["device"],
        compute_type=cfg["whisper"]["compute_type"],
        language=cfg["whisper"]["language"],
    )

    writer = VaultWriter(
        output_dir=cfg["vault"]["output_dir"],
        filename_format=cfg["vault"]["filename_format"],
    ) if cfg["vault"]["enabled"] else None

    # ── 步骤 1：找今天的录音 ───────────────────────────────────────────

    recordings = recorder.list_recordings(date)
    console.print(f"\n[bold]步骤 1[/bold] 找到 [cyan]{len(recordings)}[/cyan] 个录音文件")

    if not recordings:
        console.print("[yellow]今天没有录音文件，流水线结束[/yellow]")
        return {"date": str(date), "recordings": 0, "processed": 0}

    # ── 步骤 2：静音过滤 ───────────────────────────────────────────────

    active_files, skipped_files = filter_recordings(
        recordings,
        min_speech_ratio=1.0 - cfg["silence"]["skip_if_silence_ratio"],
        vad_aggressiveness=cfg["silence"]["vad_aggressiveness"],
    )
    console.print(
        f"[bold]步骤 2[/bold] 静音过滤: "
        f"[green]{len(active_files)} 个保留[/green]，"
        f"[dim]{len(skipped_files)} 个跳过[/dim]"
    )

    if not active_files:
        console.print("[yellow]所有文件均为静音，流水线结束[/yellow]")
        return {"date": str(date), "recordings": len(recordings), "processed": 0}

    # ── 步骤 3+4：声纹分离 + 转写 ─────────────────────────────────────

    from transcriber.whisper_transcriber import TranscriptResult
    all_results: list[TranscriptResult] = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("处理录音...", total=len(active_files))

        for audio_file in active_files:
            progress.update(task, description=f"处理: [cyan]{audio_file.name}[/cyan]")

            # 声纹分离
            diarization_segs = None
            if diarizer:
                try:
                    diarization_result = diarizer.diarize(audio_file)
                    diarization_segs = diarization_result.segments
                except Exception as e:
                    logger.warning(f"声纹分离失败（{audio_file.name}）: {e}，继续转写")

            # 转写
            try:
                result = transcriber.transcribe(audio_file, diarization_segs)
                all_results.append(result)
            except Exception as e:
                logger.error(f"转写失败（{audio_file.name}）: {e}")

            progress.advance(task)

    total_segments = sum(len(r.segments) for r in all_results)
    console.print(f"[bold]步骤 3+4[/bold] 转写完成: [cyan]{total_segments}[/cyan] 个片段")

    # ── 步骤 5：写入 Vault ─────────────────────────────────────────────

    output_path = None
    if writer and not dry_run and all_results:
        output_path = writer.write(all_results, date)
        console.print(f"[bold]步骤 5[/bold] 已写入 Vault: [green]{output_path}[/green]")
    elif dry_run:
        console.print("[bold]步骤 5[/bold] [yellow]DRY RUN — 跳过写入[/yellow]")

    # ── 步骤 6：清理过期录音 ───────────────────────────────────────────

    deleted = recorder.cleanup_old_recordings(cfg["storage"]["retention_days"])
    if deleted:
        console.print(f"[bold]步骤 6[/bold] 清理了 [dim]{deleted}[/dim] 个过期录音")

    console.print("\n[bold green]✅ 流水线完成[/bold green]")

    return {
        "date": str(date),
        "recordings": len(recordings),
        "active": len(active_files),
        "skipped": len(skipped_files),
        "segments": total_segments,
        "output": str(output_path) if output_path else None,
        "deleted": deleted,
    }
