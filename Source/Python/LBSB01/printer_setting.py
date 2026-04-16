"""
PrinterSetting — 標籤印表機設定。

由 Main Menu「設定→標籤印表機設定」開啟。
對照 VB6 Frm_Set_Printer.frm，改用藍色色系。

欄位模型對齊 spec.md LB_PRINTER Table 定義：
  PRINTER_ID, PRINTER_NAME, SITE_ID, SERVER_IP,
  PRINTER_IP, PRINTER_PORT, PRINTER_DRIVER,
  SHIFT_LEFT, SHIFT_TOP, DARKNESS,
  PRINTER_MODEL, IS_ACTIVE, NOTE
"""

from __future__ import annotations
import logging
import socket
import tkinter as tk
from tkinter import ttk, messagebox

log = logging.getLogger(__name__)


def _get_host_ip() -> str:
    """取得本機 IP（優先 UDP trick 取得對外網卡 IP；失敗回 gethostbyname）。"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
        finally:
            s.close()
    except OSError:
        try:
            return socket.gethostbyname(socket.gethostname())
        except OSError:
            return "127.0.0.1"

# ── 藍色色系（與 main.py 一致）──
CLR_BG = "#D6E4F0"
CLR_HEADER_BG = "#2E86C1"
CLR_HEADER_FG = "#FFFFFF"
CLR_TITLE_FG = "#003366"
CLR_ACCENT = "#1A5276"
CLR_ROW_ODD = "#EAF2F8"
CLR_ROW_EVEN = "#D4E6F1"
CLR_SELECT_BG = "#5DADE2"
CLR_BTN_BG = "#2E86C1"
CLR_BTN_FG = "#FFFFFF"
CLR_WARN = "#CC0000"

# ── 印表機型號選項 ──
PRINTER_MODELS = [
    "GoDEX G500（桌上型）",
    "GoDEX G530（桌上型）",
]


class PrinterSetting(tk.Toplevel):
    """標籤印表機設定視窗。"""

    def __init__(self, master: tk.Tk) -> None:
        super().__init__(master)
        self.title("LBSB01-標籤印表機設定")
        self.geometry("1100x680")
        self.resizable(True, True)
        self.configure(bg=CLR_BG)

        # 子視窗 On-Top 且為 Modal：使用者必須關閉本窗才能操作主畫面
        self.transient(master)
        self.grab_set()

        # 登入 session（由 master=App 提供）；無 session 則以 S01 為 fallback 供獨立測試
        self._session = getattr(master, "session", None)
        self._site_id = self._session.site_id if self._session else "S01"
        self._site_name = self._session.site_name if self._session else "S01"
        self.title(f"LBSB01-標籤印表機設定  [站點 {self._site_id}-{self._site_name}]")

        self._selected_idx: int | None = None
        self._is_new: bool = False

        # 從 master (App) 取得 local_db；無則獨立啟動測試用
        self._local_db = getattr(master, "local_db", None)
        if self._local_db is None:
            from local_db import LocalDB
            self._local_db = LocalDB()

        # 從 Local Cache 載入印表機清單
        self._printers: list[dict] = self._load_printers()

        self._build_ui()
        self._refresh_grid()

    def _load_printers(self) -> list[dict]:
        """從 local_db 讀取該站點印表機清單，統一小寫 key（UI 用）。"""
        rows = self._local_db.list_printers(self._site_id)
        return [self._to_lower_keys(r) for r in rows]

    @staticmethod
    def _to_lower_keys(row: dict) -> dict:
        """local_db 回傳 UPPER_CASE，UI 內部用 lower_case。"""
        mapping = {
            "PRINTER_ID": "printer_id",
            "PRINTER_NAME": "printer_name",
            "SITE_ID": "site_id",
            "SERVER_IP": "server_ip",
            "PRINTER_IP": "printer_ip",
            "PRINTER_DRIVER": "printer_driver",
            "SHIFT_LEFT": "shift_left",
            "SHIFT_TOP": "shift_top",
            "DARKNESS": "darkness",
            "PRINTER_MODEL": "printer_model",
            "IS_ACTIVE": "is_active",
            "NOTE": "note",
        }
        return {mapping.get(k, k): v for k, v in row.items() if k in mapping}

    # ── UI ───────────────────────────────────────────────────

    def _build_ui(self) -> None:
        # ====== 標題列 + 按鈕 ======
        top = tk.Frame(self, bg=CLR_BG)
        top.pack(fill="x", padx=8, pady=(8, 4))

        tk.Button(top, text="重新整理", font=("新細明體", 11), bg=CLR_BTN_BG, fg=CLR_BTN_FG,
                  command=self._on_refresh).pack(side="left", padx=(0, 8))
        tk.Button(top, text="列印印表機識別貼紙", font=("新細明體", 10), bg=CLR_BTN_BG, fg=CLR_BTN_FG,
                  command=self._on_print_id_label).pack(side="left", padx=(0, 8))
        tk.Button(top, text="  新 增  ", font=("新細明體", 11), bg="#27AE60", fg="white",
                  command=self._on_add).pack(side="left", padx=(0, 8))
        tk.Button(top, text="  刪 除  ", font=("新細明體", 11), bg=CLR_WARN, fg="white",
                  command=self._on_delete).pack(side="left", padx=(0, 8))

        # ====== 印表機清單（Treeview）======
        grid_frame = tk.Frame(self, bg=CLR_BG)
        grid_frame.pack(fill="both", expand=True, padx=8, pady=4)

        columns = ("printer_id", "printer_name", "server_ip",
                   "printer_driver", "printer_ip",
                   "shift_left", "shift_top", "darkness",
                   "printer_model", "is_active", "note")
        col_names = ("印表機編號", "名稱", "Server IP",
                     "Driver", "印表機 IP",
                     "左位移", "上位移", "明暗",
                     "型號", "啟用", "說明")
        col_widths = (90, 140, 120,
                      130, 120,
                      55, 55, 45,
                      150, 40, 150)

        self.tree = ttk.Treeview(grid_frame, columns=columns, show="headings",
                                 selectmode="browse", height=15)
        for col, name, w in zip(columns, col_names, col_widths):
            self.tree.heading(col, text=name)
            self.tree.column(col, width=w, minwidth=30)

        vsb = ttk.Scrollbar(grid_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(grid_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        grid_frame.columnconfigure(0, weight=1)
        grid_frame.rowconfigure(0, weight=1)

        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)

        # ── 交替行色 ──
        self.tree.tag_configure("odd", background=CLR_ROW_ODD)
        self.tree.tag_configure("even", background=CLR_ROW_EVEN)

        # ====== 編輯區（下方）======
        edit_frame = tk.LabelFrame(self, text="印表機設定", font=("標楷體", 12, "bold"),
                                   fg=CLR_TITLE_FG, bg=CLR_BG, padx=10, pady=8)
        edit_frame.pack(fill="x", padx=8, pady=(0, 8))

        # Row 0: 編號 / 名稱 / 型號
        r = 0
        tk.Label(edit_frame, text="印表機編號:", bg=CLR_BG, fg=CLR_TITLE_FG,
                 font=("新細明體", 11)).grid(row=r, column=0, sticky="e", padx=(0, 4))
        self.var_id = tk.StringVar()
        self.ent_id = tk.Entry(edit_frame, textvariable=self.var_id, width=15,
                               font=("新細明體", 11), state="disabled")
        self.ent_id.grid(row=r, column=1, sticky="w", pady=3)

        tk.Label(edit_frame, text="名稱:", bg=CLR_BG, fg=CLR_TITLE_FG,
                 font=("新細明體", 11)).grid(row=r, column=2, sticky="e", padx=(16, 4))
        self.var_name = tk.StringVar()
        tk.Entry(edit_frame, textvariable=self.var_name, width=20,
                 font=("新細明體", 11)).grid(row=r, column=3, sticky="w", pady=3)

        tk.Label(edit_frame, text="型號:", bg=CLR_BG, fg=CLR_TITLE_FG,
                 font=("新細明體", 11)).grid(row=r, column=4, sticky="e", padx=(16, 4))
        self.var_model = tk.StringVar()
        cmb_model = ttk.Combobox(edit_frame, textvariable=self.var_model, width=25,
                                 font=("新細明體", 10), values=PRINTER_MODELS)
        cmb_model.grid(row=r, column=5, sticky="w", pady=3)

        # Row 1: Server IP（站點由 session 自動帶入，不顯示於畫面）
        r = 1
        self.var_site = tk.StringVar()  # 保留 var，由 session.site_id 自動填入

        tk.Label(edit_frame, text="Server IP:", bg=CLR_BG, fg=CLR_TITLE_FG,
                 font=("新細明體", 11)).grid(row=r, column=0, sticky="e", padx=(0, 4))
        self.var_server_ip = tk.StringVar()
        tk.Entry(edit_frame, textvariable=self.var_server_ip, width=16,
                 font=("新細明體", 11)).grid(row=r, column=1, sticky="w", pady=3)

        # Row 2: Driver / 印表機 IP （互斥：填 Driver 則 IP 留空不可填，反之亦然）
        r = 2
        tk.Label(edit_frame, text="Driver:", bg=CLR_BG, fg=CLR_TITLE_FG,
                 font=("新細明體", 11)).grid(row=r, column=0, sticky="e", padx=(0, 4))
        self.var_driver = tk.StringVar()
        self.ent_driver = tk.Entry(edit_frame, textvariable=self.var_driver,
                                   width=20, font=("新細明體", 11))
        self.ent_driver.grid(row=r, column=1, sticky="w", pady=3)

        tk.Label(edit_frame, text="印表機 IP:", bg=CLR_BG, fg=CLR_TITLE_FG,
                 font=("新細明體", 11)).grid(row=r, column=2, sticky="e", padx=(16, 4))
        self.var_printer_ip = tk.StringVar()
        self.ent_printer_ip = tk.Entry(edit_frame, textvariable=self.var_printer_ip,
                                       width=16, font=("新細明體", 11))
        self.ent_printer_ip.grid(row=r, column=3, sticky="w", pady=3)

        tk.Label(edit_frame, text="USB:填USB，藍芽:填印表機設定的名稱，IP:留空白",
                 fg=CLR_ACCENT, bg=CLR_BG, font=("新細明體", 9)).grid(
                     row=r, column=4, columnspan=2, sticky="w", padx=(16, 0), pady=3)

        # 互斥：IP 有填 → Driver 清空並鎖定；Driver 有填 → IP 清空並鎖定
        self._syncing_excl = False
        self.var_printer_ip.trace_add("write", self._on_ip_driver_change)
        self.var_driver.trace_add("write", self._on_ip_driver_change)

        # Row 3: 公差校正（位移 / 明暗）
        r = 3
        tk.Label(edit_frame, text="左位移(dots):", bg=CLR_BG, fg=CLR_TITLE_FG,
                 font=("新細明體", 11)).grid(row=r, column=0, sticky="e", padx=(0, 4))
        frm_l = tk.Frame(edit_frame, bg=CLR_BG)
        frm_l.grid(row=r, column=1, sticky="w", pady=3)
        self.var_shift_l = tk.StringVar(value="0")
        tk.Entry(frm_l, textvariable=self.var_shift_l, width=6,
                 font=("新細明體", 11)).pack(side="left")
        tk.Label(frm_l, text="  左右微調", fg=CLR_ACCENT, bg=CLR_BG,
                 font=("新細明體", 9)).pack(side="left")

        tk.Label(edit_frame, text="上位移(dots):", bg=CLR_BG, fg=CLR_TITLE_FG,
                 font=("新細明體", 11)).grid(row=r, column=2, sticky="e", padx=(16, 4))
        frm_t = tk.Frame(edit_frame, bg=CLR_BG)
        frm_t.grid(row=r, column=3, sticky="w", pady=3)
        self.var_shift_t = tk.StringVar(value="0")
        tk.Entry(frm_t, textvariable=self.var_shift_t, width=6,
                 font=("新細明體", 11)).pack(side="left")
        tk.Label(frm_t, text="  上下微調", fg=CLR_ACCENT, bg=CLR_BG,
                 font=("新細明體", 9)).pack(side="left")

        tk.Label(edit_frame, text="明暗:", bg=CLR_BG, fg=CLR_TITLE_FG,
                 font=("新細明體", 11)).grid(row=r, column=4, sticky="e", padx=(16, 4))
        frm_d = tk.Frame(edit_frame, bg=CLR_BG)
        frm_d.grid(row=r, column=5, sticky="w", pady=3)
        self.var_dark = tk.StringVar(value="12")
        tk.Entry(frm_d, textvariable=self.var_dark, width=4,
                 font=("新細明體", 11)).pack(side="left")
        tk.Label(frm_d, text="  0=預設12，最大19；小型機 12~14、工業型 6~8",
                 fg=CLR_WARN, bg=CLR_BG, font=("新細明體", 9)).pack(side="left")

        # Row 4: 說明 + 存檔
        r = 4
        tk.Label(edit_frame, text="說明:", bg=CLR_BG, fg=CLR_TITLE_FG,
                 font=("新細明體", 11)).grid(row=r, column=0, sticky="e", padx=(0, 4))
        self.var_note = tk.StringVar()
        tk.Entry(edit_frame, textvariable=self.var_note, width=50,
                 font=("新細明體", 11)).grid(row=r, column=1, columnspan=4, sticky="w", pady=3)

        tk.Button(edit_frame, text="  存  檔  ", font=("新細明體", 14, "bold"),
                  bg=CLR_BTN_BG, fg=CLR_BTN_FG, activebackground="#1A6AA5",
                  command=self._on_save).grid(row=r, column=5, sticky="e", padx=4, pady=3)

    # ── Grid ─────────────────────────────────────────────────

    def _refresh_grid(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)

        for i, p in enumerate(self._printers):
            tag = "odd" if i % 2 == 0 else "even"
            active = "Y" if p.get("is_active", 1) else "N"
            self.tree.insert("", "end", values=(
                p.get("printer_id", ""),
                p.get("printer_name", ""),
                p.get("server_ip", ""),
                p.get("printer_driver", ""),
                p.get("printer_ip", ""),
                p.get("shift_left", 0),
                p.get("shift_top", 0),
                p.get("darkness", 12),
                p.get("printer_model", ""),
                active,
                p.get("note", ""),
            ), tags=(tag,))

    # ── Events ───────────────────────────────────────────────

    def _on_ip_driver_change(self, *_args) -> None:
        """印表機 IP 與 Driver 互斥：一方有值 → 另一方清空並鎖定。"""
        if self._syncing_excl:
            return
        ip = self.var_printer_ip.get().strip()
        drv = self.var_driver.get().strip()

        self._syncing_excl = True
        try:
            if ip:
                if drv:
                    self.var_driver.set("")
                self.ent_driver.configure(state="disabled")
                self.ent_printer_ip.configure(state="normal")
            elif drv:
                if ip:
                    self.var_printer_ip.set("")
                self.ent_printer_ip.configure(state="disabled")
                self.ent_driver.configure(state="normal")
            else:
                self.ent_printer_ip.configure(state="normal")
                self.ent_driver.configure(state="normal")
        finally:
            self._syncing_excl = False

    def _on_tree_select(self, _event) -> None:
        sel = self.tree.selection()
        if not sel:
            return
        values = self.tree.item(sel[0], "values")
        idx = self.tree.index(sel[0])

        # 若正在新增，卻切換到別筆 → 放棄新增，移除空白列
        if self._is_new and self._selected_idx is not None and idx != self._selected_idx:
            blank_idx = self._selected_idx
            if 0 <= blank_idx < len(self._printers) and not self._printers[blank_idx].get("printer_id"):
                self._printers.pop(blank_idx)
                self._is_new = False
                self.ent_id.configure(state="disabled")
                self._refresh_grid()
                # 重新計算目標 idx（被 pop 的列之後的 idx 要 -1）
                if idx > blank_idx:
                    idx -= 1
                self._reselect(idx)
                return

        self._selected_idx = idx

        # columns: printer_id, printer_name, server_ip, printer_driver, printer_ip,
        #          shift_left, shift_top, darkness, printer_model, is_active, note
        self.var_id.set(values[0])
        self.var_name.set(values[1])
        self.var_server_ip.set(values[2])
        self.var_driver.set(values[3])
        self.var_printer_ip.set(values[4])
        self.var_shift_l.set(values[5])
        self.var_shift_t.set(values[6])
        self.var_dark.set(values[7])
        self.var_model.set(values[8])
        self.var_note.set(values[10])
        self.var_site.set(self._site_id)  # 站點由 session 帶入

    def _on_refresh(self) -> None:
        """重新從 local_db 載入印表機清單。"""
        self._printers = self._load_printers()
        self._selected_idx = None
        self._is_new = False
        self.ent_id.configure(state="disabled")
        self._refresh_grid()
        messagebox.showinfo("重新整理", f"已重新載入站點 {self._site_id} 的印表機清單")

    def _on_save(self) -> None:
        if self._selected_idx is None:
            messagebox.showwarning("存檔", "請先選取印表機")
            return

        online = self._session.online if self._session else False

        # 新增模式：寫入 local.db（離線時排 PENDING_OPS）
        if self._is_new:
            pid = self.var_id.get().strip()
            if not pid:
                messagebox.showwarning("存檔", "請輸入印表機編號")
                return
            payload = self._collect_form(pid)
            ok, msg = self._local_db.add_printer(payload, online=online)
            if not ok:
                messagebox.showerror("新增失敗", msg)
                return
            self._printers[self._selected_idx] = payload
            self._is_new = False
            self.ent_id.configure(state="disabled")
            self._refresh_grid()
            self._reselect(self._selected_idx)
            messagebox.showinfo("新增", f"印表機 {pid} 新增成功")
            return

        # 編輯模式：更新 local.db
        p = self._printers[self._selected_idx]
        pid = p["printer_id"]
        payload = self._collect_form(pid)
        ok, msg = self._local_db.save_printer(payload, online=online)
        if not ok:
            messagebox.showerror("存檔失敗", msg)
            return
        p.update(payload)
        self._refresh_grid()
        self._reselect(self._selected_idx)
        messagebox.showinfo("存檔", f"印表機 {pid} 設定已儲存")

    def _on_add(self) -> None:
        """新增：在清單尾端放一筆空白資料，解鎖印表機編號欄位供填入。"""
        blank = {
            "printer_id": "",
            "printer_name": "",
            "site_id": self._site_id,   # 預設為登入站點
            "server_ip": _get_host_ip(),  # 預設為本機 IP（LBSB01 所在主機）
            "printer_ip": "",
            "printer_driver": "",   # 新增時留空；使用者選填 Driver 或 印表機 IP（互斥）
            "shift_left": "0",
            "shift_top": "0",
            "darkness": "12",
            "printer_model": "",
            "is_active": 1,
            "note": "",
        }
        self._printers.append(blank)
        self._refresh_grid()
        self._is_new = True
        self._selected_idx = len(self._printers) - 1
        self._reselect(self._selected_idx)
        self.ent_id.configure(state="normal")
        self.ent_id.focus_set()

    def _on_delete(self) -> None:
        """刪除：依 Cursor 位置硬刪除。先呼叫 SRVDP018 清子表對應，再呼叫 SRVLB092 刪 LB_PRINTER。"""
        if self._selected_idx is None:
            messagebox.showwarning("刪除", "請先選取要刪除的印表機")
            return

        p = self._printers[self._selected_idx]
        pid = p.get("printer_id", "")
        site = p.get("site_id", "")

        if not pid:
            # 新增但尚未存檔的空白列，直接移除即可
            self._printers.pop(self._selected_idx)
            self._selected_idx = None
            self._is_new = False
            self.ent_id.configure(state="disabled")
            self._refresh_grid()
            return

        if not messagebox.askyesno(
            "刪除確認",
            f"印表機 {pid}（站點 {site}）\n\n"
            "刪除時會一併刪除 資訊設備有參考到的標籤對應資料!!\n\n"
            "請確認是否繼續？",
            icon="warning",
        ):
            return

        # 透過 local_db：刪 Local Cache + 離線時排 PENDING_OPS（SRVDP018 + DELETE 順序）
        online = self._session.online if self._session else False
        ok, msg = self._local_db.remove_printer(site, pid, online=online)
        if not ok:
            messagebox.showerror("刪除失敗", msg)
            return

        self._printers.pop(self._selected_idx)
        self._selected_idx = None
        self._refresh_grid()
        messagebox.showinfo("刪除", f"印表機 {pid} 已刪除（含站點標籤對應）")

    # ── Helpers ──────────────────────────────────────────────

    def _collect_form(self, printer_id: str) -> dict:
        return {
            "printer_id": printer_id,
            "printer_name": self.var_name.get(),
            "site_id": self._site_id,  # 存檔時一律帶入登入站點
            "server_ip": self.var_server_ip.get(),
            "printer_ip": self.var_printer_ip.get(),
            "printer_driver": self.var_driver.get(),
            "shift_left": self.var_shift_l.get(),
            "shift_top": self.var_shift_t.get(),
            "darkness": self.var_dark.get(),
            "printer_model": self.var_model.get(),
            "is_active": 1,
            "note": self.var_note.get(),
        }

    def _reselect(self, idx: int) -> None:
        children = self.tree.get_children()
        if 0 <= idx < len(children):
            item = children[idx]
            self.tree.selection_set(item)
            self.tree.see(item)

    # ── 列印識別貼紙 ─────────────────────────────────────────

    def _on_print_id_label(self) -> None:
        if self._selected_idx is None:
            messagebox.showwarning("列印", "請先選取印表機")
            return
        p = self._printers[self._selected_idx]
        messagebox.showinfo("列印識別貼紙",
            f"印表機: {p['printer_id']} - {p.get('printer_name','')}\n"
            f"（識別貼紙列印待實作）")
