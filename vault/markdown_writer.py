"""Vault 输出模块 — 将转写结果转换为 Markdown 并写入 Vault.

输出格式：
- 按说话人分段，连续同一说话人的合并
- 时间戳标注
- 标准 frontmatter（兼容 ThirdSpace Vault 规范）
"""

from __future__ import annotations

import datetime
import logging
from pathlib import Path

from transcriber.whisper_transcriber import TranscriptResult, TranscriptSegment

logger = logging.getLogger(__name__)


def _format_time(seconds: float) -> str:
    """将秒数格式化为 HH:MM:SS."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def segments_to_markdown(
    results: list[TranscriptResult],
    date: datetime.date,
    title: str = "生活录音",
) -> str:
    """将转写结果列表转换为 Markdown 文本.

    Args:
        results: 多个音频文件的转写结果（按时间顺序）
        date: 日期
        title: 标题

    Returns:
        完整的 Markdown 文本（含 frontmatter）
    """
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    date_str = date.strftime("%Y-%m-%d")

    # 收集所有说话人
    all_speakers: set[str] = set()
    for result in results:
        for seg in result.segments:
            all_speakers.add(seg.speaker)

    speakers_list = ", ".join(f'"{s}"' for s in sorted(all_speakers))
    # frontmatter（ThirdSpace Vault 规范）
    frontmatter_lines = [
        "---",
        'type: "note"',
        'topic: "work"',
        f'created: "{now}"',
        f'modified: "{now}"',
        'tags: ["lifelog", "work", "crafted"]',
        'origin: "crafted"',
        'source: "lifelogger"',
        'status: "active"',
        f'date: "{date_str}"',
        f'speakers: [{speakers_list}]',
        "---",
        "",
    ]

    # 正文
    body_lines = [
        f"# {date_str} {title}",
        "",
        f"> 生成时间：{now}  ",
        f"> 说话人：{', '.join(sorted(all_speakers))}",
        "",
        "---",
        "",
    ]

    # 合并所有转写片段并按时间排序
    all_segments: list[TranscriptSegment] = []
    for result in results:
        all_segments.extend(result.segments)
    all_segments.sort(key=lambda s: s.start)

    if not all_segments:
        body_lines.append("*（今日无有效录音）*")
    else:
        current_speaker: str | None = None
        current_block: list[str] = []
        current_start: float = 0.0

        def flush_block():
            if current_block and current_speaker:
                time_str = _format_time(current_start)
                body_lines.append(f"**{current_speaker}** `{time_str}`")
                body_lines.append(" ".join(current_block))
                body_lines.append("")

        for seg in all_segments:
            if seg.speaker != current_speaker:
                flush_block()
                current_speaker = seg.speaker
                current_block = [seg.text]
                current_start = seg.start
            else:
                current_block.append(seg.text)

        flush_block()  # 写入最后一个块

    return "\n".join(frontmatter_lines + body_lines)


class VaultWriter:
    """将转写结果写入 Vault.

    Args:
        output_dir: Vault 输出目录
        filename_format: 文件名格式，支持 {date} 占位符
    """

    def __init__(
        self,
        output_dir: str = "~/vault/space/crafted/work/lifelogs",
        filename_format: str = "{date}_lifelogs.md",
    ) -> None:
        self.output_dir = Path(output_dir).expanduser()
        self.filename_format = filename_format
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def write(
        self,
        results: list[TranscriptResult],
        date: datetime.date | None = None,
        title: str = "生活录音",
    ) -> Path:
        """将转写结果写入 Vault Markdown 文件.

        Args:
            results: 转写结果列表
            date: 日期（默认今天）
            title: 文档标题

        Returns:
            写入的文件路径
        """
        date = date or datetime.date.today()
        filename = self.filename_format.format(date=date.strftime("%Y-%m-%d"))
        output_path = self.output_dir / filename

        content = segments_to_markdown(results, date, title)
        output_path.write_text(content, encoding="utf-8")

        total_segs = sum(len(r.segments) for r in results)
        logger.info(f"已写入 Vault: {output_path} ({total_segs} 个片段)")
        return output_path
