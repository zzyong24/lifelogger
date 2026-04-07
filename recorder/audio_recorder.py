"""音频录制模块 — 后台持续录音，每小时切割文件.

支持 macOS（BlackHole）和 Linux（ALSA/PulseAudio）。
"""

from __future__ import annotations

import datetime
import logging
import subprocess
import time
from pathlib import Path

logger = logging.getLogger(__name__)


class AudioRecorder:
    """后台音频录制器.

    Args:
        input_device: 录音设备名称（macOS: "BlackHole 2ch"，Linux: "default"）
        recordings_dir: 录音文件存储目录
        chunk_duration: 每段录音时长（秒），默认 3600（1小时）
        sample_rate: 采样率，默认 16000（whisper 标准）
        channels: 声道数，默认 1（单声道）
        audio_format: 输出格式，默认 "mp3"
        bitrate: 比特率，默认 "32k"
    """

    def __init__(
        self,
        input_device: str = "BlackHole 2ch",
        recordings_dir: str = "~/Library/Application Support/lifelogger/recordings",
        chunk_duration: int = 3600,
        sample_rate: int = 16000,
        channels: int = 1,
        audio_format: str = "mp3",
        bitrate: str = "32k",
    ) -> None:
        self.input_device = input_device
        self.recordings_dir = Path(recordings_dir).expanduser()
        self.chunk_duration = chunk_duration
        self.sample_rate = sample_rate
        self.channels = channels
        self.audio_format = audio_format
        self.bitrate = bitrate
        self._process: subprocess.Popen | None = None

        self.recordings_dir.mkdir(parents=True, exist_ok=True)

    def _build_ffmpeg_cmd(self, output_path: Path) -> list[str]:
        """构建 ffmpeg 录音命令.

        macOS 使用 avfoundation，Linux 使用 alsa。
        """
        import platform

        if platform.system() == "Darwin":
            # macOS: avfoundation
            # 支持两种格式:
            #   数字索引: "1" → ":1"（推荐，稳定）
            #   设备名:   "BlackHole 2ch" → ":BlackHole 2ch"
            audio_input = f":{self.input_device}"
            return [
                "ffmpeg", "-y",
                "-f", "avfoundation",
                "-i", audio_input,   # ":设备名/索引" 表示纯音频输入
                "-t", str(self.chunk_duration),
                "-ac", str(self.channels),
                "-ar", str(self.sample_rate),
                "-b:a", self.bitrate,
                str(output_path),
            ]
        else:
            # Linux: alsa
            return [
                "ffmpeg", "-y",
                "-f", "alsa",
                "-i", self.input_device,
                "-t", str(self.chunk_duration),
                "-ac", str(self.channels),
                "-ar", str(self.sample_rate),
                "-b:a", self.bitrate,
                str(output_path),
            ]

    def record_chunk(self) -> Path:
        """录制一段音频，返回文件路径."""
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = self.recordings_dir / f"{timestamp}.{self.audio_format}"

        cmd = self._build_ffmpeg_cmd(output_path)
        logger.info(f"开始录制: {output_path.name}（{self.chunk_duration}s）")

        try:
            subprocess.run(cmd, check=True, capture_output=True)
            logger.info(f"录制完成: {output_path.name} ({output_path.stat().st_size / 1024:.0f} KB)")
            return output_path
        except subprocess.CalledProcessError as e:
            logger.error(f"录制失败: {e.stderr.decode()}")
            raise

    def run_forever(self, stop_event=None) -> None:
        """持续录音，每个 chunk_duration 秒切割一个文件（阻塞）.

        Args:
            stop_event: threading.Event，设置后停止录音（热键模式用）
        """
        logger.info(f"启动持续录音 | 设备: {self.input_device} | 存储: {self.recordings_dir}")
        while True:
            if stop_event and stop_event.is_set():
                logger.info("录制停止（stop_event 触发）")
                break
            try:
                self.record_chunk()
            except KeyboardInterrupt:
                logger.info("录制停止（用户中断）")
                break
            except Exception as e:
                logger.error(f"录制出错，5秒后重试: {e}")
                time.sleep(5)

    def list_recordings(self, date: datetime.date | None = None) -> list[Path]:
        """列出录音文件，可按日期过滤."""
        pattern = f"{date.strftime('%Y%m%d')}*.{self.audio_format}" if date else f"*.{self.audio_format}"
        return sorted(self.recordings_dir.glob(pattern))

    def cleanup_old_recordings(self, retention_days: int = 7) -> int:
        """删除超过 retention_days 天的录音文件，返回删除数量."""
        cutoff = datetime.date.today() - datetime.timedelta(days=retention_days)
        deleted = 0
        for f in self.recordings_dir.glob(f"*.{self.audio_format}"):
            try:
                # 从文件名提取日期（格式: YYYYMMDD_HHMMSS）
                file_date = datetime.date(
                    int(f.stem[:4]), int(f.stem[4:6]), int(f.stem[6:8])
                )
                if file_date < cutoff:
                    f.unlink()
                    deleted += 1
                    logger.debug(f"删除过期录音: {f.name}")
            except (ValueError, IndexError):
                pass
        if deleted:
            logger.info(f"清理完成，删除 {deleted} 个过期录音文件")
        return deleted
