"""
Bar_CP11 — 血品核對標籤-合格（舊 L01 / Bar_L01_300DPI）。

完整移植 VB6 Bar_L01_300DPI()，含 7 個子函式。
字型對照：
  sFont0  = 標楷體
  sFont1  = 細明體
  sFontB  = Arial Black
  sFontS  = Arial Rounded MT Bold  (Rh+ 實心血型)
  sFontEpt = Swis721 BdOul BT       (Rh- 空心血型)
"""

from __future__ import annotations
import os
from sample_data import LabelData
from ezpl import GodexPrinter

# ── 字型常數 ─────────────────────────────────────────────────
FONT_0 = "標楷體"
FONT_1 = "細明體"
FONT_B = "Arial Black"
FONT_S = "Arial Rounded MT Bold"    # Rh+ 實心
FONT_EPT = "Swis721 BdOul BT"       # Rh- 空心

# images 目錄（相對於本檔）
_IMG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "images")


def print_cp11(
    printer: GodexPrinter,
    data: LabelData,
    paper_width: int = 80,
    paper_height: int = 75,
    gap: int = 3,
    shift_l: int = 0,
    shift_t: int = 0,
    darkness: int = 12,
) -> None:
    """
    列印 CP11 — 血品核對標籤-合格。

    對應 VB6 Bar_L01_300DPI(rs1)。
    """
    printer.label_setup(width=paper_width, height=paper_height,
                        gap=gap, darkness=darkness, speed=2)
    printer.job_start()

    base_x = 10 + shift_l
    base_y = 45 + shift_t
    base_x1 = 470 + base_x
    base_xt = base_x + 40
    iby = base_y + 112

    # ══════════════════════════════════════════════════════════
    # 血袋號（左側條碼 + 文字）
    # ══════════════════════════════════════════════════════════
    a = data.data_1
    printer.barcode("Q", base_x, base_y, 4, 4, 80, 0, 0, a)
    printer.text_out(base_xt + 20, base_y + 85, 46, FONT_0, a)

    # ══════════════════════════════════════════════════════════
    # 相關血袋號（右側條碼 + 文字）
    # ══════════════════════════════════════════════════════════
    a = data.data_2
    if a:
        printer.barcode("Q", base_x1, base_y, 4, 4, 80, 0, 0, a)
        printer.text_out(base_x1 + 57, base_y + 85, 46, FONT_0, a)

    # ══════════════════════════════════════════════════════════
    # 血品3碼名稱（旋轉文字，含「減」字加底線）
    # ══════════════════════════════════════════════════════════
    a = _replace_prd_name(data.data_4)
    if a:
        a_len = ((len(a) * 375) * 4) // 1000
        a_ln = 18 - a_len + 18

        if "Recovered plasma" in a:
            printer.text_out_r(base_x, base_y + 131 - 17, 90, FONT_B, a,
                               width=22, weight=900, degree=0)
        else:
            printer.text_out_r(base_x, base_y + 131, 66, FONT_1, a,
                               width=a_ln, weight=900, degree=0)

        # 「減」字加底線
        if "減" in a:
            a_ln1 = (len(a) * 2083 * a_ln) // 1000
            printer.draw_hor_line(base_x, base_y + 198, a_ln1, 4)

    # ══════════════════════════════════════════════════════════
    # 血品3碼條碼
    # ══════════════════════════════════════════════════════════
    a = data.data_3
    if a:
        printer.barcode("Q", base_x, base_y + 210, 4, 4, 70, 0, 0, a)

    ibx = base_x1 + 85
    shx = 0
    b_font_size = 180
    b_font_shift_x = b_font_size // 6 - 18

    # ══════════════════════════════════════════════════════════
    # 生物危害標誌（DATA_14 = "1"）
    # ══════════════════════════════════════════════════════════
    if data.data_14 == "1":
        img_path = os.path.join(_IMG_DIR, "biomedical-50.JPG")
        printer.put_image(ibx + 170, iby + 10, img_path)

    # ══════════════════════════════════════════════════════════
    # 自體捐血（DATA_15 = "1"）
    # ══════════════════════════════════════════════════════════
    if data.data_15 == "1":
        for idx, ch in enumerate("自體捐血"):
            printer.text_out(ibx + 215, iby + 130 + idx * 50, 50, FONT_0, ch)

    # ══════════════════════════════════════════════════════════
    # 血型大字（180pt）— Rh+ 實心 / Rh- 空心
    # ══════════════════════════════════════════════════════════
    a = data.data_5 or ""
    blood_printed = False

    if "AB-" in a:
        printer.text_out(ibx - 48 - b_font_shift_x, iby, b_font_size, FONT_EPT, "AB")
        shx = -25
        blood_printed = True
    elif "AB+" in a:
        printer.text_out(ibx - 48 - b_font_shift_x, iby, b_font_size, FONT_S, "AB")
        shx = -25
        blood_printed = True
    elif "A-" in a:
        printer.text_out(ibx - b_font_shift_x, iby, b_font_size, FONT_EPT, "A")
        blood_printed = True
    elif "B-" in a:
        printer.text_out(ibx - b_font_shift_x, iby, b_font_size, FONT_EPT, "B")
        blood_printed = True
    elif "O-" in a:
        printer.text_out(ibx - b_font_shift_x, iby, b_font_size, FONT_EPT, "O")
        blood_printed = True
    elif "A+" in a:
        printer.text_out(ibx - b_font_shift_x, iby, b_font_size, FONT_S, "A")
        blood_printed = True
    elif "B+" in a:
        printer.text_out(ibx - b_font_shift_x, iby, b_font_size, FONT_S, "B")
        blood_printed = True
    elif "O+" in a:
        printer.text_out(ibx - b_font_shift_x, iby, b_font_size, FONT_S, "O")
        blood_printed = True

    # Rh D 陽性/陰性
    if blood_printed and a:
        if "-" in a:
            printer.text_out_fine(ibx - 70, iby + 93 + b_font_size // 3, 60, FONT_0,
                                  "Rh D 陰性", width=26, weight=80, inverse=1)
        else:
            printer.text_out_fine(ibx - 35, iby + 93 + b_font_size // 3, 60, FONT_0,
                                  "Rh D 陽性", width=26, weight=80)

    # 血型條碼
    iby = iby + 158 + b_font_size // 3
    if blood_printed and a:
        printer.barcode("Q", ibx - 35 + shx, iby, 3, 3, 80, 0, 0, a)

    iby = iby + 85
    if blood_printed and a:
        printer.text_out(ibx + 33, iby, 36, FONT_0, a)

    iy_set = 190

    # ══════════════════════════════════════════════════════════
    # 採血日期 / 製備日期（二取一）
    # ══════════════════════════════════════════════════════════
    if data.data_9:
        _bar_donor_date(printer, data.data_9, base_x1, 305 + iy_set + shift_t)
    elif data.data_17:
        _bar_cp_prd_date(printer, data.data_17, base_x1, 305 + iy_set + shift_t)

    # ══════════════════════════════════════════════════════════
    # 有效期限
    # ══════════════════════════════════════════════════════════
    if data.data_10:
        _bar_lim_date(printer, data.data_10, base_x1, 342 + iy_set + 10 + shift_t)

    # ══════════════════════════════════════════════════════════
    # 注意事項（DATA_11，\n 分行）
    # ══════════════════════════════════════════════════════════
    x_count = 0
    if data.data_11:
        lines = data.data_11.split("\\n")
        for x_count, line in enumerate(lines):
            cur_y = base_y + 290 + x_count * 28
            printer.text_out(base_x, cur_y, 28, FONT_0, line)

    # DATA_11 結束後的 iby（供 DATA_12 接續用）
    iby_after_notes = base_y + 290 + x_count * 28 + 10 if data.data_11 else base_y + 290

    # ══════════════════════════════════════════════════════════
    # 補充說明（DATA_12，\n 分行，接在 DATA_11 之後）
    # ══════════════════════════════════════════════════════════
    if data.data_12:
        lines12 = data.data_12.split("\\n")
        for y_idx, line in enumerate(lines12):
            printer.text_out(base_x - 10, iby_after_notes + y_idx * 26, 26, FONT_0, line)

    # ══════════════════════════════════════════════════════════
    # 以下區塊用【絕對 Y 座標】，不隨 DATA_11/12 行數浮動
    # VB6: iYset = BaseY + 190 + 15 = 250
    # ══════════════════════════════════════════════════════════
    iy_abs = base_y + 190 + 15  # = 250

    # 地址（DATA_13，含 Logo 圖片）— VB6: IBY = 427 + iYset = 677
    if data.data_13:
        _bar_address(printer, data.data_13, base_x, 427 + iy_abs - 2)

    # 抗原名稱（DATA_8）— VB6: iBy1 = BaseY + 622 = 667
    if data.data_8:
        iby_anti = base_y + 622
        _bar_anti(printer, base_x1, iby_anti, data.data_8, 34, 18, 2, 320)

    # 橫線分隔 — VB6: IBY(=677) + 60 = 737
    iby_sep = 427 + iy_abs + 60  # = 737
    printer.draw_hor_line(base_x - 3, iby_sep, 875, 2)
    iby_sep += 10  # = 747

    # ISBT DIN13（DATA_6）
    if data.data_6:
        din = data.data_6[:13]
        flag = data.data_6[13:15] if len(data.data_6) > 13 else ""
        chk = data.data_6[-1:] if len(data.data_6) > 15 else ""
        _bar_isbt_din13(printer, base_x, iby_sep, din, flag, chk)

    # ISBT PD5（DATA_7）
    if data.data_7:
        _bar_isbt_pd5(printer, base_x1 + 78, iby_sep, data.data_7)

    printer.job_end()


