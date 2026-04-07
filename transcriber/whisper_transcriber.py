"""转写模块 — faster-whisper 转写，对齐声纹分割结果.

核心逻辑：whisper 按时间段转写 → 对齐 diarization 说话人标签 → 输出对话文本。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class TranscriptSegment:
    """转写片段（含说话人标签）.

    Attributes:
        speaker: 说话人名称
        start: 开始时间（秒）
        end: 结束时间（秒）
        text: 转写文本
    """

    speaker: str
    start: float
    end: float
    text: str


@dataclass
class TranscriptResult:
    """转写结果."""

    segments: list[TranscriptSegment] = field(default_factory=list)
    audio_file: str = ""
    language: str = "zh"
    duration: float = 0.0


class WhisperTranscriber:
    """faster-whisper 转写器.

    Args:
        model_size: 模型大小（tiny/base/small/medium/large-v3）
        device: 推理设备（cpu/cuda/mps）
        compute_type: 量化类型（int8/float16/float32）
        language: 语言代码（zh/en/auto）
    """

    def __init__(
        self,
        model_size: str = "large-v3",
        device: str = "cpu",
        compute_type: str = "int8",
        language: str = "zh",
    ) -> None:
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.language = language
        self._model = None  # 懒加载

    def _get_model(self):
        if self._model is None:
            logger.info(f"加载 Whisper 模型: {self.model_size} ({self.device}/{self.compute_type})")
            from faster_whisper import WhisperModel
            self._model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type,
            )
        return self._model

    def _find_speaker(
        self,
        seg_start: float,
        seg_end: float,
        diarization_segments,
    ) -> str:
        """找和 whisper 片段时间重叠最多的说话人.

        Args:
            seg_start: whisper 片段开始时间
            seg_end: whisper 片段结束时间
            diarization_segments: SpeakerSegment 列表

        Returns:
            说话人名称
        """
        if not diarization_segments:
            return "未知"

        best_speaker = "未知"
        best_overlap = 0.0

        for d_seg in diarization_segments:
            # 计算重叠时长
            overlap_start = max(seg_start, d_seg.start)
            overlap_end = min(seg_end, d_seg.end)
            overlap = max(0.0, overlap_end - overlap_start)
            if overlap > best_overlap:
                best_overlap = overlap
                best_speaker = d_seg.speaker_name

        return best_speaker

    def transcribe(
        self,
        audio_file: str | Path,
        diarization_segments=None,
    ) -> TranscriptResult:
        """转写音频文件，可选对齐声纹分割结果.

        Args:
            audio_file: 音频文件路径
            diarization_segments: SpeakerSegment 列表（来自 SpeakerDiarizer）

        Returns:
            TranscriptResult，包含带说话人标签的转写片段列表
        """
        audio_file = Path(audio_file)
        logger.info(f"转写: {audio_file.name}")

        model = self._get_model()
        lang = None if self.language == "auto" else self.language

        segments_iter, info = model.transcribe(
            str(audio_file),
            language=lang,
            word_timestamps=True,
            vad_filter=True,        # 内置 VAD，自动跳过静音段
            vad_parameters={
                "min_silence_duration_ms": 500,
            },
        )

        result_segments: list[TranscriptSegment] = []
        for seg in segments_iter:
            text = seg.text.strip()
            if not text:
                continue

            speaker = (
                self._find_speaker(seg.start, seg.end, diarization_segments)
                if diarization_segments
                else "未知"
            )

            result_segments.append(TranscriptSegment(
                speaker=speaker,
                start=seg.start,
                end=seg.end,
                text=text,
            ))

        logger.info(f"转写完成: {len(result_segments)} 个片段 | 语言: {info.language}")

        return TranscriptResult(
            segments=result_segments,
            audio_file=str(audio_file),
            language=info.language,
            duration=info.duration,
        )
