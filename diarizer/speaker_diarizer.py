"""声纹分离模块 — 区分音频中的多个说话人.

使用 pyannote.audio 3.1 进行说话人分割，
结合声纹特征库识别已知说话人。
"""

from __future__ import annotations

import logging
import pickle
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class SpeakerSegment:
    """一段说话人语音片段.

    Attributes:
        speaker_id: 声纹分离原始 ID（如 SPEAKER_00）
        speaker_name: 识别后的真实姓名（如 zyongzhu），未知则为 speaker_id
        start: 开始时间（秒）
        end: 结束时间（秒）
    """

    speaker_id: str      # pyannote 原始 ID: SPEAKER_00 / SPEAKER_01 ...
    speaker_name: str    # 识别后的名字，未识别则等于 speaker_id
    start: float
    end: float

    @property
    def duration(self) -> float:
        return self.end - self.start


@dataclass
class DiarizationResult:
    """声纹分离结果."""

    segments: list[SpeakerSegment] = field(default_factory=list)
    audio_file: str = ""
    num_speakers: int = 0

    @property
    def speakers(self) -> list[str]:
        """返回所有说话人名称（去重）."""
        return list(dict.fromkeys(s.speaker_name for s in self.segments))


class SpeakerDiarizer:
    """说话人分割 + 身份识别.

    Args:
        hf_token: HuggingFace access token（pyannote 需要）
        speakers_dir: 声纹特征存储目录
        match_threshold: 声纹匹配阈值（0-1），越高越严格
        min_speakers: 最少说话人数（-1 自动）
        max_speakers: 最多说话人数（-1 自动）
    """

    def __init__(
        self,
        hf_token: str,
        speakers_dir: str = "~/.lifelogger/speakers",
        match_threshold: float = 0.82,
        min_speakers: int = 1,
        max_speakers: int = -1,
    ) -> None:
        self.hf_token = hf_token
        self.speakers_dir = Path(speakers_dir).expanduser()
        self.match_threshold = match_threshold
        self.min_speakers = min_speakers
        self.max_speakers = max_speakers
        self.speakers_dir.mkdir(parents=True, exist_ok=True)

        self._pipeline = None       # 懒加载 pyannote pipeline
        self._embed_model = None    # 懒加载声纹嵌入模型
        self._known_speakers: dict[str, np.ndarray] = {}  # 已注册声纹

        self._load_known_speakers()

    # ── 懒加载模型 ─────────────────────────────────────────────────────

    def _get_pipeline(self):
        if self._pipeline is None:
            logger.info("加载 pyannote 声纹分离模型...")
            from pyannote.audio import Pipeline
            kwargs = {}
            if self.min_speakers > 0:
                kwargs["min_speakers"] = self.min_speakers
            if self.max_speakers > 0:
                kwargs["max_speakers"] = self.max_speakers
            self._pipeline = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1",
                use_auth_token=self.hf_token,
            )
        return self._pipeline

    def _get_embed_model(self):
        if self._embed_model is None:
            logger.info("加载声纹嵌入模型...")
            from pyannote.audio import Model
            from pyannote.audio.pipelines.speaker_verification import PretrainedSpeakerEmbedding
            self._embed_model = PretrainedSpeakerEmbedding(
                "speechbrain/spkrec-ecapa-voxceleb"
            )
        return self._embed_model

    # ── 声纹注册 ───────────────────────────────────────────────────────

    def _load_known_speakers(self) -> None:
        """从磁盘加载已注册声纹."""
        for npy_file in self.speakers_dir.glob("*.npy"):
            name = npy_file.stem
            self._known_speakers[name] = np.load(npy_file)
        if self._known_speakers:
            logger.info(f"已加载 {len(self._known_speakers)} 个声纹: {list(self._known_speakers.keys())}")

    def register_speaker(self, name: str, audio_file: str | Path, overwrite: bool = False) -> None:
        """注册说话人声纹.

        Args:
            name: 说话人名称（如 "zyongzhu"）
            audio_file: 包含该说话人的音频文件（建议 30s+ 纯人声）
            overwrite: 是否覆盖已有声纹
        """
        save_path = self.speakers_dir / f"{name}.npy"
        if save_path.exists() and not overwrite:
            logger.info(f"声纹已存在: {name}（用 overwrite=True 覆盖）")
            return

        logger.info(f"注册声纹: {name} ← {audio_file}")

        import torchaudio
        waveform, sample_rate = torchaudio.load(str(audio_file))
        # 重采样到 16kHz
        if sample_rate != 16000:
            resampler = torchaudio.transforms.Resample(sample_rate, 16000)
            waveform = resampler(waveform)

        model = self._get_embed_model()
        embedding = model({"waveform": waveform, "sample_rate": 16000})
        embedding_np = embedding.detach().numpy().flatten()

        np.save(save_path, embedding_np)
        self._known_speakers[name] = embedding_np
        logger.info(f"声纹注册完成: {name}")

    def list_speakers(self) -> list[str]:
        """列出已注册的说话人."""
        return list(self._known_speakers.keys())

    # ── 声纹识别 ───────────────────────────────────────────────────────

    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))

    def _identify_speaker(self, embedding: np.ndarray) -> tuple[str, float]:
        """将声纹向量与已知声纹库匹配.

        Returns:
            (name, score) — 最佳匹配名称和相似度分数
        """
        best_name, best_score = "", 0.0
        for name, known_emb in self._known_speakers.items():
            score = self._cosine_similarity(embedding, known_emb)
            if score > best_score:
                best_score, best_name = score, name
        return best_name, best_score

    # ── 核心分割 ───────────────────────────────────────────────────────

    def diarize(self, audio_file: str | Path) -> DiarizationResult:
        """对音频文件进行说话人分割 + 身份识别.

        Args:
            audio_file: 音频文件路径

        Returns:
            DiarizationResult，包含带说话人标签的时间段列表
        """
        audio_file = Path(audio_file)
        logger.info(f"声纹分离: {audio_file.name}")

        pipeline = self._get_pipeline()
        diarization = pipeline(str(audio_file))

        # 提取所有说话人的原始片段
        raw_segments: dict[str, list[tuple[float, float]]] = {}
        for turn, _, speaker_id in diarization.itertracks(yield_label=True):
            if speaker_id not in raw_segments:
                raw_segments[speaker_id] = []
            raw_segments[speaker_id].append((turn.start, turn.end))

        logger.info(f"检测到 {len(raw_segments)} 个说话人: {list(raw_segments.keys())}")

        # 声纹识别：提取每个 SPEAKER_XX 的代表性嵌入并匹配
        speaker_name_map: dict[str, str] = {}
        if self._known_speakers:
            import torchaudio
            from pyannote.audio.utils.signal import Binarize

            embed_model = self._get_embed_model()
            waveform, sr = torchaudio.load(str(audio_file))
            if sr != 16000:
                resampler = torchaudio.transforms.Resample(sr, 16000)
                waveform = resampler(waveform)

            for speaker_id, segs in raw_segments.items():
                # 取最长的 5 个片段做平均嵌入（更准确）
                segs_sorted = sorted(segs, key=lambda s: s[1] - s[0], reverse=True)[:5]
                embeddings = []
                for start, end in segs_sorted:
                    s_idx = int(start * 16000)
                    e_idx = int(end * 16000)
                    chunk = waveform[:, s_idx:e_idx]
                    if chunk.shape[1] < 3200:  # 跳过太短的片段
                        continue
                    emb = embed_model({"waveform": chunk, "sample_rate": 16000})
                    embeddings.append(emb.detach().numpy().flatten())

                if not embeddings:
                    speaker_name_map[speaker_id] = speaker_id
                    continue

                avg_emb = np.mean(embeddings, axis=0)
                name, score = self._identify_speaker(avg_emb)
                if score >= self.match_threshold:
                    speaker_name_map[speaker_id] = name
                    logger.info(f"  {speaker_id} → {name} (相似度: {score:.2f})")
                else:
                    speaker_name_map[speaker_id] = speaker_id
                    logger.info(f"  {speaker_id} → 未知 (最高相似度: {score:.2f})")
        else:
            # 没有注册声纹，直接用原始 ID
            for sid in raw_segments:
                speaker_name_map[sid] = sid

        # 组装最终结果
        all_segments: list[SpeakerSegment] = []
        for speaker_id, segs in raw_segments.items():
            name = speaker_name_map.get(speaker_id, speaker_id)
            for start, end in segs:
                all_segments.append(SpeakerSegment(
                    speaker_id=speaker_id,
                    speaker_name=name,
                    start=start,
                    end=end,
                ))

        all_segments.sort(key=lambda s: s.start)

        return DiarizationResult(
            segments=all_segments,
            audio_file=str(audio_file),
            num_speakers=len(raw_segments),
        )
