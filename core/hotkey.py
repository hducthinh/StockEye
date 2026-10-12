from __future__ import annotations

import sys
import time
from PyQt5.QtCore import QThread, pyqtSignal

VK_KEY_3 = 0x33
VK_KEY_4 = 0x34
VK_KEY_5 = 0x35
VK_KEY_6 = 0x36
VK_KEY_7 = 0x37

VK_NUMPAD_3 = 0x63
VK_NUMPAD_4 = 0x64
VK_NUMPAD_5 = 0x65
VK_NUMPAD_6 = 0x66
VK_NUMPAD_7 = 0x67


class GlobalHotkeyListener(QThread):
    """
    Background worker that listens for global key presses on Windows.
    - Key 3: resync_requested
    - Key 4: pause_toggled
    - Key 5: preset_requested("standard")
    - Key 6: preset_requested("puzzle")
    - Key 7: toggle_visibility_requested
    """
    resync_requested = pyqtSignal()
    pause_toggled = pyqtSignal()
    preset_requested = pyqtSignal(str)
    toggle_visibility_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = True

    def stop(self) -> None:
        self._running = False

    def run(self) -> None:
        if sys.platform != "win32":
            return

        import ctypes
        user32 = ctypes.windll.user32

        prev_3 = False
        prev_4 = False
        prev_5 = False
        prev_6 = False
        prev_7 = False
        last_trigger_times = {3: 0.0, 4: 0.0, 5: 0.0, 6: 0.0, 7: 0.0}
        debounce_sec = 0.35

        while self._running:
            try:
                # Key 3 check (Resync)
                down_3 = bool(
                    (user32.GetAsyncKeyState(VK_KEY_3) & 0x8000)
                    or (user32.GetAsyncKeyState(VK_NUMPAD_3) & 0x8000)
                )
                # Key 4 check (Toggle Pause)
                down_4 = bool(
                    (user32.GetAsyncKeyState(VK_KEY_4) & 0x8000)
                    or (user32.GetAsyncKeyState(VK_NUMPAD_4) & 0x8000)
                )
                # Key 5 check (Standard Board)
                down_5 = bool(
                    (user32.GetAsyncKeyState(VK_KEY_5) & 0x8000)
                    or (user32.GetAsyncKeyState(VK_NUMPAD_5) & 0x8000)
                )
                # Key 6 check (Puzzle Rush)
                down_6 = bool(
                    (user32.GetAsyncKeyState(VK_KEY_6) & 0x8000)
                    or (user32.GetAsyncKeyState(VK_NUMPAD_6) & 0x8000)
                )
                # Key 7 check (Toggle Tool Visibility)
                down_7 = bool(
                    (user32.GetAsyncKeyState(VK_KEY_7) & 0x8000)
                    or (user32.GetAsyncKeyState(VK_NUMPAD_7) & 0x8000)
                )

                now = time.monotonic()
                if down_3 and not prev_3:
                    if now - last_trigger_times[3] >= debounce_sec:
                        last_trigger_times[3] = now
                        self.resync_requested.emit()
                elif down_4 and not prev_4:
                    if now - last_trigger_times[4] >= debounce_sec:
                        last_trigger_times[4] = now
                        self.pause_toggled.emit()
                elif down_5 and not prev_5:
                    if now - last_trigger_times[5] >= debounce_sec:
                        last_trigger_times[5] = now
                        self.preset_requested.emit("standard")
                elif down_6 and not prev_6:
                    if now - last_trigger_times[6] >= debounce_sec:
                        last_trigger_times[6] = now
                        self.preset_requested.emit("puzzle")
                elif down_7 and not prev_7:
                    if now - last_trigger_times[7] >= debounce_sec:
                        last_trigger_times[7] = now
                        self.toggle_visibility_requested.emit()

                prev_3 = down_3
                prev_4 = down_4
                prev_5 = down_5
                prev_6 = down_6
                prev_7 = down_7

            except Exception:
                pass

            time.sleep(0.04)  # ~25 checks per second, negligible CPU usage (<0.01%)
