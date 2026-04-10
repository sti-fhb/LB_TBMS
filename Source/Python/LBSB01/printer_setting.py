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
import tkinter as tk
from tkinter import ttk, messagebox

log = logging.getLogger(__name__)

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
    "GoDEX EZ2250i（工業型）",
    "GoDEX EZ2350i（工業型）",
    "GoDEX EZ6250i（工業型）",
    "GoDEX G500（桌上型）",
    "GoDEX G530（桌上型）",
    "GoDEX RT700i（桌上型）",
    "GoDEX DT2x（攜帶型）",
    "GoDEX MX30（攜帶型）",
]


class PrinterSetting(tk.Toplevel):
    """標籤印表機設定視窗。"""

    def __init__(self, master: tk.Tk) -> None:
        super().__init__(master)
        self.title("LBSB01-標籤印表機設定")
        self.geometry("1100x680")
        self.resizable(True, True)
        self.configure(bg=CLR_BG)

        # 模擬資料（後續改為從 API/本地快取讀取）
        self._printers: list[dict] = self._load_sample_data()
        self._selected_idx: int | None = None

        self._build_ui()
        self._refresh_grid()

    # ── UI ───────────────────────────────────────────────────

    def _build_ui(self) -> None:
        # ====== 標題列 + 按鈕 ======
        top = tk.Frame(self, bg=CLR_BG)
        top.pack(fill="x", padx=8, pady=(8, 4))

        tk.Button(top, text="重新整理", font=("新細明體", 11), bg=CLR_BTN_BG, fg=CLR_BTN_FG,
                  command=self._on_refresh).pack(side="left", padx=(0, 8))
        tk.Button(top, text="列印印表機識別貼紙", font=("新細明體", 10), bg=CLR_BTN_BG, fg=CLR_BTN_FG,
                  command=self._on_print_id_label).pack(side="left", padx=(0, 8))
        tk.Button(top, text="新增印表機", font=("新細明體", 11), bg="#27AE60", fg="white",
                  command=self._on_add).pack(side="left", padx=(0, 8))

        # 提示
        hint_frame = tk.Frame(top, bg=CLR_BG)
        hint_frame.pack(side="right")
        tk.Label(hint_frame, text="PS: 明暗=0 代表預設 12，最大 19",
                 fg=CLR_WARN, bg=CLR_BG, font=("新細明體", 9)).pack(anchor="e")
        tk.Label(hint_frame, text="建議值: 小型機 12~14，工業型 6~8",
                 fg=CLR_ACCENT, bg=CLR_BG, font=("新細明體", 9)).pack(anchor="e")

        # ====== 印表機清單（Treeview）======
        grid_frame = tk.Frame(self, bg=CLR_BG)
        grid_frame.pack(fill="both", expand=True, padx=8, pady=4)

        columns = ("printer_id", "printer_name", "site_id", "server_ip",
                   "printer_ip", "printer_driver",
                   "shift_left", "shift_top", "darkness",
                   "printer_model", "is_active", "note")
        col_names = ("印表機編號", "名稱", "站點", "Server IP",
                     "印表機 IP", "Driver",
                     "左位移", "上位移", "明暗",
                     "型號", "啟用", "說明")
        col_widths = (90, 120, 55, 120,
                      120, 130,
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

        # Row 1: 站點 / Server IP / 印表機 IP / Port
        r = 1
        tk.Label(edit_frame, text="站點:", bg=CLR_BG, fg=CLR_TITLE_FG,
                 font=("新細明體", 11)).grid(row=r, column=0, sticky="e", padx=(0, 4))
        self.var_site = tk.StringVar()
        tk.Entry(edit_frame, textvariable=self.var_site, width=10,
                 font=("新細明體", 11)).grid(row=r, column=1, sticky="w", pady=3)

        tk.Label(edit_frame, text="Server IP:", bg=CLR_BG, fg=CLR_TITLE_FG,
                 font=("新細明體", 11)).grid(row=r, column=2, sticky="e", padx=(16, 4))
        self.var_server_ip = tk.StringVar()
        tk.Entry(edit_frame, textvariable=self.var_server_ip, width=16,
                 font=("新細明體", 11)).grid(row=r, column=3, sticky="w", pady=3)

        tk.Label(edit_frame, text="印表機 IP:", bg=CLR_BG, fg=CLR_TITLE_FG,
                 font=("新細明體", 11)).grid(row=r, column=4, sticky="e", padx=(16, 4))
        self.var_printer_ip = tk.StringVar()
        tk.Entry(edit_frame, textvariable=self.var_printer_ip, width=16,
                 font=("新細明體", 11)).grid(row=r, column=5, sticky="w", pady=3)

        # Row 2: Driver
        r = 2
        tk.Label(edit_frame, text="Driver:", bg=CLR_BG, fg=CLR_TITLE_FG,
                 font=("新細明體", 11)).grid(row=r, column=0, sticky="e", padx=(0, 4))
        self.var_driver = tk.StringVar()
        tk.Entry(edit_frame, textvariable=self.var_driver, width=20,
                 font=("新細明體", 11)).grid(row=r, column=1, sticky="w", pady=3)

        tk.Label(edit_frame, text="USB 填 USB，藍牙填 #名稱，有 IP 可留空",
                 fg=CLR_ACCENT, bg=CLR_BG, font=("新細明體", 9)).grid(
                     row=r, column=2, columnspan=4, sticky="w", pady=3)

        # Row 3: 公差校正
        r = 3
        tk.Label(edit_frame, text="左位移(dots):", bg=CLR_BG, fg=CLR_TITLE_FG,
                 font=("新細明體", 11)).grid(row=r, column=0, sticky="e", padx=(0, 4))
        self.var_shift_l = tk.StringVar(value="0")
        tk.Entry(edit_frame, textvariable=self.var_shift_l, width=6,
                 font=("新細明體", 11)).grid(row=r, column=1, sticky="w", pady=3)

        tk.Label(edit_frame, text="上位移(dots):", bg=CLR_BG, fg=CLR_TITLE_FG,
                 font=("新細明體", 11)).grid(row=r, column=2, sticky="e", padx=(16, 4))
        self.var_shift_t = tk.StringVar(value="0")
        tk.Entry(edit_frame, textvariable=self.var_shift_t, width=6,
                 font=("新細明體", 11)).grid(row=r, column=3, sticky="w", pady=3)

        tk.Label(edit_frame, text="明暗:", bg=CLR_BG, fg=CLR_TITLE_FG,
                 font=("新細明體", 11)).grid(row=r, column=4, sticky="e", padx=(16, 4))
        self.var_dark = tk.StringVar(value="12")
        tk.Entry(edit_frame, textvariable=self.var_dark, width=4,
                 font=("新細明體", 11)).grid(row=r, column=5, sticky="w", pady=3)

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
                p.get("site_id", ""),
                p.get("server_ip", ""),
                p.get("printer_ip", ""),
                p.get("printer_driver", ""),
                p.get("shift_left", 0),
                p.get("shift_top", 0),
                p.get("darkness", 12),
                p.get("printer_model", ""),
                active,
                p.get("note", ""),
            ), tags=(tag,))

    # ── Events ───────────────────────────────────────────────

    def _on_tree_select(self, _event) -> None:
        sel = self.tree.selection()
        if not sel:
            return
        values = self.tree.item(sel[0], "values")
        idx = self.tree.index(sel[0])
        self._selected_idx = idx

        self.var_id.set(values[0])
        self.var_name.set(values[1])
        self.var_site.set(values[2])
        self.var_server_ip.set(values[3])
        self.var_printer_ip.set(values[4])
        self.var_driver.set(values[5])
        self.var_shift_l.set(values[6])
        self.var_shift_t.set(values[7])
        self.var_dark.set(values[8])
        self.var_model.set(values[9])
        self.var_note.set(values[11])

    def _on_refresh(self) -> None:
        # 後續改為 Call API 重新取得
        self._printers = self._load_sample_data()
        self._refresh_grid()
        messagebox.showinfo("重新整理", "已重新載入印表機清單")

    def _on_save(self) -> None:
        if self._selected_idx is None:
            messagebox.showwarning("存檔", "請先選取印表機")
            return

        p = self._printers[self._selected_idx]
        p["printer_name"] = self.var_name.get()
        p["site_id"] = self.var_site.get()
        p["server_ip"] = self.var_server_ip.get()
        p["printer_ip"] = self.var_printer_ip.get()
        p["printer_driver"] = self.var_driver.get()
        p["shift_left"] = self.var_shift_l.get()
        p["shift_top"] = self.var_shift_t.get()
        p["darkness"] = self.var_dark.get()
        p["printer_model"] = self.var_model.get()
        p["note"] = self.var_note.get()

        self._refresh_grid()
        # 後續改為 Call API 寫入中央 DB
        messagebox.showinfo("存檔", f"印表機 {p['printer_id']} 設定已儲存（本地）")

    def _on_add(self) -> None:
        # 產生新編號
        max_num = 0
        for p in self._printers:
            pid = p.get("printer_id", "")
            if pid.startswith("PRN-"):
                try:
                    num = int(pid[4:])
                    max_num = max(max_num, num)
                except ValueError:
                    pass
        new_id = f"PRN-{max_num + 1:03d}"

        new_printer = {
            "printer_id": new_id,
            "printer_name": "",
            "site_id": "",
            "server_ip": "",
            "printer_ip": "",
            "printer_driver": "USB",
            "shift_left": "0",
            "shift_top": "0",
            "darkness": "12",
            "printer_model": "",
            "is_active": 1,
            "note": "",
        }
        self._printers.append(new_printer)
        self._refresh_grid()

        # 選取新增的那一筆
        children = self.tree.get_children()
        if children:
            last = children[-1]
            self.tree.selection_set(last)
            self.tree.see(last)
            self._on_tree_select(None)

    def _on_print_id_label(self) -> None:
        if self._selected_idx is None:
            messagebox.showwarning("列印", "請先選取印表機")
            return
        p = self._printers[self._selected_idx]
        messagebox.showinfo("列印識別貼紙",
            f"印表機: {p['printer_id']} - {p.get('printer_name','')}\n"
            f"（識別貼紙列印待實作）")

    # ── Sample Data ──────────────────────────────────────────

    @staticmethod
    def _load_sample_data() -> list[dict]:
        """模擬印表機清單（後續改為 API 取得）。"""
        return [
            {
                "printer_id": "PRN-001", "printer_name": "血庫一樓條碼機",
                "site_id": "S01", "server_ip": "192.168.1.10",
                "printer_ip": "",
                "printer_driver": "USB",
                "shift_left": "0", "shift_top": "0", "darkness": "12",
                "printer_model": "GoDEX G530（桌上型）", "is_active": 1,
                "note": "血庫一樓護理站旁",
            },
            {
                "printer_id": "PRN-002", "printer_name": "血庫二樓條碼機",
                "site_id": "S01", "server_ip": "192.168.1.10",
                "printer_ip": "192.168.1.50",
                "printer_driver": "",
                "shift_left": "2", "shift_top": "-3", "darkness": "14",
                "printer_model": "GoDEX EZ2250i（工業型）", "is_active": 1,
                "note": "成分處理室",
            },
            {
                "printer_id": "PRN-003", "printer_name": "採血車攜帶型",
                "site_id": "S01", "server_ip": "192.168.1.10",
                "printer_ip": "",
                "printer_driver": "#GoDEX_MX30_BT01",
                "shift_left": "0", "shift_top": "0", "darkness": "13",
                "printer_model": "GoDEX MX30（攜帶型）", "is_active": 1,
                "note": "採血車藍牙連線",
            },
        ]
