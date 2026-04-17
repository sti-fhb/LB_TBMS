"""
LBSB01 — 標籤服務程式 (Python 版)。

三層 Queue 架構：
  1. Online Queue  — API 傳入的列印指令（本地暫存）
  2. Offline Queue — 離線/重印項目（本地暫存）
  3. DB Log Queue  — 呼叫 API 寫入 DB（記錄所有進出與異動）

啟動入口：python main.py（後續會加 Login 頁面）
"""

from __future__ import annotations
import logging
import os
import time
import traceback
import tkinter as tk
from tkinter import ttk, messagebox

from labels import LABEL_DEFS, LABEL_MAP, PAPER_SIZES, LabelDef
from sample_data import LabelData
from sample_data_print import SampleDataPrint, print_label
from printer_setting import PrinterSetting
from ezpl import GodexPrinter, LinkType
from login import authenticate, Session, _health_check, HARDCODED_TOKEN
from local_db import LocalDB
from central_api import replay_op
from task_listener import start_listener, LISTENER_PORT
from version import VERSION
from tray import TrayIcon

# ── Log（LBSB01{YYYYMMDD}.log，存放於主目錄\Log）──
# 僅記錄 Login/Logout/系統訊息，不記錄操作細節（level=INFO）
def _init_log() -> logging.Logger:
    from datetime import date
    import sys as _sys
    # PyInstaller onefile: 用 sys.executable 取真正執行檔目錄，不要用 __file__（臨時目錄）
    if getattr(_sys, "frozen", False):
        app_dir = os.path.dirname(_sys.executable)
    else:
        app_dir = os.path.dirname(os.path.abspath(__file__))
    log_dir = os.path.join(app_dir, "Log")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f"LBSB01{date.today().strftime('%Y%m%d')}.log")
    logging.basicConfig(
        filename=log_file,
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        encoding="utf-8",
    )
    return logging.getLogger(__name__)

log = _init_log()

# ── 藍色色系 ─────────────────────────────────────────────────
CLR_BG = "#D6E4F0"           # 主背景（淺藍）
CLR_ONLINE_BG = "#C0D8F0"    # 線上區背景
CLR_ONLINE_FG = "#003366"    # 線上區前景（深藍）
CLR_OFFLINE_BG = "#4A7FB5"   # 離線區背景（深藍）
CLR_OFFLINE_FG = "#FFFFFF"   # 離線區前景（白）
CLR_TITLE_FG = "#003366"     # 標題前景
CLR_ACCENT = "#1A5276"       # 強調色
CLR_BTN_BG = "#2E86C1"       # 一般按鈕背景
CLR_BTN_FG = "#FFFFFF"       # 一般按鈕前景
CLR_PRINT_BG = "#D35400"    # 線上列印按鈕背景（橘）
CLR_PRINT_FG = "#FFFFFF"    # 線上列印按鈕前景


