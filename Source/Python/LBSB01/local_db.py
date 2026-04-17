"""
LBSB01 本地資料庫模組（SQLite）。

職責：
  1. 本地資料鏡像（LB_PRINTER_CACHE / LB_PRINT_LOG_CACHE）→ 離線可讀寫
  2. Online / Offline Queue → 列印佇列本地持久化
  3. PENDING_OPS → 待同步操作佇列（離線時累積，上線後依序 replay）

檔案位置：主目錄/local.db（與 config.ini 同層）
"""

from __future__ import annotations
import json
import logging
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

from version import VERSION

log = logging.getLogger(__name__)


def _app_dir() -> Path:
    """執行檔所在目錄（支援 PyInstaller onefile）。"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).parent


def build_result(
    fixed: bool = False,
    width: int | None = None,
    height: int | None = None,
    shift_left: int | None = None,
    shift_top: int | None = None,
    darkness: int | None = None,
    memo: str = "",
) -> str:
    """組 RESULT（依 EA Rule {AEF2D0FB-7EE2-4e0f-96C6-22C30BD80E66}）。

    格式：[VERSION] + ['F'?固定參數] + 'W'[寬] + 'H'[長] + 'L'[左位移] + 'T'[上位移] + 'D'[明暗值] + [備註]

    已列印：帶完整 W/H/L/T/D 參數
    純移動/刪除：僅帶備註段（如 -OnLine / -OffLine / -Delete / -Off_DEL）

    範例：
        build_result(width=80, height=35, shift_left=40, shift_top=0, darkness=8)
        → "v1.1r1W80H35L40T0D8"
        build_result(memo="-OffLine")
        → "v1.1r1-OffLine"
    """
    parts = [VERSION]
    if fixed:
        parts.append("F")
    if width is not None:
        parts.append(f"W{width}")
    if height is not None:
        parts.append(f"H{height}")
    if shift_left is not None:
        parts.append(f"L{shift_left}")
    if shift_top is not None:
        parts.append(f"T{shift_top}")
    if darkness is not None:
        parts.append(f"D{darkness}")
    if memo:
        parts.append(memo)
    return "".join(parts)

_DB_FILE = _app_dir() / "local.db"


class LocalDB:
    """SQLite 本地資料庫封裝（WAL mode）。"""

    def __init__(self, db_path: Path | None = None) -> None:
        self._path = db_path or _DB_FILE
        self._conn = sqlite3.connect(str(self._path), check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.row_factory = sqlite3.Row
        self._init_tables()
        log.info("LocalDB 開啟: %s", self._path)

    def close(self) -> None:
        self._conn.close()
        log.info("LocalDB 關閉")

    # ── Schema ───────────────────────────────────────────────

    def _init_tables(self) -> None:
        """建立所有必要的 Table（若不存在）。"""
        self._conn.executescript("""
            -- 印表機設定本地鏡像
            CREATE TABLE IF NOT EXISTS LB_PRINTER_CACHE (
                PRINTER_ID      TEXT PRIMARY KEY,
                PRINTER_NAME    TEXT,
                SITE_ID         TEXT,
                SERVER_IP       TEXT,
                PRINTER_IP      TEXT,
                PRINTER_DRIVER  TEXT,
                SHIFT_LEFT      INTEGER DEFAULT 0,
                SHIFT_TOP       INTEGER DEFAULT 0,
                DARKNESS        INTEGER DEFAULT 12,
                PRINTER_MODEL   TEXT,
                IS_ACTIVE       INTEGER DEFAULT 1,
                NOTE            TEXT,
                UPDATED_AT      TEXT
            );

            -- 列印 LOG 本地鏡像
            CREATE TABLE IF NOT EXISTS LB_PRINT_LOG_CACHE (
                UUID            TEXT PRIMARY KEY,
                BAR_TYPE        TEXT,
                SITE_ID         TEXT,
                PRINTER_ID      TEXT,
                SPECIMEN_NO     TEXT,
                DATA_1          TEXT, DATA_2  TEXT, DATA_3  TEXT, DATA_4  TEXT,
                DATA_5          TEXT, DATA_6  TEXT, DATA_7  TEXT, DATA_8  TEXT,
                DATA_9          TEXT, DATA_10 TEXT, DATA_11 TEXT, DATA_12 TEXT,
                DATA_13         TEXT, DATA_14 TEXT, DATA_15 TEXT, DATA_16 TEXT,
                DATA_17         TEXT, DATA_18 TEXT, DATA_19 TEXT,
                SERVER_IP       TEXT,
                STATUS          INTEGER DEFAULT 0,
                RESULT          TEXT,
                CREATED_USER    TEXT,
                CREATED_AT      TEXT,
                UPDATED_AT      TEXT
            );

            -- Online Queue（Status=0 待列印）
            CREATE TABLE IF NOT EXISTS ONLINE_QUEUE (
                SEQ             INTEGER PRIMARY KEY AUTOINCREMENT,
                UUID            TEXT NOT NULL,
                CREATED_AT      TEXT
            );

            -- Offline Queue（Status=2 離線區）
            CREATE TABLE IF NOT EXISTS OFFLINE_QUEUE (
                SEQ             INTEGER PRIMARY KEY AUTOINCREMENT,
                UUID            TEXT NOT NULL,
                CREATED_AT      TEXT
            );

            -- 待同步操作佇列（離線時累積，上線後 replay）
            CREATE TABLE IF NOT EXISTS PENDING_OPS (
                SEQ             INTEGER PRIMARY KEY AUTOINCREMENT,
                OP_TYPE         TEXT NOT NULL,   -- INSERT / UPDATE / DELETE / CALL_SRV
                TARGET          TEXT NOT NULL,   -- Table 名稱或 SRV 編碼
                PAYLOAD         TEXT NOT NULL,   -- JSON
                CREATED_AT      TEXT NOT NULL,
                STATUS          INTEGER DEFAULT 0  -- 0=待同步, 1=已同步, 2=失敗
            );
        """)
        self._conn.commit()

    # ── PENDING_OPS 操作 ─────────────────────────────────────

    def enqueue_op(self, op_type: str, target: str, payload: dict) -> int:
        """新增一筆待同步操作。回傳 seq。"""
        now = datetime.now().isoformat()
        cur = self._conn.execute(
            "INSERT INTO PENDING_OPS (OP_TYPE, TARGET, PAYLOAD, CREATED_AT, STATUS) "
            "VALUES (?, ?, ?, ?, 0)",
            (op_type, target, json.dumps(payload, ensure_ascii=False), now),
        )
        self._conn.commit()
        seq = cur.lastrowid
        log.debug("PENDING_OPS enqueue: seq=%d op=%s target=%s", seq, op_type, target)
        return seq

    def get_pending_ops(self) -> list[dict]:
        """取得所有待同步操作（status=0），依 seq 排序。"""
        rows = self._conn.execute(
            "SELECT SEQ, OP_TYPE, TARGET, PAYLOAD, CREATED_AT "
            "FROM PENDING_OPS WHERE STATUS=0 ORDER BY SEQ"
        ).fetchall()
        return [
            {
                "seq": r["SEQ"],
                "op_type": r["OP_TYPE"],
                "target": r["TARGET"],
                "payload": json.loads(r["PAYLOAD"]),
                "created_at": r["CREATED_AT"],
            }
            for r in rows
        ]

    def mark_op_synced(self, seq: int) -> None:
        """標記操作已同步。"""
        self._conn.execute("UPDATE PENDING_OPS SET STATUS=1 WHERE SEQ=?", (seq,))
        self._conn.commit()

    def mark_op_failed(self, seq: int) -> None:
        """標記操作同步失敗。"""
        self._conn.execute("UPDATE PENDING_OPS SET STATUS=2 WHERE SEQ=?", (seq,))
        self._conn.commit()

    def retry_failed_ops(self) -> None:
        """將失敗的操作重設為待同步（下次重試）。"""
        self._conn.execute("UPDATE PENDING_OPS SET STATUS=0 WHERE STATUS=2")
        self._conn.commit()

    def pending_count(self) -> int:
        """待同步筆數。"""
        row = self._conn.execute("SELECT COUNT(*) FROM PENDING_OPS WHERE STATUS=0").fetchone()
        return row[0]

    # ── LB_PRINTER_CACHE 操作 ────────────────────────────────

    def list_printers(self, site_id: str) -> list[dict]:
        """查詢站點印表機清單。"""
        rows = self._conn.execute(
            "SELECT * FROM LB_PRINTER_CACHE WHERE SITE_ID=? ORDER BY PRINTER_ID",
            (site_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_printer(self, printer_id: str) -> dict | None:
        """取得單筆印表機。"""
        row = self._conn.execute(
            "SELECT * FROM LB_PRINTER_CACHE WHERE PRINTER_ID=?", (printer_id,)
        ).fetchone()
        return dict(row) if row else None

    def printer_exists(self, printer_id: str) -> bool:
        """檢查印表機編號是否已存在。"""
        row = self._conn.execute(
            "SELECT 1 FROM LB_PRINTER_CACHE WHERE PRINTER_ID=?", (printer_id,)
        ).fetchone()
        return row is not None

    def insert_printer(self, data: dict) -> None:
        """新增印表機（Local Cache）。"""
        now = datetime.now().isoformat()
        self._conn.execute(
            "INSERT OR REPLACE INTO LB_PRINTER_CACHE "
            "(PRINTER_ID, PRINTER_NAME, SITE_ID, SERVER_IP, PRINTER_IP, PRINTER_DRIVER, "
            " SHIFT_LEFT, SHIFT_TOP, DARKNESS, PRINTER_MODEL, IS_ACTIVE, NOTE, UPDATED_AT) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                data.get("printer_id"), data.get("printer_name"), data.get("site_id"),
                data.get("server_ip"), data.get("printer_ip"), data.get("printer_driver"),
                data.get("shift_left", 0), data.get("shift_top", 0), data.get("darkness", 12),
                data.get("printer_model"), data.get("is_active", 1), data.get("note"), now,
            ),
        )
        self._conn.commit()

    def update_printer(self, data: dict) -> None:
        """更新印表機（Local Cache）。"""
        now = datetime.now().isoformat()
        self._conn.execute(
            "UPDATE LB_PRINTER_CACHE SET "
            "PRINTER_NAME=?, SITE_ID=?, SERVER_IP=?, PRINTER_IP=?, PRINTER_DRIVER=?, "
            "SHIFT_LEFT=?, SHIFT_TOP=?, DARKNESS=?, PRINTER_MODEL=?, IS_ACTIVE=?, NOTE=?, "
            "UPDATED_AT=? WHERE PRINTER_ID=?",
            (
                data.get("printer_name"), data.get("site_id"),
                data.get("server_ip"), data.get("printer_ip"), data.get("printer_driver"),
                data.get("shift_left", 0), data.get("shift_top", 0), data.get("darkness", 12),
                data.get("printer_model"), data.get("is_active", 1), data.get("note"),
                now, data.get("printer_id"),
            ),
        )
        self._conn.commit()

    def delete_printer(self, printer_id: str) -> None:
        """刪除印表機（Local Cache）。"""
        self._conn.execute("DELETE FROM LB_PRINTER_CACHE WHERE PRINTER_ID=?", (printer_id,))
        self._conn.commit()

    def replace_all_printers(self, site_id: str, printers: list[dict]) -> None:
        """全量刷新某站點的印表機清單（上線同步後用）。"""
        self._conn.execute("DELETE FROM LB_PRINTER_CACHE WHERE SITE_ID=?", (site_id,))
        for p in printers:
            self.insert_printer(p)

    # ── Queue Task 操作 ──────────────────────────────────────

    def delete_queue_task(self, uuid: str, online: bool) -> None:
        """刪除 Queue 單筆：

        - 從 ONLINE_QUEUE 或 OFFLINE_QUEUE 移除
        - LB_PRINT_LOG_CACHE: Status=1（終態），RESULT 加備註（-Delete / -Off_DEL）
        """
        memo = "-Delete" if online else "-Off_DEL"
        result = build_result(memo=memo)

        # 先從 Queue 表移除
        table = "ONLINE_QUEUE" if online else "OFFLINE_QUEUE"
        self._conn.execute(f"DELETE FROM {table} WHERE UUID=?", (uuid,))
        self._conn.commit()

        # 更新 LOG 狀態
        self.update_print_log(uuid, status=1, result=result)
        log.debug("Queue task 刪除: uuid=%s table=%s", uuid[:8], table)

    def move_task_to_offline(self, uuid: str) -> None:
        """Online → Offline（雙擊移動）。"""
        row = self._conn.execute(
            "SELECT CREATED_AT FROM ONLINE_QUEUE WHERE UUID=?", (uuid,)
        ).fetchone()
        if not row:
            return
        now = datetime.now().isoformat()
        self._conn.execute("DELETE FROM ONLINE_QUEUE WHERE UUID=?", (uuid,))
        self._conn.execute(
            "INSERT INTO OFFLINE_QUEUE (UUID, CREATED_AT) VALUES (?, ?)",
            (uuid, now),
        )
        self._conn.commit()
        self.update_print_log(uuid, status=2, result=build_result(memo="-OffLine"))

    def move_task_to_online(self, uuid: str) -> None:
        """Offline → Online（雙擊移回）。"""
        row = self._conn.execute(
            "SELECT CREATED_AT FROM OFFLINE_QUEUE WHERE UUID=?", (uuid,)
        ).fetchone()
        if not row:
            return
        now = datetime.now().isoformat()
        self._conn.execute("DELETE FROM OFFLINE_QUEUE WHERE UUID=?", (uuid,))
        self._conn.execute(
            "INSERT INTO ONLINE_QUEUE (UUID, CREATED_AT) VALUES (?, ?)",
            (uuid, now),
        )
        self._conn.commit()
        self.update_print_log(uuid, status=0, result=build_result(memo="-OnLine"))

    def override_task_printer(self, uuid: str, new_printer_id: str) -> None:
        """覆寫 Task 的目標印表機。"""
        self._conn.execute(
            "UPDATE LB_PRINT_LOG_CACHE SET PRINTER_ID=?, UPDATED_AT=? WHERE UUID=?",
            (new_printer_id, datetime.now().isoformat(), uuid),
        )
        self._conn.commit()

    # ── Queue 查詢（給 GUI 顯示用）──────────────────────────

    def list_online_queue(self) -> list[dict]:
        """讀取 Online Queue 清單（join LB_PRINT_LOG_CACHE 取顯示資訊）。"""
        return self._list_queue("ONLINE_QUEUE")

    def list_offline_queue(self) -> list[dict]:
        """讀取 Offline Queue 清單。"""
        return self._list_queue("OFFLINE_QUEUE")

    def _list_queue(self, table: str) -> list[dict]:
        rows = self._conn.execute(f"""
            SELECT q.SEQ, q.UUID, q.CREATED_AT,
                   l.BAR_TYPE, l.PRINTER_ID, l.SPECIMEN_NO
              FROM {table} q
              LEFT JOIN LB_PRINT_LOG_CACHE l ON l.UUID = q.UUID
             ORDER BY q.SEQ
        """).fetchall()
        return [dict(r) for r in rows]

    # ── LB_PRINT_LOG_CACHE 操作 ──────────────────────────────

    def insert_print_log(self, data: dict) -> None:
        """寫入列印 LOG（由 Task Listener 收到 Task 時呼叫）。"""
        now = datetime.now().isoformat()
        self._conn.execute(
            "INSERT OR REPLACE INTO LB_PRINT_LOG_CACHE "
            "(UUID, BAR_TYPE, SITE_ID, PRINTER_ID, SPECIMEN_NO, "
            " DATA_1, DATA_2, DATA_3, DATA_4, DATA_5, DATA_6, DATA_7, DATA_8, DATA_9, DATA_10, "
            " DATA_11, DATA_12, DATA_13, DATA_14, DATA_15, DATA_16, DATA_17, DATA_18, DATA_19, "
            " SERVER_IP, STATUS, RESULT, CREATED_USER, CREATED_AT, UPDATED_AT) "
            "VALUES (?,?,?,?,?, ?,?,?,?,?,?,?,?,?,?, ?,?,?,?,?,?,?,?,?, ?,?,?,?,?,?)",
            (
                data.get("uuid"), data.get("bar_type"), data.get("site_id"),
                data.get("printer_id"), data.get("specimen_no"),
                data.get("data_1"), data.get("data_2"), data.get("data_3"),
                data.get("data_4"), data.get("data_5"), data.get("data_6"),
                data.get("data_7"), data.get("data_8"), data.get("data_9"),
                data.get("data_10"), data.get("data_11"), data.get("data_12"),
                data.get("data_13"), data.get("data_14"), data.get("data_15"),
                data.get("data_16"), data.get("data_17"), data.get("data_18"),
                data.get("data_19"),
                data.get("server_ip"), data.get("status", 0), data.get("result"),
                data.get("created_user"), now, now,
            ),
        )
        self._conn.commit()

    def update_print_log(self, uuid: str, status: int | None = None,
                         result: str | None = None) -> None:
        """更新列印 LOG 狀態與 RESULT。"""
        updates, params = [], []
        if status is not None:
            updates.append("STATUS=?")
            params.append(status)
        if result is not None:
            updates.append("RESULT=?")
            params.append(result)
        if not updates:
            return
        updates.append("UPDATED_AT=?")
        params.append(datetime.now().isoformat())
        params.append(uuid)
        self._conn.execute(
            f"UPDATE LB_PRINT_LOG_CACHE SET {', '.join(updates)} WHERE UUID=?",
            params,
        )
        self._conn.commit()

    # ── 便利方法：寫 Local + 排 PENDING_OPS ──────────────────

    def add_printer(self, data: dict, _online: bool = False) -> tuple[bool, str]:
        """新增印表機。寫 Local Cache + 排入 PENDING_OPS（線上由背景同步 Thread 處理）。"""
        pid = data.get("printer_id", "").strip()
        if not pid:
            return False, "印表機編號不可為空"
        if self.printer_exists(pid):
            return False, f"印表機編號 {pid} 已存在，請使用不同編號"

        self.insert_printer(data)
        self.enqueue_op("INSERT", "LB_PRINTER", data)
        return True, "OK"

    def save_printer(self, data: dict, _online: bool = False) -> tuple[bool, str]:
        """更新印表機。寫 Local Cache + 排入 PENDING_OPS（線上由背景同步 Thread 處理）。"""
        ip = (data.get("printer_ip") or "").strip()
        drv = (data.get("printer_driver") or "").strip()
        if ip and drv:
            return False, "印表機 IP 與 Driver 不可同時填值（互斥）"

        self.update_printer(data)
        self.enqueue_op("UPDATE", "LB_PRINTER", data)
        return True, "OK"

    def remove_printer(self, site_id: str, printer_id: str, _online: bool = False) -> tuple[bool, str]:
        """刪除印表機。寫 Local Cache + 排入 PENDING_OPS（含跨模組 SRV）。"""
        self.delete_printer(printer_id)
        # 順序保證：先 SRVDP020-刪除元件設備標籤對應（清 DP 子表）→ 再 DELETE LB_PRINTER
        self.enqueue_op("CALL_SRV", "SRVDP020",
                        {"site_id": site_id, "printer_id": printer_id})
        self.enqueue_op("DELETE", "LB_PRINTER",
                        {"printer_id": printer_id})
        return True, "OK"
