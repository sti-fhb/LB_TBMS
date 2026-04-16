"""
LBSB01 程式 icon — 主畫面 Title Bar 與系統匣共用。

使用 PIL 繪製一張高解析度印表機圖；
  - 系統匣：直接給 pystray 用 PIL.Image
  - 主畫面 title bar：轉為 tkinter PhotoImage（透過 ImageTk）
"""

from __future__ import annotations
from PIL import Image, ImageDraw


def make_app_icon(size: int = 64) -> Image.Image:
    """繪製桌上型印表機 icon（仿 GoDEX G500），高對比白底 + 深粗邊。

    size: 輸出正方形邊長（預設 64，系統匣縮小時仍清楚）。
    """
    # 高對比配色：純白機殼 + 深粗邊 + 亮藍上蓋 + 三色按鈕
    BODY = (255, 255, 255)
    TOP = (46, 134, 193)
    PAPER = (255, 255, 255)
    BORDER = (20, 30, 40)
    LED = (46, 204, 113)
    ACCENT = (211, 84, 0)
    GRAY = (200, 200, 200)

    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # 用 64x64 為基準座標，再按比例縮放
    def s(v: int) -> int:
        return round(v * size / 64)

    # 上方紙張
    d.rectangle((s(16), s(2), s(47), s(8)), fill=PAPER, outline=BORDER, width=max(1, s(2)))
    # 上蓋（亮藍梯形）
    d.polygon([(s(14), s(10)), (s(49), s(10)), (s(45), s(14)), (s(18), s(14))],
              fill=TOP, outline=BORDER)
    # 機殼主體
    d.rectangle((s(8), s(14), s(55), s(52)), fill=BODY, outline=BORDER, width=max(1, s(3)))
    # 紙張出口凹槽
    d.rectangle((s(12), s(32), s(51), s(42)), fill=PAPER, outline=BORDER, width=max(1, s(2)))
    # 控制面板按鈕
    d.ellipse((s(18), s(46), s(24), s(52)), fill=LED, outline=BORDER)
    d.ellipse((s(28), s(46), s(34), s(52)), fill=ACCENT, outline=BORDER)
    d.ellipse((s(38), s(46), s(44), s(52)), fill=GRAY, outline=BORDER)

    return img