class App(tk.Tk):

    def __init__(self) -> None:
        super().__init__()
        log.info("LBSB01 啟動 %s", VERSION)
        self.title(f"LBSB01-標籤服務程式 {VERSION}")
        self.geometry("1010x720")
        self.resizable(True, True)
        self.configure(bg=CLR_BG)

        # 視窗 icon（仿 GoDEX 桌上型印表機）
        self._app_icon = self._make_printer_icon()
        self.iconphoto(True, self._app_icon)

        # ── APIDP001 自動認證（認證失敗仍可執行：離線模式）──
        self._show_auth_splash()
        self.session: Session = authenticate()
        self._remove_auth_splash()

        # ── LocalDB + Task Listener ──
        self.local_db = LocalDB()
        self._http_server = start_listener(self.local_db, self.session, app=self)
        self._poll_task_events()  # 定時從 queue 取 Listener 通知

        if self.session.online:
            self._log_msg(f"LOGIN 成功（線上模式）: site={self.session.site_id}")
            messagebox.showinfo("連線成功",
                f"已連線至主系統\n站點：{self.session.site_name}")
            self._start_sync_timer()
        else:
            self._log_msg(f"LOGIN 離線作業: site={self.session.site_id}")
            messagebox.showinfo("離線作業",
                f"目前為離線作業模式\n\n"
                f"站點：{self.session.site_name}\n\n"
                f"連線至主系統後將自動切換為線上模式")
            self._start_reconnect_timer()

        self._log_msg(f"Task Listener 啟動: port={LISTENER_PORT}")
        self._update_mode_display()
        self._build_menu()
        self._build_ui()
        self._load_printer_combos()

        # ── System Tray（最小化/關閉時收進右下角通知區）──
        self._tray = TrayIcon(self, on_show=self._show_window, on_quit=self._quit_app)
        self._tray.start()
        self.protocol("WM_DELETE_WINDOW", self._confirm_quit)
        self.bind("<Unmap>", self._on_unmap)
        self._user_quit = False
        self._refresh_queues()  # 啟動時載入現有 Queue

    # ── App Icon（主畫面 Title Bar 與系統匣共用同一張 PIL 圖）──
    def _make_printer_icon(self) -> tk.PhotoImage:
        """用 PIL 繪製印表機 icon 並轉為 tk.PhotoImage（與系統匣同源）。"""
        from PIL import ImageTk
        from icon import make_app_icon
        self._pil_icon = make_app_icon(64)  # 保留 ref，避免 GC 回收
        return ImageTk.PhotoImage(self._pil_icon)

    # ── Mode Display ─────────────────────────────────────────
    def _update_mode_display(self) -> None:
        mode = "線上" if self.session.online else "離線"
        self.title(f"LBSB01-標籤服務程式 {VERSION}  [{self.session.site_name}]  【{mode}】")
        if hasattr(self, "lbl_status"):
            if self.session.online:
                self.lbl_status.config(text="  ● 線上  ", bg="#27AE60")
            else:
                self.lbl_status.config(text="  ● 離線  ", bg="#CC0000")

    # ── Reconnect Timer（離線時每 60 秒嘗試重連）──────────────
    _reconnect_id: str | None = None

    def _start_reconnect_timer(self) -> None:
        if self._reconnect_id is not None:
            return  # 已在運行
        self._reconnect_id = self.after(60_000, self._try_reconnect)

    def _try_reconnect(self) -> None:
        """每 60 秒健康檢查中央；成功後切換線上、同步 Local 暫存。"""
        self._reconnect_id = None
        if self.session.online:
            return  # 已上線，不再重試

        if _health_check():
            self.session.online = True
            self.session.token = HARDCODED_TOKEN
            self.session.error_message = ""
            self._log_msg(f"重連成功 → 切換為線上模式: site={self.session.site_id}")
            self._update_mode_display()
            self._sync_local_to_db()
            self._start_sync_timer()
        else:
            # 仍離線 → 60 秒後再試
            self._reconnect_id = self.after(60_000, self._try_reconnect)

    def _sync_local_to_db(self) -> None:
        """上線後 replay PENDING_OPS 至中央 DB，再全量刷新 Local Cache。"""
        ops = self.local_db.get_pending_ops()
        if not ops:
            self._log_msg("無待同步操作")
            return

        token = HARDCODED_TOKEN

        total = len(ops)
        self._log_msg(f"開始同步 {total} 筆待同步操作至主 DB ...")

        ok_count = 0
        fail_count = 0
        for op in ops:
            seq = op["seq"]
            success, msg = replay_op(
                token,
                op["op_type"], op["target"], op["payload"],
            )
            if success:
                self.local_db.mark_op_synced(seq)
                ok_count += 1
            else:
                self.local_db.mark_op_failed(seq)
                fail_count += 1
                self._log_msg(f"同步失敗 SEQ={seq} [{op['op_type']}/{op['target']}]: {msg}")

        self._log_msg(f"同步完成: 成功 {ok_count} 筆, 失敗 {fail_count} 筆")

    # ── 背景同步 Timer（線上時每 30 秒處理 PENDING_OPS）──────
    _sync_timer_id: str | None = None

    def _start_sync_timer(self) -> None:
        """啟動背景同步計時器（線上模式時定期處理 PENDING_OPS）。"""
        if self._sync_timer_id is not None:
            return
        self._sync_timer_id = self.after(30_000, self._sync_tick)

    def _stop_sync_timer(self) -> None:
        if self._sync_timer_id is not None:
            self.after_cancel(self._sync_timer_id)
            self._sync_timer_id = None

    def _sync_tick(self) -> None:
        """每 30 秒檢查 PENDING_OPS，有待同步就 replay。"""
        self._sync_timer_id = None
        if not self.session.online:
            return  # 離線不同步
        pending = self.local_db.pending_count()
        if pending > 0:
            self._sync_local_to_db()
        # 排下一次
        if self.session.online:
            self._sync_timer_id = self.after(30_000, self._sync_tick)

    # ── Auto Print（勾選後每 2 秒自動送印 Online Queue 第一筆）──
    _auto_print_id: str | None = None

    def _on_auto_toggle(self, *_args) -> None:
        """Auto CheckBox 切換 → 啟動/停止自動列印計時器。"""
        if self.var_auto.get():
            self._log_msg("Auto 自動列印已啟動")
            self._auto_print_tick()
        else:
            self._log_msg("Auto 自動列印已停止")
            if self._auto_print_id is not None:
                self.after_cancel(self._auto_print_id)
                self._auto_print_id = None

    def _auto_print_tick(self) -> None:
        """每 2 秒檢查 Online Queue，有項目就自動送印第一筆。"""
        self._auto_print_id = None
        if not self.var_auto.get():
            return
        queue_list = self.local_db.list_online_queue()
        if queue_list:
            # 自動選取第一筆
            self.lst_queue.selection_clear(0, "end")
            self.lst_queue.selection_set(0)
            self._on_online_select()
            self._on_print()
        # 排下一次（無論有無項目都繼續 tick）
        if self.var_auto.get():
            self._auto_print_id = self.after(2000, self._auto_print_tick)

    # ── Task Events Poll（每 200ms 從 queue 取 Listener 通知）──
    def _poll_task_events(self) -> None:
        """Main thread 定時 poll task queue；有事件就刷新畫面。"""
        q = getattr(self, "_task_event_queue", None)
        if q is not None:
            try:
                while True:
                    q.get_nowait()
                    self._on_task_received()
            except Exception:
                pass
        self.after(200, self._poll_task_events)

    def _on_task_received(self) -> None:
        """Task Listener 收到新 Task 時，刷新 Online/Offline Queue 畫面。"""
        self._add_msg("收到新列印指令")
        self._refresh_queues()

    def _refresh_queues(self) -> None:
        """從 local.db 重新載入 Online / Offline Queue ListBox。"""
        if not hasattr(self, "lst_queue") or not hasattr(self, "lst_wait"):
            return
        # Online
        self.lst_queue.delete(0, "end")
        for r in self.local_db.list_online_queue():
            self.lst_queue.insert("end", self._fmt_queue_item(r))
        # Offline
        self.lst_wait.delete(0, "end")
        for r in self.local_db.list_offline_queue():
            self.lst_wait.insert("end", self._fmt_queue_item(r))

    @staticmethod
    def _fmt_queue_item(r: dict) -> str:
        ts = App._fmt_ts(r.get("CREATED_AT") or "")
        return f"{ts}  {r.get('BAR_TYPE') or '?'}  {r.get('PRINTER_ID') or '?'}  {r.get('SPECIMEN_NO') or ''}"

    @staticmethod
    def _fmt_ts(iso: str) -> str:
        """ISO timestamp → 'YYYY-MM-DD HH:MM:SS.fff'（毫秒至千分之一秒）。"""
        if not iso:
            return ""
        # iso 格式如 '2026-04-15T14:30:45.123456' 或 '2026-04-15T14:30:45'
        s = iso.replace("T", " ")
        if "." in s:
            head, frac = s.split(".", 1)
            frac = (frac + "000")[:3]  # 取前 3 位（毫秒），不足補 0
            return f"{head}.{frac}"
        return f"{s}.000"

    # ── Queue 點選 → 明細帶入左側 ──────────────────────────
    def _on_online_select(self, _event=None) -> None:
        self._fill_detail(self.lst_queue, self.local_db.list_online_queue(), online=True)

    def _on_offline_select(self, _event=None) -> None:
        self._fill_detail(self.lst_wait, self.local_db.list_offline_queue(), online=False)

    def _on_online_dblclick(self, _event=None) -> None:
        """雙擊 Online 項目 → 移至 Offline Queue。"""
        queue_list = self.local_db.list_online_queue()
        sel = self.lst_queue.curselection()
        if not sel or sel[0] >= len(queue_list):
            return
        row = queue_list[sel[0]]
        uuid = row.get("UUID", "")
        self.local_db.move_task_to_offline(uuid)
        self._refresh_queues()
        self._log_msg(f"移至離線區: {row.get('BAR_TYPE','')} @ {row.get('PRINTER_ID','')}")

    def _on_offline_dblclick(self, _event=None) -> None:
        """雙擊 Offline 項目 → 移回 Online Queue。"""
        queue_list = self.local_db.list_offline_queue()
        sel = self.lst_wait.curselection()
        if not sel or sel[0] >= len(queue_list):
            return
        row = queue_list[sel[0]]
        uuid = row.get("UUID", "")
        self.local_db.move_task_to_online(uuid)
        self._refresh_queues()
        self._log_msg(f"移回線上區: {row.get('BAR_TYPE','')} @ {row.get('PRINTER_ID','')}")

    def _fill_detail(self, listbox: tk.Listbox, queue_list: list[dict], online: bool) -> None:
        sel = listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        if idx >= len(queue_list):
            return
        q = queue_list[idx]
        uuid = q.get("UUID", "")
        # 從 LB_PRINT_LOG_CACHE 取完整資料
        row = self.local_db._conn.execute(
            "SELECT * FROM LB_PRINT_LOG_CACHE WHERE UUID=?", (uuid,)
        ).fetchone()
        if not row:
            return
        row = dict(row)

        # Online 區填左側 var_sn / var_type / var_count / var_user / var_printer_no / var_uuid
        # Offline 區填對應的 off_var_* 欄位
        prefix = "" if online else "off_"
        self._set_var(f"{prefix}var_sn", self._fmt_ts(row.get("CREATED_AT", "")))
        self._set_var(f"{prefix}var_type", row.get("BAR_TYPE", ""))
        self._set_var(f"{prefix}var_user", row.get("CREATED_USER", "") or "")
        self._set_var(f"{prefix}var_printer_no", row.get("PRINTER_ID", ""))
        # 顯示標籤中文名（lbl_sname / off_lbl_sname）
        from labels import LABEL_MAP
        ld = LABEL_MAP.get(row.get("BAR_TYPE", ""))
        lbl = getattr(self, f"{prefix}lbl_sname", None)
        if lbl is not None:
            lbl.config(text=ld.name if ld else "")

        # 未勾選固定參數時，自動帶入紙張尺寸 + 印表機 shift/darkness
        if online and not self.var_fix_size.get():
            if ld:
                self.var_w.set(str(ld.width_mm))
                self.var_h.set(str(ld.height_mm))
                size_str = ld.size_display
                if size_str in self.cmb_size["values"]:
                    self.cmb_size.set(size_str)
            printer_id = row.get("PRINTER_ID", "")
            p = self.local_db.get_printer(printer_id)
            if p:
                self.var_shift_l.set(str(p.get("SHIFT_LEFT") or 0))
                self.var_shift_t.set(str(p.get("SHIFT_TOP") or 0))
                self.var_dark.set(str(p.get("DARKNESS") or 12))

    def _set_var(self, name: str, value: str) -> None:
        v = getattr(self, name, None)
        if v is not None:
            v.set(str(value))

    def _load_printer_combos(self) -> None:
        """載入站點印表機清單到 Online / Offline 明細區的「指定/變更印表機」下拉。"""
        printers = self.local_db.list_printers(self.session.site_id)
        values = [f"{p['PRINTER_ID']}-{p['PRINTER_NAME']}" for p in printers]
        if hasattr(self, "cmb_printer"):
            self.cmb_printer["values"] = values
        if hasattr(self, "off_cmb_printer"):
            self.off_cmb_printer["values"] = values

    def _override_printer(self, online: bool) -> None:
        """使用者在明細區下拉變更印表機 → 覆寫該筆 Task 的 PRINTER_ID。"""
        listbox = self.lst_queue if online else self.lst_wait
        queue_list = (self.local_db.list_online_queue() if online
                      else self.local_db.list_offline_queue())
        sel = listbox.curselection()
        if not sel or sel[0] >= len(queue_list):
            return
        uuid = queue_list[sel[0]].get("UUID", "")
        cmb = self.cmb_printer if online else self.off_cmb_printer
        val = cmb.get().strip()
        if not val:
            return
        new_pid = val.split("-", 1)[0]
        self.local_db.override_task_printer(uuid, new_pid)
        self._refresh_queues()
        self._add_msg(f"變更列印項目印表機 → {new_pid}")

    def _on_delete_queue(self, online: bool) -> None:
        """刪除 Queue 單筆（Online/Offline）。"""
        listbox = self.lst_queue if online else self.lst_wait
        queue_list = (self.local_db.list_online_queue() if online
                      else self.local_db.list_offline_queue())
        sel = listbox.curselection()
        if not sel:
            messagebox.showwarning("刪除", "請先選取一筆列印項目")
            return
        idx = sel[0]
        if idx >= len(queue_list):
            return
        uuid = queue_list[idx].get("UUID", "")
        bar_type = queue_list[idx].get("BAR_TYPE", "")
        printer_id = queue_list[idx].get("PRINTER_ID", "")
        if not messagebox.askyesno(
            "刪除確認",
            f"確定刪除該筆列印項目？\n\n"
            f"標籤: {bar_type}\n印表機: {printer_id}",
            icon="warning",
        ):
            return
        self.local_db.delete_queue_task(uuid, online=online)
        self._refresh_queues()
        self._add_msg(f"刪除列印項目: {bar_type} @ {printer_id}")

    # ── System Tray ─────────────────────────────────────────
    def _confirm_quit(self) -> None:
        """按 X 或 系統匣「結束程式」→ 確認後才真的退出。"""
        if messagebox.askyesno(
            "確認關閉",
            "確定要關閉 LBSB01 嗎？\n\n"
            "關閉後無法接收列印指令，\n"
            "若只是要暫時隱藏畫面，請改用最小化（─）收至系統匣。",
            icon="warning",
        ):
            self._user_quit = True
            self.destroy()

    def _on_unmap(self, _event=None) -> None:
        """最小化（─）→ 隱藏視窗到系統匣（不 Prompt）。"""
        if self.state() == "iconic":
            self.withdraw()
            self._add_msg("已最小化至系統匣（右下角圖示可恢復）")

    def _show_window(self) -> None:
        """從系統匣選單「顯示主畫面」。"""
        self.deiconify()
        self.lift()
        self.focus_force()

    def _quit_app(self) -> None:
        """從系統匣選單「結束程式」→ 走確認流程。"""
        self._show_window()  # 先恢復畫面才彈 prompt
        self._confirm_quit()

    # ── Close / Logout ───────────────────────────────────────
    def destroy(self) -> None:
        self._log_msg("LOGOUT 程式關閉")
        if self._reconnect_id is not None:
            self.after_cancel(self._reconnect_id)
            self._reconnect_id = None
        self._stop_sync_timer()
        if self._auto_print_id is not None:
            self.after_cancel(self._auto_print_id)
            self._auto_print_id = None
        if hasattr(self, "_http_server"):
            self._http_server.shutdown()
        if hasattr(self, "_tray"):
            self._tray.stop()
        if hasattr(self, "local_db"):
            self.local_db.close()
        super().destroy()

    # ── Auth Splash ──────────────────────────────────────────
    def _show_auth_splash(self) -> None:
        """顯示認證中提示畫面。"""
        self._splash = tk.Frame(self, bg=CLR_BG)
        self._splash.place(relx=0, rely=0, relwidth=1, relheight=1)
        tk.Label(self._splash, text="正在檢查主系統連線 ...",
                 font=("標楷體", 20, "bold"), bg=CLR_BG, fg=CLR_TITLE_FG).place(
                     relx=0.5, rely=0.4, anchor="center")
        tk.Label(self._splash, text="健康檢查中",
                 font=("新細明體", 11), bg=CLR_BG, fg=CLR_ACCENT).place(
                     relx=0.5, rely=0.5, anchor="center")
        self.update()

    def _remove_auth_splash(self) -> None:
        """移除認證提示畫面。"""
        if hasattr(self, "_splash"):
            self._splash.destroy()
            del self._splash

    # ── Menu ─────────────────────────────────────────────────
    def _build_menu(self) -> None:
        menubar = tk.Menu(self)
        menu_setting = tk.Menu(menubar, tearoff=0)
        menu_setting.add_command(label="標籤印表機設定",
                                command=self._open_printer_setting)
        menubar.add_cascade(label="設定", menu=menu_setting)
        menubar.add_command(label="標籤測試頁", command=self._open_sample_data_print)
        self.config(menu=menubar)

    # ── UI ───────────────────────────────────────────────────
    def _build_ui(self) -> None:
        # ====== Row 0: 標題列 ======
        top = tk.Frame(self, bg=CLR_BG)
        top.pack(fill="x", padx=6, pady=(6, 0))

        tk.Label(top, text="LBSB01-標籤服務程式", font=("標楷體", 18, "bold"),
                 bg=CLR_BG, fg=CLR_TITLE_FG).pack(side="left")

        # 線上/離線狀態指示
        if self.session.online:
            status_text, status_fg, status_bg = "● 線上", "#FFFFFF", "#27AE60"
        else:
            status_text, status_fg, status_bg = "● 離線", "#FFFFFF", "#CC0000"
        self.lbl_status = tk.Label(top, text=f"  {status_text}  ",
                                   font=("新細明體", 11, "bold"),
                                   fg=status_fg, bg=status_bg, relief="ridge", padx=6)
        self.lbl_status.pack(side="left", padx=(12, 0))

        # 連線方式由所選印表機決定，不在此選擇（預設值供其他視窗共用）
        self.var_link = tk.StringVar(value="USB")

        self.var_auto = tk.IntVar(value=0)
        self.var_auto.trace_add("write", self._on_auto_toggle)
        tk.Checkbutton(top, text="Auto自動依序列印", variable=self.var_auto,
                       bg=CLR_BG, fg=CLR_TITLE_FG, selectcolor=CLR_BG,
                       font=("新細明體", 12)).pack(side="left", padx=(10, 0))

        self.lbl_time = tk.Label(top, text="", font=("新細明體", 12),
                                 bg=CLR_BG, fg=CLR_TITLE_FG, anchor="e")
        self.lbl_time.pack(side="right")
        self._update_clock()

        # ====== Row 1: 左=線上明細 + 右=線上排隊 ======
        row1 = tk.Frame(self, bg=CLR_BG)
        row1.pack(fill="both", expand=True, padx=6, pady=4)

        # --- 左: 線上列印項目明細 ---
        frm_detail = tk.LabelFrame(row1, text="線上列印項目明細",
                                   font=("標楷體", 12, "bold"),
                                   fg=CLR_ONLINE_FG, bg=CLR_ONLINE_BG, padx=8, pady=4)
        frm_detail.pack(side="left", fill="y", padx=(0, 4))

        fields = [
            ("時間序:", "var_sn", 30, True),
            ("條碼種類:", "var_type", 8, True),
            ("列印者:", "var_user", 15, False),
            ("印表機編號:", "var_printer_no", 10, False),
        ]
        self.lbl_sname = None  # 條碼種類旁的中文名 label，於 var_type row 內建立
        for i, (lbl_text, var_name, width, disabled) in enumerate(fields):
            tk.Label(frm_detail, text=lbl_text, bg=CLR_ONLINE_BG, fg=CLR_ONLINE_FG,
                     font=("新細明體", 9)).grid(row=i, column=0, sticky="e", padx=(0, 4), pady=2)
            sv = tk.StringVar()
            setattr(self, var_name, sv)
            state = "disabled" if disabled else "normal"

            if var_name == "var_type":
                # 條碼種類：Entry + 中文名 Label 合併在 column 1（避免中文名撐寬欄位）
                sub = tk.Frame(frm_detail, bg=CLR_ONLINE_BG)
                sub.grid(row=i, column=1, sticky="w", pady=2)
                tk.Entry(sub, textvariable=sv, width=width, state=state,
                         font=("新細明體", 9)).pack(side="left")
                self.lbl_sname = tk.Label(sub, text="", bg=CLR_ONLINE_BG, fg=CLR_ACCENT,
                                          font=("標楷體", 11, "bold"))
                self.lbl_sname.pack(side="left", padx=(4, 0))
            else:
                tk.Entry(frm_detail, textvariable=sv, width=width, state=state,
                         font=("新細明體", 9)).grid(row=i, column=1, sticky="w", pady=2)

        r = len(fields)
        tk.Label(frm_detail, text="指定印表機:", bg=CLR_ONLINE_BG, fg=CLR_ONLINE_FG,
                 font=("新細明體", 10)).grid(row=r, column=0, sticky="e", padx=(0, 4), pady=4)
        sub_p = tk.Frame(frm_detail, bg=CLR_ONLINE_BG)
        sub_p.grid(row=r, column=1, columnspan=2, sticky="w", pady=4)
        self.var_printer = tk.StringVar()
        self.cmb_printer = ttk.Combobox(sub_p, textvariable=self.var_printer,
                                        width=22, font=("新細明體", 11), state="readonly")
        self.cmb_printer.pack(side="left")
        tk.Button(sub_p, text="存檔", font=("新細明體", 9), bg=CLR_BTN_BG, fg=CLR_BTN_FG,
                  command=lambda: self._override_printer(online=True)).pack(side="left", padx=(4, 0))

        # --- 右: 線上排隊列印項目 (Online Queue) ---
        frm_queue = tk.LabelFrame(row1, text="線上排隊列印項目 (Online Queue)",
                                  font=("標楷體", 12, "bold"),
                                  fg=CLR_ONLINE_FG, bg=CLR_ONLINE_BG, padx=8, pady=4)
        frm_queue.pack(side="left", fill="both", expand=True)

        btn_row = tk.Frame(frm_queue, bg=CLR_ONLINE_BG)
        btn_row.pack(fill="x")
        tk.Label(btn_row, text="點二下可將線上項目移至下面離線",
                 fg=CLR_ACCENT, bg=CLR_ONLINE_BG, font=("新細明體", 8)).pack(side="left")
        tk.Button(btn_row, text="刪除單筆", font=("新細明體", 9),
                  command=lambda: self._on_delete_queue(online=True)).pack(side="right", padx=2)
        # 「更新資料」已移除：Queue 異動時自動刷新畫面

        self.lst_queue = tk.Listbox(frm_queue, font=("新細明體", 12), height=6)
        self.lst_queue.pack(fill="both", expand=True, pady=(4, 0))
        self.lst_queue.bind("<<ListboxSelect>>", self._on_online_select)
        self.lst_queue.bind("<Double-Button-1>", self._on_online_dblclick)

        self.btn_print_online = tk.Button(
            frm_queue, text="  列印線上指定項目  ",
            font=("標楷體", 18, "bold"), bg=CLR_PRINT_BG, fg=CLR_PRINT_FG,
            activebackground="#A04000", activeforeground="white",
            command=self._on_print)
        self.btn_print_online.pack(fill="x", pady=(4, 0), ipady=4)

        # ====== Row 2: 紙張輸出規格 ======
        frm_paper = tk.LabelFrame(self, text="紙張輸出規格(資料來自印表機設定檔,可手調固定)",
                                  font=("標楷體", 10), fg=CLR_ACCENT, bg=CLR_BG, padx=8, pady=4)
        frm_paper.pack(fill="x", padx=6, pady=(0, 4))

        paper_inner = tk.Frame(frm_paper, bg=CLR_BG)
        paper_inner.pack(fill="x")

        tk.Label(paper_inner, text="標籤:", bg=CLR_BG, fg=CLR_TITLE_FG,
                 font=("新細明體", 10)).pack(side="left")
        self.var_label = tk.StringVar()
        self.cmb_label = ttk.Combobox(paper_inner, textvariable=self.var_label,
                                      state="readonly", width=30, font=("新細明體", 10))
        self.cmb_label["values"] = [d.display for d in LABEL_DEFS]
        self.cmb_label.current(0)
        self.cmb_label.pack(side="left", padx=(2, 8))
        self.cmb_label.bind("<<ComboboxSelected>>", self._on_label_changed)

        tk.Label(paper_inner, text="尺寸:", bg=CLR_BG, fg=CLR_TITLE_FG,
                 font=("新細明體", 10)).pack(side="left")
        self.var_size = tk.StringVar()
        self.cmb_size = ttk.Combobox(paper_inner, textvariable=self.var_size,
                                     state="readonly", width=14, font=("新細明體", 10))
        self.cmb_size["values"] = [f"{w}mm x {h}mm" for w, h in PAPER_SIZES]
        self.cmb_size.pack(side="left", padx=(2, 8))
        self.cmb_size.bind("<<ComboboxSelected>>", self._on_size_changed)

        tk.Label(paper_inner, text="寬", bg=CLR_BG, fg=CLR_TITLE_FG,
                 font=("新細明體", 10)).pack(side="left")
        self.var_w = tk.StringVar(value="80")
        tk.Entry(paper_inner, textvariable=self.var_w, width=5, font=("新細明體", 10)).pack(side="left")
        tk.Label(paper_inner, text="高", bg=CLR_BG, fg=CLR_TITLE_FG,
                 font=("新細明體", 10)).pack(side="left", padx=(4, 0))
        self.var_h = tk.StringVar(value="35")
        tk.Entry(paper_inner, textvariable=self.var_h, width=5, font=("新細明體", 10)).pack(side="left")

        tk.Label(paper_inner, text="左位移", bg=CLR_BG, fg=CLR_TITLE_FG,
                 font=("新細明體", 10)).pack(side="left", padx=(8, 0))
        self.var_shift_l = tk.StringVar(value="0")
        tk.Entry(paper_inner, textvariable=self.var_shift_l, width=4, font=("新細明體", 10)).pack(side="left")
        tk.Label(paper_inner, text="上位移", bg=CLR_BG, fg=CLR_TITLE_FG,
                 font=("新細明體", 10)).pack(side="left", padx=(4, 0))
        self.var_shift_t = tk.StringVar(value="0")
        tk.Entry(paper_inner, textvariable=self.var_shift_t, width=4, font=("新細明體", 10)).pack(side="left")

        tk.Label(paper_inner, text="明暗", bg=CLR_BG, fg=CLR_TITLE_FG,
                 font=("新細明體", 10)).pack(side="left", padx=(8, 0))
        self.var_dark = tk.StringVar(value="12")
        tk.Entry(paper_inner, textvariable=self.var_dark, width=3, font=("新細明體", 10)).pack(side="left")

        self.var_fix_size = tk.IntVar(value=0)
        tk.Checkbutton(paper_inner, text="固定參數", variable=self.var_fix_size,
                       bg=CLR_BG, fg="#CC0000", selectcolor=CLR_BG,
                       font=("新細明體", 10, "bold")).pack(side="left", padx=(8, 0))

        # ====== Row 3: 左=離線明細 + 右=離線等待重印 ======
        row3 = tk.Frame(self, bg=CLR_BG)
        row3.pack(fill="both", expand=True, padx=6, pady=(0, 4))

        # --- 左: 離線列印項目明細（結構同線上明細，對應右側 Offline Queue）---
        frm_offline = tk.LabelFrame(row3, text="離線列印項目明細", font=("標楷體", 12, "bold"),
                                    fg=CLR_OFFLINE_FG, bg=CLR_OFFLINE_BG, padx=8, pady=4)
        frm_offline.pack(side="left", fill="y", padx=(0, 4))

        off_fields = [
            ("時間序:", "off_var_sn", 30, True),
            ("條碼種類:", "off_var_type", 8, True),
            ("列印者:", "off_var_user", 15, False),
            ("印表機編號:", "off_var_printer_no", 10, False),
        ]
        self.off_lbl_sname = None
        for i, (lbl_text, var_name, width, disabled) in enumerate(off_fields):
            tk.Label(frm_offline, text=lbl_text, bg=CLR_OFFLINE_BG, fg=CLR_OFFLINE_FG,
                     font=("新細明體", 9)).grid(row=i, column=0, sticky="e", padx=(0, 4), pady=2)
            sv = tk.StringVar()
            setattr(self, var_name, sv)
            state = "disabled" if disabled else "normal"

            if var_name == "off_var_type":
                sub = tk.Frame(frm_offline, bg=CLR_OFFLINE_BG)
                sub.grid(row=i, column=1, sticky="w", pady=2)
                tk.Entry(sub, textvariable=sv, width=width, state=state,
                         font=("新細明體", 9)).pack(side="left")
                self.off_lbl_sname = tk.Label(sub, text="", bg=CLR_OFFLINE_BG, fg="#FFD700",
                                              font=("標楷體", 11, "bold"))
                self.off_lbl_sname.pack(side="left", padx=(4, 0))
            else:
                tk.Entry(frm_offline, textvariable=sv, width=width, state=state,
                         font=("新細明體", 9)).grid(row=i, column=1, sticky="w", pady=2)

        r2 = len(off_fields)
        tk.Label(frm_offline, text="變更待印印表機:", bg=CLR_OFFLINE_BG, fg="#FFD700",
                 font=("新細明體", 10)).grid(row=r2, column=0, sticky="e", padx=(0, 4), pady=4)
        sub_op = tk.Frame(frm_offline, bg=CLR_OFFLINE_BG)
        sub_op.grid(row=r2, column=1, columnspan=2, sticky="w", pady=4)
        self.off_var_printer = tk.StringVar()
        self.off_cmb_printer = ttk.Combobox(sub_op, textvariable=self.off_var_printer,
                                            width=22, font=("新細明體", 11), state="readonly")
        self.off_cmb_printer.pack(side="left")
        tk.Button(sub_op, text="存檔", font=("新細明體", 9), bg=CLR_BTN_BG, fg=CLR_BTN_FG,
                  command=lambda: self._override_printer(online=False)).pack(side="left", padx=(4, 0))

        # --- 右: 離線等待重印項目 (Offline Queue) ---
        frm_wait = tk.LabelFrame(row3, text="離線等待重印項目 (Offline Queue)",
                                 font=("標楷體", 12),
                                 fg=CLR_OFFLINE_FG, bg=CLR_OFFLINE_BG, padx=8, pady=4)
        frm_wait.pack(side="left", fill="both", expand=True)

        btn_row2 = tk.Frame(frm_wait, bg=CLR_OFFLINE_BG)
        btn_row2.pack(fill="x")
        tk.Label(btn_row2, text="點二下可將離線項目移至上面進行上線排隊列印",
                 fg="#FFD700", bg=CLR_OFFLINE_BG, font=("新細明體", 8)).pack(side="left")
        tk.Button(btn_row2, text="刪除單筆", font=("新細明體", 9),
                  command=lambda: self._on_delete_queue(online=False)).pack(side="right", padx=2)
        # 「更新資料」已移除：Queue 異動時自動刷新畫面

        self.lst_wait = tk.Listbox(frm_wait, font=("新細明體", 12), height=5)
        self.lst_wait.pack(fill="both", expand=True, pady=(4, 0))
        self.lst_wait.bind("<<ListboxSelect>>", self._on_offline_select)
        self.lst_wait.bind("<Double-Button-1>", self._on_offline_dblclick)

        # ====== Row 4: 訊息 + 測試列印 ======
        row4 = tk.Frame(self, bg=CLR_BG)
        row4.pack(fill="x", padx=6, pady=(0, 4))

        frm_msg = tk.LabelFrame(row4, text="訊息", font=("新細明體", 9), bg=CLR_BG)
        frm_msg.pack(side="left", fill="both", expand=True, padx=(0, 4))
        self.lst_msg = tk.Listbox(frm_msg, font=("新細明體", 9), height=3)
        self.lst_msg.pack(fill="both", expand=True)

        frm_test = tk.LabelFrame(row4, text="列印測試資料", font=("標楷體", 10),
                                 fg=CLR_OFFLINE_FG, bg=CLR_OFFLINE_BG, padx=4, pady=4)
        frm_test.pack(side="left", fill="y")
        self.var_test_text = tk.StringVar(
            value=r"\F40;測試標籤列印資料本頁此列\n第二列,加\F##;可設定字型大小\n第三列測試頁- *****測試頁***\n第四列測試頁- *****測試頁***")
        tk.Entry(frm_test, textvariable=self.var_test_text, width=50,
                 font=("新細明體", 9)).pack(side="left", padx=(0, 4))
        tk.Button(frm_test, text="列印測試資料", font=("新細明體", 9),
                  command=self._on_test_print).pack(side="left")

        # IP/Port 由所選印表機決定（預設值供其他視窗共用）
        self.var_ip = tk.StringVar(value="192.168.1.100")
        self.var_port = tk.StringVar(value="9100")

        # 初始化
        self._on_label_changed(None)

    # ── Clock ────────────────────────────────────────────────
    def _update_clock(self) -> None:
        self.lbl_time.config(text=time.strftime("%Y/%m/%d %H:%M:%S"))
        self.after(1000, self._update_clock)

    # ── Events ───────────────────────────────────────────────
    def _on_label_changed(self, _event) -> None:
        ld = self._get_label_def()
        if not ld:
            return
        if not self.var_fix_size.get():
            size_str = ld.size_display
            if size_str in self.cmb_size["values"]:
                self.cmb_size.set(size_str)
            self.var_w.set(str(ld.width_mm))
            self.var_h.set(str(ld.height_mm))
        self.var_type.set(ld.code)
        self.lbl_sname.config(text=ld.name)

    def _on_size_changed(self, _event) -> None:
        parts = self.var_size.get().replace("mm", "").split("x")
        if len(parts) == 2:
            self.var_w.set(parts[0].strip())
            self.var_h.set(parts[1].strip())

    # ── Helpers ──────────────────────────────────────────────
    def _get_label_def(self) -> LabelDef | None:
        display = self.var_label.get()
        code = display.split("-")[0] if "-" in display else display
        return LABEL_MAP.get(code)

    def _get_paper_size(self) -> tuple[int, int]:
        try:
            w = int(self.var_w.get().strip())
            h = int(self.var_h.get().strip())
        except ValueError:
            raise ValueError("紙張寬/高必須為數字")
        if w <= 0 or h <= 0:
            raise ValueError("紙張寬/高必須大於 0")
        return w, h

    def _add_msg(self, text: str) -> None:
        """純 UI 訊息（不寫 log）。"""
        self.lst_msg.insert(0, f"[{time.strftime('%H:%M:%S')}] {text}")
        if self.lst_msg.size() > 100:
            self.lst_msg.delete(100, "end")

    def _log_msg(self, text: str) -> None:
        """系統訊息：同時寫 Log + 訊息區。"""
        log.info(text)
        if hasattr(self, "lst_msg"):
            self._add_msg(text)

    # ── 取得目前選取的 Queue 項目 UUID ─────────────────────────
    def _get_selected_queue_uuid(self, online: bool) -> str | None:
        """取得目前 Online/Offline Queue 選取項目的 UUID；未選取回傳 None。"""
        listbox = self.lst_queue if online else self.lst_wait
        queue_list = (self.local_db.list_online_queue() if online
                      else self.local_db.list_offline_queue())
        sel = listbox.curselection()
        if not sel or sel[0] >= len(queue_list):
            return None
        return queue_list[sel[0]].get("UUID", "")

    # ── 取得列印參數（shift / darkness）──────────────────────
    def _get_print_params(self) -> tuple[int, int, int]:
        """回傳 (shift_left, shift_top, darkness)。"""
        try:
            shift_l = int(self.var_shift_l.get().strip() or "0")
        except ValueError:
            shift_l = 0
        try:
            shift_t = int(self.var_shift_t.get().strip() or "0")
        except ValueError:
            shift_t = 0
        try:
            darkness = int(self.var_dark.get().strip() or "12")
        except ValueError:
            darkness = 12
        return shift_l, shift_t, darkness

    # ── 取得印表機連線資訊 ───────────────────────────────────
    def _get_printer_connection(self, printer_id: str) -> tuple[LinkType, str, int]:
        """依 printer_id 查 Local Cache 取得連線方式。"""
        p = self.local_db.get_printer(printer_id)
        if p and (p.get("PRINTER_IP") or "").strip():
            return LinkType.TCP, p["PRINTER_IP"].strip(), 9100
        driver = (p.get("PRINTER_DRIVER") or "").strip() if p else ""
        if driver and driver.upper() != "USB":
            return LinkType.BT, driver, 9100
        return LinkType.USB, driver, 9100

    # ── Actions ──────────────────────────────────────────────
    def _on_print(self) -> None:
        """列印線上指定項目：取 Queue 選取項目 → GoDEX 列印 → 更新 Status + RESULT。"""
        # 必須先選取 Online Queue 項目
        uuid = self._get_selected_queue_uuid(online=True)
        if not uuid:
            messagebox.showwarning("列印", "請先在 Online Queue 選取一筆列印項目")
            return

        # 取完整 Task 資料
        row = self.local_db._conn.execute(
            "SELECT * FROM LB_PRINT_LOG_CACHE WHERE UUID=?", (uuid,)
        ).fetchone()
        if not row:
            messagebox.showwarning("列印", "找不到該筆列印資料")
            return
        row = dict(row)
        bar_type = row.get("BAR_TYPE", "")
        printer_id = row.get("PRINTER_ID", "")

        # 從 LABEL_MAP 取標籤定義
        label_def = LABEL_MAP.get(bar_type)
        if not label_def:
            messagebox.showwarning("列印", f"不支援的標籤類型: {bar_type}")
            return

        shift_l, shift_t, darkness = self._get_print_params()

        if self.var_fix_size.get():
            try:
                paper_w, paper_h = self._get_paper_size()
            except ValueError as e:
                messagebox.showwarning("輸入錯誤", str(e))
                return
        else:
            paper_w, paper_h = label_def.width_mm, label_def.height_mm

        # 組裝列印資料
        data = LabelData(
            label_type=bar_type,
            bag_no=row.get("SPECIMEN_NO", ""),
            data_1=row.get("DATA_1", ""), data_2=row.get("DATA_2", ""),
            data_3=row.get("DATA_3", ""), data_4=row.get("DATA_4", ""),
            data_5=row.get("DATA_5", ""), data_6=row.get("DATA_6", ""),
            data_7=row.get("DATA_7", ""), data_8=row.get("DATA_8", ""),
            data_9=row.get("DATA_9", ""), data_10=row.get("DATA_10", ""),
            data_11=row.get("DATA_11", ""), data_12=row.get("DATA_12", ""),
            data_13=row.get("DATA_13", ""), data_14=row.get("DATA_14", ""),
            data_15=row.get("DATA_15", ""), data_16=row.get("DATA_16", ""),
            data_17=row.get("DATA_17", ""), data_18=row.get("DATA_18", ""),
            data_19=row.get("DATA_19", ""),
        )

        # 取得印表機連線方式
        link, ip, tcp_port = self._get_printer_connection(printer_id)

        self._add_msg(f"列印 {bar_type} @ {printer_id} ({paper_w}x{paper_h}mm)")

        try:
            with GodexPrinter(link) as printer:
                printer.open(ip=ip, tcp_port=tcp_port)
                print_label(printer, label_def, data, paper_w, paper_h,
                            shift_l=shift_l, shift_t=shift_t, darkness=darkness)

            # ── 列印成功 → 更新 Status + RESULT ──
            from local_db import build_result
            result_val = build_result(
                fixed=bool(self.var_fix_size.get()),
                width=paper_w, height=paper_h,
                shift_left=shift_l, shift_top=shift_t,
                darkness=darkness,
            )
            self.local_db.delete_queue_task(uuid, online=True)
            self.local_db.update_print_log(uuid, status=1, result=result_val)
            self._refresh_queues()

            mode = "USB" if link == LinkType.USB else f"TCP {ip}:{tcp_port}"
            self._log_msg(f"列印完成: {bar_type} @ {printer_id}（{mode}）RESULT={result_val}")

        except FileNotFoundError as e:
            messagebox.showerror("DLL 錯誤", str(e))
        except ConnectionError as e:
            messagebox.showerror("連線失敗", str(e))
        except Exception as e:
            log.error("列印失敗:\n%s", traceback.format_exc())
            messagebox.showerror("列印失敗", f"{e}\n\n詳見 app.log")

    def _open_printer_setting(self) -> None:
        """Menu → 設定 → 標籤印表機設定。關閉後重新載入印表機下拉。"""
        ps = PrinterSetting(self)
        self.wait_window(ps)
        self._load_printer_combos()

    def _open_sample_data_print(self) -> None:
        """Menu → 標籤測試頁。"""
        SampleDataPrint(self)

    def _on_test_print(self) -> None:
        """列印測試資料 — 移植 VB6 PrintTest + Bar_ANY 邏輯。

        文字格式：可選 \\F##; 前綴設定字型大小，\\n 換行。
        範例：\\F45;第一列\\n第二列
        """
        raw = self.var_test_text.get().strip()
        if not raw:
            messagebox.showwarning("測試列印", "請輸入測試文字")
            return

        # 解析 \F##; 前綴取得字型大小（預設 60）
        font_h = 60
        text = raw
        if text.startswith("\\F"):
            sep = text.find(";")
            if sep > 2:
                try:
                    font_h = int(text[2:sep])
                except ValueError:
                    pass
                text = text[sep + 1:]

        lines = text.split("\\n")

        try:
            paper_w, paper_h = self._get_paper_size()
        except ValueError as e:
            messagebox.showwarning("輸入錯誤", str(e))
            return

        ld = self._get_label_def()
        gap = ld.gap if ld else 3
        link = LinkType.USB if self.var_link.get() == "USB" else LinkType.TCP
        ip = self.var_ip.get().strip()
        try:
            tcp_port = int(self.var_port.get().strip())
        except ValueError:
            tcp_port = 9100

        try:
            shift_l = int(self.var_shift_l.get().strip() or "0")
        except ValueError:
            shift_l = 0
        try:
            shift_t = int(self.var_shift_t.get().strip() or "0")
        except ValueError:
            shift_t = 0
        try:
            darkness = int(self.var_dark.get().strip() or "12")
        except ValueError:
            darkness = 12

        self._add_msg(f"測試列印 FontH={font_h} 共{len(lines)}行")

        try:
            with GodexPrinter(link) as printer:
                printer.open(ip=ip, tcp_port=tcp_port)
                printer.label_setup(paper_w, paper_h, gap, darkness=darkness, speed=2)
                printer.job_start()

                bx = 5 + shift_l
                by = 5 + shift_t
                for line in lines:
                    printer.text_out(bx, by, font_h, "標楷體", line)
                    self._add_msg(line)
                    by += font_h

                printer.job_end()

            mode = "USB" if link == LinkType.USB else f"TCP {ip}:{tcp_port}"
            self._add_msg(f"測試列印完成（{mode}）")

        except FileNotFoundError as e:
            messagebox.showerror("DLL 錯誤", str(e))
        except ConnectionError as e:
            messagebox.showerror("連線失敗", str(e))
        except Exception as e:
            log.error("測試列印失敗:\n%s", traceback.format_exc())
            messagebox.showerror("測試列印失敗", f"{e}\n\n詳見 app.log")


