"""
SampleData_Print — 標籤測試頁。

獨立視窗，由 Main Menu 開啟。
提供標籤選擇、紙張尺寸設定、Sample Data 列印功能。
"""

from __future__ import annotations
import logging

import tkinter as tk
from tkinter import ttk, messagebox

from labels import LABEL_DEFS, LABEL_MAP, PAPER_SIZES, LabelDef
from sample_data import LabelData, build_sample
from bar_l00 import print_l00
from bar_cp11 import print_cp11
from bar_cp19 import print_cp19
from ezpl import GodexPrinter

log = logging.getLogger(__name__)


# ── Dispatcher ───────────────────────────────────────────────

def print_label(
    printer: GodexPrinter,
    label_def: LabelDef,
    data: LabelData,
    paper_w: int,
    paper_h: int,
    shift_l: int = 0,
    shift_t: int = 0,
    darkness: int = 12,
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
        print_l00(printer, bld, paper_width=paper_w, paper_height=paper_h, gap=label_def.gap,
                  shift_left=shift_l, shift_top=shift_t, darkness=darkness)
    elif code == "CP11":
        print_cp11(printer, data, paper_width=paper_w, paper_height=paper_h, gap=label_def.gap,
                   shift_l=shift_l, shift_t=shift_t, darkness=darkness)
    elif code == "CP19":
        print_cp19(printer, data, paper_width=paper_w, paper_height=paper_h, gap=label_def.gap,
                   shift_l=shift_l, shift_t=shift_t, darkness=darkness)
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

    def __init__(self, master: tk.Tk) -> None:
        super().__init__(master)
        self.title("標籤測試頁 (SampleData_Print)")
        self.geometry("580x580")
        self.resizable(False, False)

        # 子視窗 On-Top 且為 Modal
        self.transient(master)
        self.grab_set()

        # 從 master (App) 取得 local_db 與 session
        self._local_db = getattr(master, "local_db", None)
        self._session = getattr(master, "session", None)
        self._site_id = self._session.site_id if self._session else "S01"

        # 載入印表機清單（從 Local Cache；離線時保留最後一次可取得的清單）
        self._printers: list[dict] = []
        if self._local_db:
            self._printers = self._local_db.list_printers(self._site_id)

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

        # ── 印表機選擇（從 Local Cache 查表）──
        row += 1
        ttk.Label(frame, text="印表機:").grid(row=row, column=0, sticky="e",
                                              padx=(0, 8), pady=(8, 0))
        self.var_printer = tk.StringVar()
        printer_values = [f"{p['PRINTER_ID']}-{p['PRINTER_NAME']}"
                          for p in self._printers] if self._printers else ["（無可用印表機）"]
        self.cmb_printer = ttk.Combobox(frame, textvariable=self.var_printer,
                                        state="readonly", width=40, values=printer_values)
        self.cmb_printer.grid(row=row, column=1, sticky="w", pady=(8, 0))
        if printer_values:
            self.cmb_printer.current(0)

        # ── 按鈕 ──
        btn_frame = ttk.Frame(self)
        btn_frame.pack(pady=12)
        ttk.Button(btn_frame, text="列印",
                   command=self._on_print).pack(side="left", padx=8)

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

    def _get_selected_printer(self) -> dict | None:
        """取得目前選取的印表機 dict。"""
        sel = self.var_printer.get()
        if not sel or sel.startswith("（"):
            return None
        pid = sel.split("-", 1)[0]
        return next((p for p in self._printers if p["PRINTER_ID"] == pid), None)

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

    # ── Actions ──────────────────────────────────────────────

    def _on_print(self) -> None:
        """列印測試資料 — 走與 SRVLB001 相同的機制（POST localhost:9200）。

        將 Task 以 Status=2 送入本機 HTTP Listener，
        驗證整條列印通道是否暢通：HTTP → Listener → Queue → 印表機。
        """
        try:
            data = self._build_data()
            self._get_paper_size()  # 驗證紙張尺寸為合法數字（實際列印參數取自印表機設定）
            label_def = self._get_label_def()
        except ValueError as e:
            messagebox.showwarning("輸入錯誤", str(e))
            return

        printer = self._get_selected_printer()
        if not printer:
            messagebox.showwarning("輸入錯誤", "請選擇印表機")
            return

        # 組 Task payload（與 SRVLB001 Client 端送出格式一致）
        import uuid as _uuid
        import socket as _socket
        task_uuid = str(_uuid.uuid4())

        # 取本機 IP 作為列印者識別（測試頁無實際操作員）
        try:
            _s = _socket.socket(_socket.AF_INET, _socket.SOCK_DGRAM)
            _s.connect(("8.8.8.8", 80))
            local_ip = _s.getsockname()[0]
            _s.close()
        except OSError:
            local_ip = "127.0.0.1"

        payload = {
            "uuid": task_uuid,
            "bar_type": label_def.code,
            "site_id": self._site_id,
            "printer_id": printer["PRINTER_ID"],
            "specimen_no": "",
            "status": 2,  # 測試頁 → 直接進 Offline Queue（R12）
            "created_user": local_ip,  # 測試頁列印者標記為本機 IP
        }
        # 帶入 data_1~data_19
        for i, field in enumerate(["data_1", "data_2", "data_3", "data_4", "data_5",
                                    "data_6", "data_7", "data_8", "data_9", "data_10",
                                    "data_11", "data_12", "data_13", "data_14", "data_15",
                                    "data_16", "data_17", "data_18", "data_19"], start=1):
            val = getattr(data, field, None) if hasattr(data, field) else data.extras.get(f"data_{i}", "")
            payload[field] = val or ""

        # POST 到本機 Task Listener（與 SRVLB001 → Printer Server 相同路徑）
        import json as _json
        import urllib.request
        import urllib.error
        from task_listener import LISTENER_PORT

        url = f"http://localhost:{LISTENER_PORT}/api/lb/task"
        token = self._session.token if self._session else ""

        req = urllib.request.Request(
            url,
            data=_json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                result = _json.loads(resp.read().decode("utf-8"))
                if result.get("success"):
                    messagebox.showinfo("完成",
                        f"測試列印指令已送出\n\n"
                        f"標籤: {label_def.display}\n"
                        f"印表機: {printer['PRINTER_ID']}\n\n"
                        f"請至主畫面【離線等待重印項目 (Offline Queue)】\n"
                        f"選取該筆後執行列印")
                else:
                    messagebox.showerror("送出失敗", result.get("message", "未知錯誤"))

        except urllib.error.HTTPError as e:
            # Listener 有回應但 HTTP 錯誤（4xx/5xx）
            try:
                err_body = _json.loads(e.read().decode("utf-8"))
                msg = err_body.get("message", f"HTTP {e.code}")
            except Exception:
                msg = f"HTTP {e.code}"
            log.error("測試列印 Listener 回應錯誤: %s", msg)
            messagebox.showerror("Listener 處理錯誤",
                f"Task Listener 回應錯誤\n\n原因：{msg}")
        except urllib.error.URLError as e:
            messagebox.showerror("通道異常",
                f"無法連線至本機 Task Listener (port {LISTENER_PORT})\n\n"
                f"原因：{e.reason}\n\n"
                f"請確認 LBSB01 Task Listener 是否正常運作")
        except Exception as e:
            log.error("測試列印送出失敗: %s", e)
            messagebox.showerror("送出失敗", str(e))
