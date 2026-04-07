"""热键控制器 — 全局热键启停录音.

默认热键:
  Ctrl+Shift+R  切换录音（启动/暂停）
  Ctrl+Shift+Q  退出

依赖: pynput（uv pip install pynput）
macOS 需要在「系统设置 → 隐私与安全 → 辅助功能」中允许终端/IDE。
"""

from __future__ import annotations

import logging
import subprocess
import threading
from pathlib import Path

logger = logging.getLogger(__name__)


class HotkeyController:
    """全局热键监听器，控制录音启停.

    Args:
        toggle_key: 切换录音的热键组合（pynput 格式）
        quit_key:   退出的热键组合
        on_start:   开始录音的回调
        on_stop:    停止录音的回调
    """

    def __init__(
        self,
        on_start,
        on_stop,
        toggle_combo: str = "<ctrl>+<shift>+r",
        quit_combo: str = "<ctrl>+<shift>+q",
    ) -> None:
        self.on_start = on_start
        self.on_stop = on_stop
        self.toggle_combo = toggle_combo
        self.quit_combo = quit_combo
        self._recording = False
        self._listener = None

    def _toggle(self) -> None:
        if self._recording:
            logger.info("热键触发：停止录音")
            self._recording = False
            self.on_stop()
            _notify("lifelogger", "⏹ 录音已停止")
        else:
            logger.info("热键触发：开始录音")
            self._recording = True
            self.on_start()
            _notify("lifelogger", "🎙 录音已开始")

    def start(self) -> None:
        """启动热键监听（阻塞）."""
        try:
            from pynput import keyboard

            hotkeys = {
                self.toggle_combo: self._toggle,
                self.quit_combo: self._quit,
            }
            logger.info(
                f"热键监听启动 | 切换: {self.toggle_combo} | 退出: {self.quit_combo}"
            )
            with keyboard.GlobalHotKeys(hotkeys) as self._listener:
                self._listener.join()
        except ImportError:
            logger.error("pynput 未安装，热键功能不可用。运行: uv pip install pynput")

    def start_background(self) -> threading.Thread:
        """在后台线程启动热键监听."""
        t = threading.Thread(target=self.start, daemon=True, name="hotkey-listener")
        t.start()
        return t

    def _quit(self) -> None:
        logger.info("热键触发：退出")
        if self._listener:
            self._listener.stop()


def _notify(title: str, message: str) -> None:
    """发送 macOS 系统通知."""
    try:
        subprocess.run(
            [
                "osascript", "-e",
                f'display notification "{message}" with title "{title}"',
            ],
            check=False,
            capture_output=True,
        )
    except Exception:
        pass
