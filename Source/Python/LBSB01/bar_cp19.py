"""
bar_cp19 — CP19 血品核對標籤-不適輸用（舊 L09）佈局。

移植自 VB6 BAR_L09_300DPI()。
標籤尺寸 80mm x 75mm。
"""

from __future__ import annotations
import os

from sample_data import LabelData
from ezpl import GodexPrinter

# ── 字型 ────────────────────────────────────────────────────────
FONT_0 = "標楷體"

# ── 圖片目錄 ────────────────────────────────────────────────────
_IMG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "images")


def print_cp19(
    printer: GodexPrinter,
    data: LabelData,
    *,
    paper_width: int = 80,
    paper_height: int = 75,
    gap: int = 2,
    shift_l: int = 0,
    shift_t: int = 0,
    darkness: int = 12,
) -> None:
    """列印 CP19 血品核對標籤-不適輸用。對應 VB6 BAR_L09_300DPI()。"""

    printer.label_setup(paper_width, paper_height, gap, darkness=darkness, speed=2)
    printer.job_start()

    base_x = shift_l
    base_y = 10 + shift_t
    if base_x < 0:
        base_x = 0

    iby = 15 + shift_t
    iby2 = 15 + shift_t // 2  # 主位移微調
    iby1 = 450 + base_y
    base_x11 = 420 + shift_l

    # ── 採血日期（Data_9）─────────────────────────────────────
    a = data.data_9 or ""
    if a:
        printer.text_out(base_x, 200 + shift_t, 46, FONT_0, "採血日期:")
        printer.text_out(base_x, 200 + 55 + shift_t, 46, FONT_0, a)

    # ── 生物危害標誌 ─────────────────────────────────────────
    if iby2 < 0:
        iby2 = 0
    img_path = os.path.join(_IMG_DIR, "biomedical-25.JPG")
    if os.path.exists(img_path):
        printer.put_image(480 + shift_l, iby2, img_path)

    # ── 分隔線 ───────────────────────────────────────────────
    # 水平線（標籤下方）
    printer.draw_hor_line(1, 445 + shift_t, 950, 3)
    # 垂直線（左右分隔）
    gl_shift_l0 = shift_l
    printer.draw_ver_line(455 + gl_shift_l0, 0, 950, 3)

    # ── 標籤上方左半：Data_16 多行文字 ───────────────────────
    a = data.data_16 or ""
    if a:
        lines = a.split("\\n")
        for x, line in enumerate(lines):
            printer.text_out(base_x, iby1 + x * 44, 44, FONT_0, line)

    # ── 標籤上方右半：Data_4 血品名稱（自動換行）────────────
    a = data.data_4 or ""
    if a:
        _l1l_print(printer, a, base_x11 + 65, iby1, 18, 18, 48)

    # ── 標籤上方右半：Data_12 多行文字 ───────────────────────
    a = data.data_12 or ""
    if a:
        # py 由 _l1l_print 回傳的結束 Y 座標
        py = _l1l_print_py
        lines = a.split("\\n")
        for x, line in enumerate(lines):
            printer.text_out(base_x11 + 65, py + x * 44, 44, FONT_0, line)

    # ── 地址（Data_13）─────────────────────────────────────
    iyset = 235 + shift_t
    data_13 = data.data_13 or ""
    if data_13:
        _bar_address(printer, data_13, base_x, 440 + iyset)

    # ── ISBT DIN13（Data_6）─────────────────────────────────
    data_6 = data.data_6 or ""
    if data_6:
        din = data_6[:13]
        flag = data_6[13:15] if len(data_6) > 13 else ""
        chk = data_6[-1:] if len(data_6) > 15 else ""
        _bar_isbt_din13(printer, base_x, 503 + iyset, din, flag, chk)

    # ── ISBT PD5（Data_7）──────────────────────────────────
    data_7 = data.data_7 or ""
    if data_7:
        _bar_isbt_pd5(printer, base_x11 + 45, 503 + iyset, data_7)

    printer.job_end()


# ═══════════════════════════════════════════════════════════════
#  子函式
# ═══════════════════════════════════════════════════════════════

# 模組層級變數，供 _l1l_print 回傳結束 Y 座標
_l1l_print_py = 0


def _l1l_print(
    printer: GodexPrinter,
    text: str, bx: int, by: int,
    l1l: int, l2l: int, font_h: int,
) -> None:
    """對應 VB6 L1L_PRINT()。自動換行列印。

    l1l: 第一行最大字數
    l2l: 後續行最大字數
    font_h: 字型大小
    """
    global _l1l_print_py
    py = by
    line_h = font_h + 3
    ix = 0

    while text:
        max_chars = l1l if ix == 0 else l2l
        line = text[:max_chars]
        text = text[max_chars:]
        if ix > 0:
            py += line_h
        printer.text_out(bx, py, font_h, FONT_0, line)
        ix += 1

    py += line_h
    _l1l_print_py = py


def _bar_address(printer: GodexPrinter, s_data: str, x: int, y: int) -> None:
    """對應 VB6 Bar_Address()。含 Logo 圖片。"""
    logo_path = os.path.join(_IMG_DIR, "Logo-18.jpg")
    if os.path.exists(logo_path):
        printer.put_image(x, y, logo_path)

    lines = s_data.split("\\n")
    for i, line in enumerate(lines):
        printer.text_out_fine(x + 49, y + i * 28, 28, FONT_0, line,
                              width=11, weight=0)


def _bar_isbt_din13(
    printer: GodexPrinter,
    ix: int, iy: int,
    s_din: str, s_flag: str, s_chk: str,
) -> None:
    """對應 VB6 Bar_ISBT_DIN13()。"""
    s_leading = "="
    shift_y = 10
    ix1 = ix + 30

    printer.barcode("Q", ix, iy, 3, 3, 80, 0, 0, f"{s_leading}{s_din}{s_flag}")
    printer.text_out(ix1, iy + 77 + shift_y, 45, FONT_0, s_din)

    if s_flag:
        printer.text_out_fine(ix1 + 275 + 23, iy + 78 + 4 + shift_y, 38, FONT_0,
                              s_flag, width=16, weight=80, degree=90)
        printer.draw_rec(ix1 + 315 + 20, iy + 75 + 4 + shift_y, 28, 38, 2, 2)

    if s_chk:
        printer.text_out(ix1 + 340, iy + 75 + 4 + shift_y, 41, FONT_0, s_chk)


def _bar_isbt_pd5(
    printer: GodexPrinter,
    ix: int, iy: int, s_pd: str,
) -> None:
    """對應 VB6 Bar_ISBT_PD5()。"""
    s_leading = "=<"
    ix = ix - 15

    printer.barcode("Q", ix + 50, iy, 2, 2, 80, 0, 0, f"{s_leading}{s_pd}")
    printer.text_out(ix + 100, iy + 87, 45, FONT_0, s_pd)
