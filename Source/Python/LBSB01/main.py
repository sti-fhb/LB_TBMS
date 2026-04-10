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
from sample_data import LabelData, build_sample
from sample_data_print import SampleDataPrint, print_label
from printer_setting import PrinterSetting
from ezpl import GodexPrinter, LinkType

# ── Log ──
logging.basicConfig(
    filename=os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.log"),
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    encoding="utf-8",
)
log = logging.getLogger(__name__)

# ── 藍色色系 ─────────────────────────────────────────────────
CLR_BG = "#D6E4F0"           # 主背景（淺藍）
CLR_ONLINE_BG = "#C0D8F0"    # 線上區背景
CLR_ONLINE_FG = "#003366"    # 線上區前景（深藍）
CLR_OFFLINE_BG = "#4A7FB5"   # 離線區背景（深藍）
CLR_OFFLINE_FG = "#FFFFFF"   # 離線區前景（白）
CLR_TITLE_FG = "#003366"     # 標題前景
CLR_ACCENT = "#1A5276"       # 強調色
CLR_BTN_BG = "#2E86C1"       # 按鈕背景
CLR_BTN_FG = "#FFFFFF"       # 按鈕前景


class App(tk.Tk):

    def __init__(self) -> None:
        super().__init__()
        self.title("LBSB01-標籤服務程式")
        self.geometry("1010x720")
        self.resizable(True, True)
        self.configure(bg=CLR_BG)
        self._build_menu()
        self._build_ui()

    # ── Menu ─────────────────────────────────────────────────
    def _build_menu(self) -> None:
        menubar = tk.Menu(self)
        menu_setting = tk.Menu(menubar, tearoff=0)
        menu_setting.add_command(label="標籤印表機設定",
                                command=self._open_printer_setting)
        menubar.add_cascade(label="設定", menu=menu_setting)
        menubar.add_command(label="標籤測試頁", command=self._open_sample_data_print)
        menubar.add_command(label="列印空白NG標籤",
                            command=lambda: messagebox.showinfo("NG", "空白NG標籤（待實作）"))
        menubar.add_command(label="查詢歷史記錄",
                            command=lambda: messagebox.showinfo("歷史", "歷史記錄查詢（待實作）"))
        self.config(menu=menubar)

    # ── UI ───────────────────────────────────────────────────
    def _build_ui(self) -> None:
        # ====== Row 0: 標題列 ======
        top = tk.Frame(self, bg=CLR_BG)
        top.pack(fill="x", padx=6, pady=(6, 0))

        tk.Label(top, text="LBSB01-標籤服務程式", font=("標楷體", 18, "bold"),
                 bg=CLR_BG, fg=CLR_TITLE_FG).pack(side="left")

        # 連線方式
        self.var_link = tk.StringVar(value="USB")
        tk.Radiobutton(top, text="USB", variable=self.var_link, value="USB",
                       bg=CLR_BG, fg=CLR_TITLE_FG, selectcolor=CLR_BG,
                       command=self._toggle_ip).pack(side="left", padx=(20, 0))
        tk.Radiobutton(top, text="IP Print", variable=self.var_link, value="TCP",
                       bg=CLR_BG, fg=CLR_TITLE_FG, selectcolor=CLR_BG,
                       command=self._toggle_ip).pack(side="left")

        self.var_clear = tk.IntVar(value=1)
        tk.Checkbutton(top, text="印出後清除", variable=self.var_clear,
                       bg=CLR_BG, fg=CLR_TITLE_FG, selectcolor=CLR_BG,
                       font=("新細明體", 9)).pack(side="left", padx=(10, 0))

        self.var_auto = tk.IntVar(value=0)
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
            ("待列印張數:", "var_count", 10, True),
            ("列印者:", "var_user", 15, False),
            ("印表機編號:", "var_printer_no", 10, False),
            ("UUID:", "var_uuid", 25, True),
        ]
        for i, (lbl_text, var_name, width, disabled) in enumerate(fields):
            tk.Label(frm_detail, text=lbl_text, bg=CLR_ONLINE_BG, fg=CLR_ONLINE_FG,
                     font=("新細明體", 9)).grid(row=i, column=0, sticky="e", padx=(0, 4), pady=2)
            sv = tk.StringVar()
            setattr(self, var_name, sv)
            state = "disabled" if disabled else "normal"
            tk.Entry(frm_detail, textvariable=sv, width=width, state=state,
                     font=("新細明體", 9)).grid(row=i, column=1, sticky="w", pady=2)

        self.lbl_sname = tk.Label(frm_detail, text="", bg=CLR_ONLINE_BG, fg=CLR_ACCENT,
                                  font=("標楷體", 11, "bold"))
        self.lbl_sname.grid(row=1, column=2, sticky="w", padx=(4, 0))

        r = len(fields)
        tk.Label(frm_detail, text="指定印表機:", bg=CLR_ONLINE_BG, fg=CLR_ONLINE_FG,
                 font=("新細明體", 10)).grid(row=r, column=0, sticky="e", padx=(0, 4), pady=4)
        self.var_printer = tk.StringVar(value="USB")
        self.cmb_printer = ttk.Combobox(frm_detail, textvariable=self.var_printer,
                                        width=25, font=("新細明體", 11))
        self.cmb_printer["values"] = ["USB"]
        self.cmb_printer.grid(row=r, column=1, columnspan=2, sticky="w", pady=4)

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
                  command=lambda: None).pack(side="right", padx=2)
        tk.Button(btn_row, text="更新資料", font=("新細明體", 9),
                  command=lambda: None).pack(side="right", padx=2)

        self.lst_queue = tk.Listbox(frm_queue, font=("新細明體", 10), height=6)
        self.lst_queue.pack(fill="both", expand=True, pady=(4, 0))

        self.btn_print_online = tk.Button(
            frm_queue, text="  列印線上指定項目  ",
            font=("標楷體", 18, "bold"), bg=CLR_BTN_BG, fg=CLR_BTN_FG,
            activebackground="#1A6AA5", activeforeground="white",
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

        # --- 左: 離線列印項目明細 ---
        frm_offline = tk.LabelFrame(row3, text="離線列印項目明細", font=("標楷體", 12),
                                    fg=CLR_OFFLINE_FG, bg=CLR_OFFLINE_BG, padx=8, pady=4)
        frm_offline.pack(side="left", fill="y", padx=(0, 4))

        offline_fields = ["時間序:", "條碼種類:", "待列印張數:", "列印者:", "印表機編號:", "UUID:"]
        for i, lbl_text in enumerate(offline_fields):
            tk.Label(frm_offline, text=lbl_text, bg=CLR_OFFLINE_BG, fg=CLR_OFFLINE_FG,
                     font=("新細明體", 9)).grid(row=i, column=0, sticky="e", padx=(0, 4), pady=2)
            tk.Entry(frm_offline, width=20, state="disabled",
                     font=("新細明體", 9)).grid(row=i, column=1, sticky="w", pady=2)

        r2 = len(offline_fields)
        tk.Label(frm_offline, text="變更待印印表機:", bg=CLR_OFFLINE_BG, fg="#FFD700",
                 font=("新細明體", 10)).grid(row=r2, column=0, sticky="e", padx=(0, 4), pady=4)
        cmb_off = ttk.Combobox(frm_offline, width=25, font=("新細明體", 11))
        cmb_off["values"] = ["USB"]
        cmb_off.grid(row=r2, column=1, sticky="w", pady=4)
        tk.Button(frm_offline, text="儲存", font=("新細明體", 11)).grid(row=r2, column=2, padx=4)

        # --- 右: 離線等待重印項目 (Offline Queue) ---
        frm_wait = tk.LabelFrame(row3, text="離線等待重印項目 (Offline Queue)",
                                 font=("標楷體", 12),
                                 fg=CLR_OFFLINE_FG, bg=CLR_OFFLINE_BG, padx=8, pady=4)
        frm_wait.pack(side="left", fill="both", expand=True)

        btn_row2 = tk.Frame(frm_wait, bg=CLR_OFFLINE_BG)
        btn_row2.pack(fill="x")
        tk.Label(btn_row2, text="點二下可將離線項目移至上面進行上線排隊列印",
                 fg="#FFD700", bg=CLR_OFFLINE_BG, font=("新細明體", 8)).pack(side="left")
        tk.Button(btn_row2, text="刪除單筆", font=("新細明體", 9)).pack(side="right", padx=2)
        tk.Button(btn_row2, text="更新資料", font=("新細明體", 9)).pack(side="right", padx=2)

        self.lst_wait = tk.Listbox(frm_wait, font=("新細明體", 10), height=5)
        self.lst_wait.pack(fill="both", expand=True, pady=(4, 0))

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
        self.var_test_text = tk.StringVar(value="測試標籤列印資料\\n本頁為測試用")
        tk.Entry(frm_test, textvariable=self.var_test_text, width=40,
                 font=("新細明體", 9)).pack(side="left", padx=(0, 4))
        tk.Button(frm_test, text="列印測試資料", font=("新細明體", 9),
                  command=self._on_test_print).pack(side="left")

        # ====== Row 5: 可用標籤 ======
        self.lbl_tag = tk.Label(self, text="", font=("新細明體", 8),
                                bg=CLR_BG, fg=CLR_ACCENT, anchor="w")
        self.lbl_tag.pack(fill="x", padx=6, pady=(0, 2))
        self._update_tag_label()

        # ── IP 設定（隱藏，TCP 模式才顯示）──
        self.frm_ip = tk.Frame(self, bg=CLR_BG)
        tk.Label(self.frm_ip, text="IP:", bg=CLR_BG, fg=CLR_TITLE_FG).pack(side="left")
        self.var_ip = tk.StringVar(value="192.168.1.100")
        tk.Entry(self.frm_ip, textvariable=self.var_ip, width=15).pack(side="left")
        tk.Label(self.frm_ip, text="Port:", bg=CLR_BG, fg=CLR_TITLE_FG).pack(side="left", padx=(8, 0))
        self.var_port = tk.StringVar(value="9100")
        tk.Entry(self.frm_ip, textvariable=self.var_port, width=6).pack(side="left")

        # 初始化
        self._on_label_changed(None)

    # ── Clock ────────────────────────────────────────────────
    def _update_clock(self) -> None:
        self.lbl_time.config(text=time.strftime("%Y/%m/%d %H:%M:%S"))
        self.after(1000, self._update_clock)

    # ── Tag Label ────────────────────────────────────────────
    def _update_tag_label(self) -> None:
        tags = ", ".join(d.display for d in LABEL_DEFS)
        self.lbl_tag.config(text=f"可用標籤: {tags}")

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

    def _toggle_ip(self) -> None:
        if self.var_link.get() == "TCP":
            self.frm_ip.pack(fill="x", padx=6, pady=2, before=self.lbl_tag)
        else:
            self.frm_ip.pack_forget()

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
        self.lst_msg.insert(0, f"[{time.strftime('%H:%M:%S')}] {text}")
        if self.lst_msg.size() > 100:
            self.lst_msg.delete(100, "end")

    # ── Actions ──────────────────────────────────────────────
    def _on_print(self) -> None:
        label_def = self._get_label_def()
        if not label_def:
            messagebox.showwarning("輸入錯誤", "請選擇標籤類型")
            return
        try:
            paper_w, paper_h = self._get_paper_size()
        except ValueError as e:
            messagebox.showwarning("輸入錯誤", str(e))
            return

        data = build_sample(label_def.code)
        link = LinkType.USB if self.var_link.get() == "USB" else LinkType.TCP
        ip = self.var_ip.get().strip()
        try:
            tcp_port = int(self.var_port.get().strip())
        except ValueError:
            tcp_port = 9100

        self._add_msg(f"列印 {label_def.display} ({paper_w}x{paper_h}mm)")

        try:
            with GodexPrinter(link) as printer:
                printer.open(ip=ip, tcp_port=tcp_port)
                print_label(printer, label_def, data, paper_w, paper_h)

            mode = "USB" if link == LinkType.USB else f"TCP {ip}:{tcp_port}"
            self._add_msg(f"列印完成（{mode}）")

        except FileNotFoundError as e:
            messagebox.showerror("DLL 錯誤", str(e))
        except ConnectionError as e:
            messagebox.showerror("連線失敗", str(e))
        except Exception as e:
            log.error("列印失敗:\n%s", traceback.format_exc())
            messagebox.showerror("列印失敗", f"{e}\n\n詳見 app.log")

    def _open_printer_setting(self) -> None:
        """Menu → 設定 → 標籤印表機設定。"""
        PrinterSetting(self)

    def _open_sample_data_print(self) -> None:
        """Menu → 標籤測試頁。"""
        SampleDataPrint(self, self.var_link, self.var_ip, self.var_port)

    def _on_test_print(self) -> None:
        messagebox.showinfo("測試列印", f"測試文字: {self.var_test_text.get()}")


if __name__ == "__main__":
    App().mainloop()