# ═══════════════════════════════════════════════════════════════
#  子函式
# ═══════════════════════════════════════════════════════════════

def _replace_prd_name(name: str) -> str:
    """對應 VB6 Replace_PRD_NAME()。"""
    if not name:
        return name
    name = name.replace("洗滌紅血球", "洗滌紅血球濃厚液")
    name = name.replace("減白分離術血小板", "減除白血球之分離術血小板")
    return name


def _bar_donor_date(printer: GodexPrinter, s_data: str, x: int, y: int) -> None:
    """對應 VB6 BAR_DonerDATE()。"""
    printer.text_out_r(x, y, 54, FONT_0, f"供血者日期:{s_data}",
                       width=20, weight=990, degree=0)


def _bar_cp_prd_date(printer: GodexPrinter, s_data: str, x: int, y: int) -> None:
    """對應 VB6 BAR_CP_PRD_DATE()。"""
    printer.text_out_r(x, y, 54, FONT_0, f"成分到期日:{s_data}",
                       width=20, weight=990, degree=0)


def _bar_lim_date(printer: GodexPrinter, s_data: str, x: int, y: int) -> None:
    """對應 VB6 BAR_LimDate()。"""
    if not s_data or s_data.startswith("9999"):
        return
    printer.text_out_r(x, y, 54, FONT_0, f"保存截止日:{s_data}",
                       width=20, weight=900, degree=0)
    printer.barcode("Q", x, y + 55, 2, 2, 70, 0, 0, s_data)


