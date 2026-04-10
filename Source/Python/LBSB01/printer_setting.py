"""
PrinterSetting — 標籤印表機設定。

由 Main Menu「設定→標籤印表機設定」開啟。
對照 VB6 Frm_Set_Printer.frm，改用藍色色系。
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
PRINTER_TYPES = [
    "GoDEX EZ2250i（工業型）",
    "GoDEX EZ2350i（工業型）",
    "GoDEX EZ6250i（工業型）",
    "GoDEX G500（桌上型）",
    "GoDEX G530（桌上型）",
    "GoDEX RT700i（桌上型）",
    "GoDEX DT2x（攜帶型）",
    "GoDEX MX30（攜帶型）",
]

# ── 連線方式選項 ──
LINK_TYPES = ["TCP", "USB", "BT"]


class PrinterSetting(tk.Toplevel):
    """標籤印表機設定視窗。"""

    def __init__(self, master: tk.Tk) -> None:
        super().__init__(master)
        self.title("LBSB01-標籤印表機設定")
        self.geometry("1050x680")
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

        # ====== 印表機清單（Treeview 取代 MSFlexGrid）======
        grid_frame = tk.Frame(self, bg=CLR_BG)
        grid_frame.pack(fill="both", expand=True, padx=8, pady=4)

        columns = ("printer_id", "printer_name", "link_type", "ip_address", "ip_port",
                   "usb_port", "bt_name", "shift_left", "shift_top", "darkness",
                   "printer_type", "is_active", "note")
        col_names = ("印表機編號", "名稱", "連線", "IP 位址", "Port",
                     "USB Port", "藍牙名稱", "左位移", "上位移", "明暗",
                     "型號", "啟用", "說明")
        col_widths = (90, 120, 50, 120, 50, 60, 100, 55, 55, 45, 150, 40, 150)

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

        # Row 0
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
        self.var_type = tk.StringVar()
        cmb_type = ttk.Combobox(edit_frame, textvariable=self.var_type, width=25,
                                font=("新細明體", 10), values=PRINTER_TYPES)
        cmb_type.grid(row=r, column=5, sticky="w", pady=3)

        # Row 1
        r = 1
        tk.Label(edit_frame, text="連線方式:", bg=CLR_BG, fg=CLR_TITLE_FG,
                 font=("新細明體", 11)).grid(row=r, column=0, sticky="e", padx=(0, 4))
        self.var_link = tk.StringVar(value="TCP")
        cmb_link = ttk.Combobox(edit_frame, textvariable=self.var_link, width=6,
                                font=("新細明體", 11), values=LINK_TYPES, state="readonly")
        cmb_link.grid(row=r, column=1, sticky="w", pady=3)
        cmb_link.bind("<<ComboboxSelected>>", self._on_link_changed)

        tk.Label(edit_frame, text="IP:", bg=CLR_BG, fg=CLR_TITLE_FG,
                 font=("新細明體", 11)).grid(row=r, column=2, sticky="e", padx=(16, 4))
        self.var_ip = tk.StringVar()
        self.ent_ip = tk.Entry(edit_frame, textvariable=self.var_ip, width=16,
                               font=("新細明體", 11))
        self.ent_ip.grid(row=r, column=3, sticky="w", pady=3)

        tk.Label(edit_frame, text="Port:", bg=CLR_BG, fg=CLR_TITLE_FG,
                 font=("新細明體", 11)).grid(row=r, column=4, sticky="e", padx=(16, 4))
        self.var_port = tk.StringVar(value="9100")
        self.ent_port = tk.Entry(edit_frame, textvariable=self.var_port, width=6,
                                 font=("新細明體", 11))
        self.ent_port.grid(row=r, column=5, sticky="w", pady=3)

        # Row 2
        r = 2
        tk.Label(edit_frame, text="USB Port:", bg=CLR_BG, fg=CLR_TITLE_FG,
                 font=("新細明體", 11)).grid(row=r, column=0, sticky="e", padx=(0, 4))
        self.var_usb = tk.StringVar(value="6")
        self.ent_usb = tk.Entry(edit_frame, textvariable=self.var_usb, width=6,
                                font=("新細明體", 11))
        self.ent_usb.grid(row=r, column=1, sticky="w", pady=3)

        tk.Label(edit_frame, text="藍牙名稱:", bg=CLR_BG, fg=CLR_TITLE_FG,
                 font=("新細明體", 11)).grid(row=r, column=2, sticky="e", padx=(16, 4))
        self.var_bt = tk.StringVar()
        self.ent_bt = tk.Entry(edit_frame, textvariable=self.var_bt, width=20,
                               font=("新細明體", 11))
        self.ent_bt.grid(row=r, column=3, sticky="w", pady=3)

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

        # 初始連線欄位狀態
        self._on_link_changed(None)

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
                p.get("link_type", ""),
                p.get("ip_address", ""),
                p.get("ip_port", ""),
                p.get("usb_port", ""),
                p.get("bt_name", ""),
                p.get("shift_left", 0),
                p.get("shift_top", 0),
                p.get("darkness", 12),
                p.get("printer_type", ""),
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
        self.var_link.set(values[2])
        self.var_ip.set(values[3])
        self.var_port.set(values[4] or "9100")
        self.var_usb.set(values[5] or "6")
        self.var_bt.set(values[6])
        self.var_shift_l.set(values[7])
        self.var_shift_t.set(values[8])
        self.var_dark.set(values[9])
        self.var_type.set(values[10])
        self.var_note.set(values[12])

        self._on_link_changed(None)

    def _on_link_changed(self, _event) -> None:
        link = self.var_link.get()
        # TCP: IP/Port 啟用, USB/BT 停用
        self.ent_ip.config(state="normal" if link == "TCP" else "disabled")
        self.ent_port.config(state="normal" if link == "TCP" else "disabled")
        self.ent_usb.config(state="normal" if link == "USB" else "disabled")
        self.ent_bt.config(state="normal" if link == "BT" else "disabled")

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
        p["link_type"] = self.var_link.get()
        p["ip_address"] = self.var_ip.get()
        p["ip_port"] = self.var_port.get()
        p["usb_port"] = self.var_usb.get()
        p["bt_name"] = self.var_bt.get()
        p["shift_left"] = self.var_shift_l.get()
        p["shift_top"] = self.var_shift_t.get()
        p["darkness"] = self.var_dark.get()
        p["printer_type"] = self.var_type.get()
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
            "link_type": "USB",
            "ip_address": "",
            "ip_port": "9100",
            "usb_port": "6",
            "bt_name": "",
            "shift_left": "0",
            "shift_top": "0",
            "darkness": "12",
            "printer_type": "",
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
                "link_type": "USB", "ip_address": "", "ip_port": "9100",
                "usb_port": "6", "bt_name": "",
                "shift_left": "0", "shift_top": "0", "darkness": "12",
                "printer_type": "GoDEX G530（桌上型）", "is_active": 1,
                "note": "血庫一樓護理站旁",
            },
            {
                "printer_id": "PRN-002", "printer_name": "血庫二樓條碼機",
                "link_type": "TCP", "ip_address": "192.168.1.50", "ip_port": "9100",
                "usb_port": "", "bt_name": "",
                "shift_left": "2", "shift_top": "-3", "darkness": "14",
                "printer_type": "GoDEX EZ2250i（工業型）", "is_active": 1,
                "note": "成分處理室",
            },
            {
                "printer_id": "PRN-003", "printer_name": "採血車攜帶型",
                "link_type": "BT", "ip_address": "", "ip_port": "",
                "usb_port": "", "bt_name": "GoDEX_MX30_BT01",
                "shift_left": "0", "shift_top": "0", "darkness": "13",
                "printer_type": "GoDEX MX30（攜帶型）", "is_active": 1,
                "note": "採血車藍牙連線",
            },
        ]
