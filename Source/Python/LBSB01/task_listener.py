"""
LBSB01 Task Listener — HTTP Server 接收中央派送的列印指令。

Port: 9200（固定，不可設定）
端點: POST /api/lb/task

流程：
  中央 SRVLB001 查 LB_PRINTER.SERVER_IP → HTTP POST 到該台 LBSB01:9200
  → 本模組收到 → 驗證 TOKEN → 寫入 local.db（ONLINE_QUEUE / OFFLINE_QUEUE）
  → 通知 GUI 刷新
"""

from __future__ import annotations
import json
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import tkinter as tk

log = logging.getLogger(__name__)

# 固定 Port（不走參數，避免與 GoDEX 9100 衝突）
LISTENER_PORT = 9200


class _TaskHandler(BaseHTTPRequestHandler):
    """處理中央派送的列印 Task。"""

    # 由 start_listener 注入
    _local_db = None
    _session = None
    _on_task_received = None  # callback: GUI 刷新通知

    def do_POST(self) -> None:
        if self.path != "/api/lb/task":
            self._reply(404, {"success": False, "message": "Not Found"})
            return

        # 驗證 TOKEN（Bearer）
        auth = self.headers.get("Authorization", "")
        if self._session and self._session.token:
            expected = f"Bearer {self._session.token}"
            if auth != expected:
                self._reply(401, {"success": False, "message": "Unauthorized"})
                return

        # 解析 Body
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
        except (json.JSONDecodeError, ValueError):
            self._reply(400, {"success": False, "message": "Invalid JSON"})
            return

        uuid = body.get("uuid", "")
        status = body.get("status", 0)

        if not uuid:
            self._reply(400, {"success": False, "message": "uuid is required"})
            return

        # 寫入 local.db
        try:
            db = self._local_db
            if db is None:
                self._reply(503, {"success": False, "message": "LocalDB not ready"})
                return

            # 寫 LB_PRINT_LOG_CACHE
            db.insert_print_log(body)

            # 依 Status 決定進哪個 Queue
            now = _now()
            if status == 2:
                db._conn.execute(
                    "INSERT INTO OFFLINE_QUEUE (UUID, CREATED_AT) VALUES (?, ?)",
                    (uuid, now))
            else:
                db._conn.execute(
                    "INSERT INTO ONLINE_QUEUE (UUID, CREATED_AT) VALUES (?, ?)",
                    (uuid, now))
            db._conn.commit()

            log.info("Task 收到: uuid=%s status=%d → %s Queue",
                     uuid[:8], status, "Offline" if status == 2 else "Online")

            # 通知 GUI 刷新（thread-safe: 透過 tk.after）
            if self._on_task_received:
                self._on_task_received()

            self._reply(200, {"success": True, "uuid": uuid})

        except Exception as e:
            log.error("Task 處理失敗: %s", e)
            self._reply(500, {"success": False, "message": str(e)})

    def _reply(self, code: int, body: dict) -> None:
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(body, ensure_ascii=False).encode("utf-8"))

    def log_message(self, format, *args) -> None:
        """覆寫預設 log，導到 app log 而非 stderr。"""
        log.debug("HTTP %s", format % args)


def _now() -> str:
    from datetime import datetime
    return datetime.now().isoformat()


def start_listener(
    local_db,
    session,
    app: tk.Tk | None = None,
) -> HTTPServer:
    """啟動 HTTP Listener（背景 daemon Thread）。

    Args:
        local_db: LocalDB instance
        session: Session instance（含 token）
        app: Tkinter root（用於 thread-safe GUI 通知）

    Returns:
        HTTPServer instance（可呼叫 .shutdown() 停止）
    """
    _TaskHandler._local_db = local_db
    _TaskHandler._session = session

    if app is not None:
        # 用 queue 做跨 thread 通知：listener 丟旗標進 queue，main thread 定時 poll
        import queue
        if not hasattr(app, "_task_event_queue"):
            app._task_event_queue = queue.Queue()

        def _notify():
            try:
                app._task_event_queue.put_nowait("task_received")
            except Exception:
                pass
        _TaskHandler._on_task_received = staticmethod(_notify)

    server = HTTPServer(("0.0.0.0", LISTENER_PORT), _TaskHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True, name="TaskListener")
    thread.start()
    log.info("Task Listener 啟動: port=%d", LISTENER_PORT)
    return server
