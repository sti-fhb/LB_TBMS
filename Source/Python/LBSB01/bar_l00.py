"""
Bar_L00 — 血品小條碼標籤佈局。

對應 VB6 M_ALLB01.bas 的 Bar_L00() 函式。
透過 GodexPrinter 呼叫 DLL 函式（USB）或產生 EZPL 指令（TCP/FILE）。
"""

from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime

from ezpl import GodexPrinter


# VB6 字型名稱對照
FONT_0 = "Arial"       # sFont0
FONT_2 = "Arial"       # sFont2
FONT_B = "Arial"       # sFontB（粗體用疊印模擬）
FONT_TB = "Arial"      # sFontTB


@dataclass
class BloodLabelData:
    """Bar_L00 所需的血品資料欄位（對應 VB6 Lr_RS1 recordset）。"""

    bag_type: str       # iType  — 標籤類型（"L00" 或 "L00A"）
    bag_no: str         # BB_BAGNO — 血袋編號
    data_1: str         # DATA_1  — 條碼資料（捐血編號 / DIN）
    data_3: str         # DATA_3  — 日期時間（原始格式）
    data_4: str         # Data_4  — 特殊旗標（"1" = 特殊）
    data_5: str         # Data_5  — 血型 Rh（如 "+" / "-"）
    data_6: str         # DATA_6  — 血品名稱
    data_7: str         # Data_7  — 血型 ABO（如 "AB"）
    data_8: str         # Data_8  — 附加資訊 1
    data_10: str        # Data_10 — 附加資訊 2
    data_11: str        # Data_11 — 附加資訊 3
    data_12: str        # Data_12 — 6 個月保存旗標
    data_19: str        # Data_19 — 血品類別代碼


def print_l00(
    printer: GodexPrinter,
    data: BloodLabelData,
    paper_width: int = 80,
    paper_height: int = 35,
    gap: int = 3,
    shift_left: int = 0,
    shift_top: int = 0,
) -> None:
    """
    透過 GodexPrinter 列印 L00（血品小條碼）標籤。

    對應 VB6 流程：
      LabelSetup → JobStart → Bar_L00 → JobEnd
    """
    # ── Label Setup（寬/高/gap 由呼叫端帶入，不寫死）──
    printer.label_setup(
        width=paper_width, height=paper_height,
        gap=gap, darkness=12, speed=2,
    )

    # ── Job Start ──
    printer.job_start()

    bx = 10 + shift_left
    by = 25 + shift_top
    py = by

    # CP02 = 舊 L00A（A 版），CP01 = 舊 L00（標準版）
    is_type_a = data.bag_type in ("CP02", "L00A")

    # ── 日期格式 ──
    d3 = _format_date(data.data_3, date_only=is_type_a)

    # ── L00A：先印血袋編號 + 條碼 ──
    if is_type_a:
        printer.text_out(bx, py + 8, 60, FONT_0, data.bag_no)
        printer.barcode("Q", bx + 489, py, narrow=3, wide=2, height=80,
                        rotation=0, readable=0, data=data.bag_no)
        py += 90

    # ── 血型行：D7-D5（如 "AB-+"）──
    d7_display = f"{data.data_7}-{data.data_5}"
    printer.text_out(bx, py + 20, 70, FONT_2, d7_display)

    # ── 捐血編號條碼（DATA_1）──
    printer.barcode("Q", bx + 150, py, narrow=2, wide=1, height=90,
                    rotation=0, readable=1, data=data.data_1)

    py += 125

    # ── 血袋編號（粗體）──
    printer.text_out_bold(bx, py, 60, FONT_B, data.bag_no)

    py += 45

    # ── 類別 + 日期 ──
    type_line = f"Type~:{data.data_19}"

    if is_type_a:
        py += 10
        printer.text_out(bx, py, 58, FONT_TB, type_line)
    else:
        py += 20
        printer.text_out(bx, py, 58, FONT_TB, type_line)
        if d3:
            printer.text_out(bx + 300, py, 58, FONT_TB, d3)

    # ── 附加資訊行 ──
    if is_type_a:
        special = "[Special]," if data.data_4 == "1" else ""
        info_line = f"{special}{data.data_6}"
        printer.text_out(bx, py + 48, 48, FONT_0, info_line)
    else:
        parts: list[str] = []
        if data.data_8:
            parts.append(data.data_8)
        if data.data_4 == "1":
            parts.append("[Special]")
        if data.data_6:
            parts.append(data.data_6)

        info_line = ",".join(parts)
        printer.text_out(bx, py + 48, 48, FONT_0, info_line)

        # D10 + D11
        extra_parts: list[str] = []
        if data.data_10:
            extra_parts.append(data.data_10)
        if data.data_11:
            extra_parts.append(data.data_11)
        if extra_parts:
            extra_line = ",".join(extra_parts)
            printer.text_out(bx, py + 96, 48, FONT_0, extra_line)

    # ── Job End ──
    printer.job_end()


def _format_date(raw: str, date_only: bool = False) -> str:
    """格式化日期字串。"""
    if not raw:
        return ""
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        return raw
    if date_only:
        return dt.strftime("%Y/%m/%d")
    return dt.strftime("%Y/%m/%d %H:%M:%S")
