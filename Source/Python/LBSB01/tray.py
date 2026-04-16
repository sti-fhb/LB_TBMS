"""
LBSB01 System Tray 模組。

最小化時收進 Windows 工作列右下角通知區（系統匣）；
右鍵選單可顯示主畫面或結束程式。
"""

from __future__ import annotations
import logging
import threading

import pystray

from icon import make_app_icon

log = logging.getLogger(__name__)


class TrayIcon:
    """背景 Thread 跑 pystray，提供右鍵選單操作主視窗。"""

    def __init__(self, app, on_show, on_quit) -> None:
        self._app = app
        self._on_show = on_show
        self._on_quit = on_quit
        self._icon = pystray.Icon(
            "LBSB01",
            make_app_icon(64),
            "LBSB01 標籤服務程式",
            menu=pystray.Menu(
                pystray.MenuItem("顯示主畫面", self._show, default=True),
                pystray.MenuItem("結束程式", self._quit),
            ),
        )
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._icon.run, daemon=True, name="TrayIcon")
        self._thread.start()
        log.info("System Tray 啟動")

    def stop(self) -> None:
        try:
            self._icon.stop()
        except Exception:
            pass

    # ── Menu callbacks（在 Tray thread 觸發，需排到 main thread）──
    def _show(self, _icon=None, _item=None) -> None:
        try:
            self._app.after(0, self._on_show)
        except Exception:
            pass

    def _quit(self, _icon=None, _item=None) -> None:
        try:
            self._app.after(0, self._on_quit)
        except Exception:
            pass
