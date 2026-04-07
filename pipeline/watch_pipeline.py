"""Watch 模式 — 监听录音目录，新文件完成后自动转写写入 Vault.

策略：
- 轮询录音目录，检测「文件停止增大超过 N 秒」判定为录制完成
- 对每个新完成的文件立即触发转写
- 转写结果追加写入当天 Vault 文件（而不是覆盖）
"""

from __future__ import annotations

import datetime
import logging
import time
from pathlib import Path

logger = logging.getLogger(__name__)


def _is_stable(path: Path, stable_seconds: int = 8) -> bool:
    """判断文件是否稳定（停止增大超过 stable_seconds 秒）."""
    try:
        size1 = path.stat().st_size
        time.sleep(stable_seconds)
        size2 = path.stat().st_size
        return size1 == size2 and size1 > 0
    except Exception:
        return False


def watch_and_transcribe(
    recordings_dir: str | Path,
    cfg: dict,
    poll_interval: int = 10,
) -> None:
    """持续监听录音目录，新文件完成后立即转写写入 Vault（阻塞）.

    Args:
        recordings_dir: 录音目录
        cfg: 完整配置字典
        poll_interval: 轮询间隔（秒）
    """
    from pipeline.silence_filter import has_speech
    from transcriber.whisper_transcriber import WhisperTranscriber
    from vault.markdown_writer import VaultWriter, append_segments

    recordings_dir = Path(recordings_dir).expanduser()
    audio_format = cfg["audio"]["audio_format"]

    transcriber = WhisperTranscriber(
        model_size=cfg["whisper"]["model_size"],
        device=cfg["whisper"]["device"],
        compute_type=cfg["whisper"]["compute_type"],
        language=cfg["whisper"]["language"],
    )

    writer = VaultWriter(
        output_dir=cfg["vault"]["output_dir"],
        filename_format=cfg["vault"]["filename_format"],
    )

    processed: set[str] = set()
    logger.info(f"Watch 模式启动 | 监听: {recordings_dir} | 轮询: {poll_interval}s")

    while True:
        try:
            today = datetime.date.today()
            pattern = f"{today.strftime('%Y%m%d')}*.{audio_format}"

            for audio_file in sorted(recordings_dir.glob(pattern)):
                if audio_file.name in processed:
                    continue

                # 跳过当前正在录制的文件（最新的那个）
                all_today = sorted(recordings_dir.glob(pattern))
                if audio_file == all_today[-1]:
                    continue  # 最新文件可能还在录

                # 等文件稳定（停止写入）
                if not _is_stable(audio_file, stable_seconds=6):
                    continue

                processed.add(audio_file.name)

                # 静音检测
                if not has_speech(audio_file):
                    logger.info(f"跳过静音文件: {audio_file.name}")
                    continue

                # 转写
                logger.info(f"开始转写: {audio_file.name}")
                try:
                    # 声纹分离（可选）
                    diarization_segs = None
                    hf_token = cfg["diarization"].get("hf_token", "")
                    if hf_token:
                        try:
                            from diarizer.speaker_diarizer import SpeakerDiarizer
                            diarizer = SpeakerDiarizer(
                                hf_token=hf_token,
                                speakers_dir=cfg["storage"]["speakers_dir"],
                            )
                            diarization_segs = diarizer.diarize(audio_file).segments
                        except Exception as e:
                            logger.warning(f"声纹分离失败: {e}")

                    result = transcriber.transcribe(audio_file, diarization_segs)

                    if result.segments:
                        append_segments(writer, result, today)
                        logger.info(
                            f"✅ 已写入 Vault: {audio_file.name} "
                            f"({len(result.segments)} 段)"
                        )
                    else:
                        logger.info(f"无有效语音: {audio_file.name}")

                except Exception as e:
                    logger.error(f"转写失败 ({audio_file.name}): {e}")

        except KeyboardInterrupt:
            logger.info("Watch 模式停止")
            break
        except Exception as e:
            logger.error(f"Watch 循环异常: {e}")

        time.sleep(poll_interval)
