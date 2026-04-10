"""
SampleData_Print — 標籤測試頁。

獨立視窗，由 Main Menu 開啟。
提供標籤選擇、紙張尺寸設定、Sample Data 列印功能。
"""

from __future__ import annotations
import logging
import os
import traceback
import tkinter as tk
from tkinter import ttk, messagebox

from labels import LABEL_DEFS, LABEL_MAP, PAPER_SIZES, LabelDef
from sample_data import LabelData, build_sample
from bar_l00 import print_l00
from bar_cp11 import print_cp11
from bar_cp19 import print_cp19
from ezpl import GodexPrinter, LinkType

log = logging.getLogger(__name__)


# ── Dispatcher ───────────────────────────────────────────────

def print_label(
    printer: GodexPrinter,
    label_def: LabelDef,
    data: LabelData,
    paper_w: int,
    paper_h: int,
) -> None:
    code = label_def.code
    if code in ("CP01", "CP02"):
        from bar_l00 import BloodLabelData
        bld = BloodLabelData(
            bag_type=data.label_type, bag_no=data.bag_no,
            data_1=data.data_1, data_3=data.data_3, data_4=data.data_4,
            data_5=data.data_5, data_6=data.data_6, data_7=data.data_7,
            data_8=data.data_8, data_10=data.data_10, data_11=data.data_11,
            data_12=data.data_12, data_19=data.data_19,
        )
        print_l00(printer, bld, paper_width=paper_w, paper_height=paper_h, gap=label_def.gap)
    elif code == "CP11":
        print_cp11(printer, data, paper_width=paper_w, paper_height=paper_h, gap=label_def.gap)
    elif code == "CP19":
        print_cp19(printer, data, paper_width=paper_w, paper_height=paper_h, gap=label_def.gap)
    else:
        _print_stub(printer, label_def, data, paper_w, paper_h)


def _print_stub(printer, label_def, data, paper_w, paper_h):
    printer.label_setup(width=paper_w, height=paper_h, gap=label_def.gap, darkness=12, speed=2)
    printer.job_start()
    bx, by = 10, 25
    y = by
    printer.text_out(bx, y, 60, "Arial", f"[{label_def.code}] {label_def.name}")
    y += 70
    if data.bag_no:
        printer.text_out(bx, y, 40, "Arial", f"BAG: {data.bag_no}")
        y += 48
    for i in range(1, 20):
        val = getattr(data, f"data_{i}", "")
        if val:
            line = f"D{i}: {val}"
            if len(line) > 50:
                line = line[:50] + "..."
            printer.text_out(bx, y, 30, "Arial", line)
            y += 35
            if y > paper_h * 8 - 100:
                break
    if data.data_1:
        bd = data.data_1[:40]
        printer.barcode("Q", bx, y, narrow=2, wide=1, height=60, rotation=0, readable=1, data=bd)
    printer.job_end()


# ═══════════════════════════════════════════════════════════════
#  SampleDataPrint — 標籤測試頁視窗
# ═══════════════════════════════════════════════════════════════