def _bar_address(printer: GodexPrinter, s_data: str, x: int, y: int) -> None:
    """對應 VB6 Bar_Address()。含 Logo 圖片。"""
    logo_path = os.path.join(_IMG_DIR, "Logo-18.jpg")
    printer.put_image(x, y, logo_path)

    lines = s_data.split("\\n")
    for i, line in enumerate(lines):
        printer.text_out_fine(x + 49, y + i * 28, 28, FONT_0, line,
                              width=11, weight=0)


def _bar_anti(
    printer: GodexPrinter,
    ix: int, iy: int, s_anti: str,
    text_h: int, text_w: int, x_gap: int, x_limit: int,
) -> None:
    """
    對應 VB6 Bar_Anti()。
    抗原名稱組合，每 7 碼一組，等級 >1 用粗體。
    """
    if not s_anti or len(s_anti) % 7 != 0:
        return

    if text_h > 50:
        i_fac_x = 42
        i_fac_y = 60
    else:
        i_fac_x = 26
        i_fac_y = 32

    offset_x = 0

    while len(s_anti) >= 7:
        chunk = s_anti[:7]
        s_anti = s_anti[7:]

        iv = int(chunk[6]) if chunk[6].isdigit() else 0
        b = chunk[:5].rstrip() + chunk[5]

        if iv > 1:
            # 粗體（等級 >1）
            i_fplus = 0
            iy_plus = 0
            if b.rstrip() in ("e-", "e+"):
                i_fplus = 12
                iy_plus = -8

            printer.text_out_fine(ix + offset_x, iy + iy_plus,
                                  text_h + 4 + i_fplus, FONT_B, b,
                                  width=text_w)
        else:
            printer.text_out_fine(ix + offset_x, iy,
                                  text_h, "Arial", b,
                                  width=text_w)

        offset_x += i_fac_x * len(b)

        # 特殊字元間距調整
        b_key = b.rstrip()
        if b_key in ("c-", "E-", "e-"):
            offset_x -= 6
        if b_key in ("Jka-", "Jka+", "Mia-", "Mia+"):
            offset_x -= 12
        if iv <= 1:
            if b_key in ("M+", "C+"):
                offset_x += 9
            if b_key in ("Jka+", "Jka-", "Jkb+", "Jkb-"):
                offset_x -= 9
            if b_key in ("Mia-", "Mia+"):
                offset_x -= 12

        if offset_x > x_limit:
            iy += i_fac_y
            offset_x = 0


def _bar_isbt_din13(
    printer: GodexPrinter,
    ix: int, iy: int,
    s_din: str, s_flag: str, s_chk: str,
) -> None:
    """對應 VB6 Bar_ISBT_DIN13()。"""
    s_leading = "="
    shift_y = 10
    ix1 = ix + 30

    # DIN13 條碼（含 leading "=" 和 flag）
    printer.barcode("Q", ix, iy, 3, 3, 80, 0, 0, f"{s_leading}{s_din}{s_flag}")

    # DIN 文字
    printer.text_out(ix1, iy + 77 + shift_y, 45, FONT_0, s_din)

    # Flag（旋轉 90°）
    if s_flag:
        printer.text_out_fine(ix1 + 275 + 23, iy + 78 + 4 + shift_y, 38, FONT_0,
                              s_flag, width=16, weight=80, degree=90)
        # Flag 外框
        printer.draw_rec(ix1 + 315 + 20, iy + 75 + 4 + shift_y, 28, 38, 2, 2)

    # Check digit
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
