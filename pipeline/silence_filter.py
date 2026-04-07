"""静音过滤模块 — 跳过无有效语音的录音文件，节省转写时间."""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def has_speech(
    audio_file: str | Path,
    min_speech_ratio: float = 0.15,
    vad_aggressiveness: int = 2,
) -> bool:
    """检测音频文件是否包含足够的语音内容.

    Args:
        audio_file: 音频文件路径
        min_speech_ratio: 最低语音占比（低于此值则跳过）
        vad_aggressiveness: VAD 灵敏度（0-3，越高越敏感）

    Returns:
        True 表示有足够语音，False 表示静音为主
    """
    try:
        import webrtcvad
        import wave
        import struct
        from pydub import AudioSegment

        audio_path = Path(audio_file)

        # 转换为 WAV（webrtcvad 需要 PCM）
        audio = AudioSegment.from_file(str(audio_path))
        audio = audio.set_frame_rate(16000).set_channels(1).set_sample_width(2)

        raw_data = audio.raw_data
        frame_duration_ms = 30  # 30ms 帧
        frame_size = int(16000 * frame_duration_ms / 1000) * 2  # 字节数

        vad = webrtcvad.Vad(vad_aggressiveness)
        frames = [raw_data[i:i + frame_size] for i in range(0, len(raw_data) - frame_size, frame_size)]

        speech_frames = sum(
            1 for frame in frames
            if len(frame) == frame_size and vad.is_speech(frame, 16000)
        )

        ratio = speech_frames / len(frames) if frames else 0.0
        has = ratio >= min_speech_ratio

        logger.debug(f"{audio_path.name}: 语音占比 {ratio:.1%} → {'保留' if has else '跳过'}")
        return has

    except ImportError:
        # webrtcvad 未安装，回退到文件大小估算
        size_mb = Path(audio_file).stat().st_size / 1024 / 1024
        # 16kHz 单声道 32k MP3，1小时约 14MB；如果太小说明大部分是静音
        return size_mb > 0.5
    except Exception as e:
        logger.warning(f"静音检测失败（{audio_file}）: {e}，默认保留")
        return True


def filter_recordings(
    recordings: list[Path],
    min_speech_ratio: float = 0.15,
    vad_aggressiveness: int = 2,
) -> tuple[list[Path], list[Path]]:
    """过滤录音列表，返回 (有语音的, 被跳过的).

    Args:
        recordings: 录音文件路径列表
        min_speech_ratio: 最低语音占比
        vad_aggressiveness: VAD 灵敏度

    Returns:
        (active_files, skipped_files)
    """
    active, skipped = [], []
    for f in recordings:
        if has_speech(f, min_speech_ratio, vad_aggressiveness):
            active.append(f)
        else:
            skipped.append(f)

    logger.info(f"静音过滤: {len(active)} 个保留，{len(skipped)} 个跳过")
    return active, skipped