class SampleDataPrint(tk.Toplevel):

    def __init__(self, master: tk.Tk, link_var: tk.StringVar,
                 ip_var: tk.StringVar, port_var: tk.StringVar) -> None:
        super().__init__(master)
        self.title("標籤測試頁 (SampleData_Print)")
        self.geometry("580x580")
        self.resizable(False, False)

        # 共用連線設定（從 Main 傳入）
        self._link_var = link_var
        self._ip_var = ip_var
        self._port_var = port_var

        self._build_ui()

    def _build_ui(self) -> None:
        ttk.Label(self, text="標籤測試頁",
                  font=("Microsoft JhengHei", 16, "bold")).pack(pady=(12, 6))

        frame = ttk.LabelFrame(self, text="列印參數", padding=12)
        frame.pack(fill="x", padx=16, pady=6)
        frame.columnconfigure(1, weight=1)

        row = 0

        # ── 標籤類型 ──
        ttk.Label(frame, text="標籤類型:").grid(row=row, column=0, sticky="e", padx=(0, 8))
        self.var_label = tk.StringVar()
        self.cmb_label = ttk.Combobox(frame, textvariable=self.var_label,
                                      state="readonly", width=40)
        self.cmb_label["values"] = [d.display for d in LABEL_DEFS]
        self.cmb_label.current(0)
        self.cmb_label.grid(row=row, column=1, sticky="w")
        self.cmb_label.bind("<<ComboboxSelected>>", self._on_label_changed)

        # ── 紙張尺寸 ──
        row += 1
        ttk.Label(frame, text="紙張尺寸:").grid(row=row, column=0, sticky="e",
                                                padx=(0, 8), pady=(8, 0))
        self.var_size = tk.StringVar()
        self.cmb_size = ttk.Combobox(frame, textvariable=self.var_size,
                                     state="readonly", width=20)
        self.cmb_size["values"] = [f"{w}mm x {h}mm" for w, h in PAPER_SIZES]
        self.cmb_size.grid(row=row, column=1, sticky="w", pady=(8, 0))
        self.cmb_size.bind("<<ComboboxSelected>>", self._on_size_changed)

        # ── 寬/高 ──
        row += 1
        ttk.Label(frame, text="寬(mm):").grid(row=row, column=0, sticky="e",
                                              padx=(0, 8), pady=(8, 0))
        wh_frame = ttk.Frame(frame)
        wh_frame.grid(row=row, column=1, sticky="w", pady=(8, 0))
        self.var_paper_w = tk.StringVar()
        ttk.Entry(wh_frame, textvariable=self.var_paper_w, width=6).pack(side="left")
        ttk.Label(wh_frame, text=" x 高(mm):").pack(side="left")
        self.var_paper_h = tk.StringVar()
        ttk.Entry(wh_frame, textvariable=self.var_paper_h, width=6).pack(side="left")
        ttk.Label(wh_frame, text="  ← 列印以此為準",
                  foreground="gray").pack(side="left", padx=(8, 0))

        # ── 血袋編號 ──
        row += 1
        ttk.Label(frame, text="血袋編號:").grid(row=row, column=0, sticky="e",
                                               padx=(0, 8), pady=(8, 0))
        self.var_bag_no = tk.StringVar(value="TW2024050001")
        ttk.Entry(frame, textvariable=self.var_bag_no, width=30).grid(
            row=row, column=1, sticky="w", pady=(8, 0))

        # ── 連線資訊（顯示，不可改，由 Main 控制）──
        row += 1
        ttk.Label(frame, text="連線方式:").grid(row=row, column=0, sticky="e",
                                               padx=(0, 8), pady=(8, 0))
        self.lbl_link = ttk.Label(frame, text="")
        self.lbl_link.grid(row=row, column=1, sticky="w", pady=(8, 0))
        self._update_link_display()

        # ── 按鈕 ──
        btn_frame = ttk.Frame(self)
        btn_frame.pack(pady=12)
        ttk.Button(btn_frame, text="產生 EZPL 檔案",
                   command=self._on_generate).pack(side="left", padx=8)
        ttk.Button(btn_frame, text="列印",
                   command=self._on_print).pack(side="left", padx=8)

        # ── 輸出區 ──
        output_frame = ttk.LabelFrame(self, text="EZPL 指令輸出", padding=8)
        output_frame.pack(fill="both", expand=True, padx=16, pady=(0, 12))
        self.txt_output = tk.Text(output_frame, height=10,
                                  font=("Consolas", 10), state="disabled")
        scrollbar = ttk.Scrollbar(output_frame, orient="vertical",
                                  command=self.txt_output.yview)
        self.txt_output.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.txt_output.pack(fill="both", expand=True)

        # 初始化
        self._on_label_changed(None)

    # ── Events ───────────────────────────────────────────────

    def _on_label_changed(self, _event) -> None:
        label_def = self._get_label_def()
        if not label_def:
            return
        size_str = label_def.size_display
        values = list(self.cmb_size["values"])
        if size_str in values:
            self.cmb_size.set(size_str)
        self.var_paper_w.set(str(label_def.width_mm))
        self.var_paper_h.set(str(label_def.height_mm))

    def _on_size_changed(self, _event) -> None:
        parts = self.var_size.get().replace("mm", "").split("x")
        if len(parts) == 2:
            self.var_paper_w.set(parts[0].strip())
            self.var_paper_h.set(parts[1].strip())

    def _update_link_display(self) -> None:
        link = self._link_var.get()
        if link == "USB":
            self.lbl_link.config(text="USB（由主畫面設定）")
        else:
            self.lbl_link.config(text=f"TCP {self._ip_var.get()}:{self._port_var.get()}（由主畫面設定）")

    # ── Helpers ──────────────────────────────────────────────

    def _get_label_def(self) -> LabelDef | None:
        display = self.var_label.get()
        code = display.split("-")[0] if "-" in display else display
        return LABEL_MAP.get(code)

    def _get_paper_size(self) -> tuple[int, int]:
        try:
            w = int(self.var_paper_w.get().strip())
            h = int(self.var_paper_h.get().strip())
        except ValueError:
            raise ValueError("紙張寬/高必須為數字")
        if w <= 0 or h <= 0:
            raise ValueError("紙張寬/高必須大於 0")
        return w, h

    def _build_data(self) -> LabelData:
        label_def = self._get_label_def()
        if not label_def:
            raise ValueError("請選擇標籤類型")
        bag_no = self.var_bag_no.get().strip() or "TW2024050001"
        return build_sample(label_def.code, bag_no)

    def _show_output(self, text: str) -> None:
        self.txt_output.configure(state="normal")
        self.txt_output.delete("1.0", "end")
        self.txt_output.insert("1.0", text)
        self.txt_output.configure(state="disabled")

    # ── Actions ──────────────────────────────────────────────

    def _on_generate(self) -> None:
        try:
            data = self._build_data()
            paper_w, paper_h = self._get_paper_size()
            label_def = self._get_label_def()
        except ValueError as e:
            messagebox.showwarning("輸入錯誤", str(e))
            return

        printer = GodexPrinter(LinkType.FILE)
        printer.open()
        print_label(printer, label_def, data, paper_w, paper_h)

        ezpl = printer.get_commands()
        filename = f"output_{label_def.code}.ezpl"
        filepath = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)
        printer.save(filepath)
        printer.close()

        self._show_output(ezpl)
        messagebox.showinfo("完成", f"EZPL 指令已存至:\n{filepath}")

    def _on_print(self) -> None:
        try:
            data = self._build_data()
            paper_w, paper_h = self._get_paper_size()
            label_def = self._get_label_def()
        except ValueError as e:
            messagebox.showwarning("輸入錯誤", str(e))
            return

        link = LinkType.USB if self._link_var.get() == "USB" else LinkType.TCP
        ip = self._ip_var.get().strip()
        try:
            tcp_port = int(self._port_var.get().strip())
        except ValueError:
            tcp_port = 9100

        # FILE 版供顯示
        file_printer = GodexPrinter(LinkType.FILE)
        file_printer.open()
        print_label(file_printer, label_def, data, paper_w, paper_h)
        self._show_output(file_printer.get_commands())
        file_printer.close()

        # 實際列印
        try:
            with GodexPrinter(link) as printer:
                printer.open(ip=ip, tcp_port=tcp_port)
                print_label(printer, label_def, data, paper_w, paper_h)

            mode = "USB (DLL)" if link == LinkType.USB else f"TCP {ip}:{tcp_port}"
            messagebox.showinfo("完成",
                f"列印完成（{mode}）\n"
                f"標籤: {label_def.display}\n"
                f"尺寸: {paper_w}mm x {paper_h}mm")

        except FileNotFoundError as e:
            messagebox.showerror("DLL 錯誤", str(e))
        except ConnectionError as e:
            messagebox.showerror("連線失敗", str(e))
        except Exception as e:
            log.error("列印失敗:\n%s", traceback.format_exc())
            messagebox.showerror("列印失敗", f"{e}\n\n詳見 app.log")