def _ensure_single_instance() -> None:
    """用持久 socket bind 確保只有一個 LBSB01 在跑；已存在則靜默退出。

    socket 綁 127.0.0.1:9201（不是 9200，避免與 Task Listener 衝突）。
    設 SO_EXCLUSIVEADDRUSE 防止其他 process 重複 bind。
    socket 不關閉，process 結束時 OS 自動回收。
    """
    import socket as _sk
    import sys as _sys

    s = _sk.socket(_sk.AF_INET, _sk.SOCK_STREAM)
    try:
        s.setsockopt(_sk.SOL_SOCKET, _sk.SO_EXCLUSIVEADDRUSE, 1)  # type: ignore[attr-defined]
    except (AttributeError, OSError):
        pass  # 非 Windows 或不支援
    try:
        s.bind(("127.0.0.1", 9201))
        # 不關閉 socket → 持續佔用直到 process 結束
        # 存到 module 層級避免被 GC 回收
        global _instance_lock_socket  # noqa: PLW0603
        _instance_lock_socket = s
        log.info("單一實例檢查通過（port 9201 bind 成功）")
    except OSError:
        log.info("偵測到另一支 LBSB01 正在執行，本次啟動中止")
        _sys.exit(0)


_instance_lock_socket = None  # module-level reference, prevent GC


if __name__ == "__main__":
    _ensure_single_instance()
    App().mainloop()
