"""
標籤定義 — 對應 EA 代碼表「標籤類別」(Code: LB_TYPE)。

群組：CP（成分）、BC（檢驗）、BS（供應）、TL（檢驗檢體）
"""

from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class LabelDef:
    """單一標籤定義。"""
    code: str           # 標籤代碼（如 CP01, BS01）
    name: str           # 中文名稱
    width_mm: int       # 紙張寬度（mm）— EA TAG: WIDTH
    height_mm: int      # 紙張高度（mm）— EA TAG: LENGTH
    gap: int            # 標籤間隙（dots）
    group: str          # 群組（CP/BC/BS/TL）

    @property
    def display(self) -> str:
        """ComboBox 顯示文字。"""
        return f"{self.code}-{self.name}"

    @property
    def size_display(self) -> str:
        """尺寸顯示文字。"""
        return f"{self.width_mm}mm x {self.height_mm}mm"


# ── 全部 16 種標籤定義（依 EA 代碼表）──────────────────────────

LABEL_DEFS: list[LabelDef] = [
    # CP — 成分
    LabelDef("CP01", "血品小標籤",             80, 35,  3, "CP"),
    LabelDef("CP02", "血品小標籤A",            80, 35,  3, "CP"),
    LabelDef("CP11", "血品核對標籤-合格",       80, 75,  3, "CP"),
    LabelDef("CP12", "血品核對標籤-特殊標識",   80, 75,  2, "CP"),
    LabelDef("CP19", "血品核對標籤-不適輸用",   80, 75,  2, "CP"),
    LabelDef("CP91", "成分藍色籃號",            80, 35,  2, "CP"),
    LabelDef("CP92", "細菌小標籤",              45, 15,  2, "CP"),

    # BC — 檢驗
    LabelDef("BC01", "檢體小標籤",              45, 15,  2, "BC"),
    LabelDef("BC02", "187標籤",                 80, 35,  2, "BC"),

    # BS — 供應
    LabelDef("BS01", "運送器材借用標籤",        80, 75,  2, "BS"),
    LabelDef("BS02", "運送器材條碼",            80, 35,  2, "BS"),
    LabelDef("BS03", "血品裝箱大標籤",         100, 200, 3, "BS"),
    LabelDef("BS04", "供應籃號標籤",            80, 75,  2, "BS"),
    LabelDef("BS05", "供應特殊血品標籤",        80, 75,  2, "BS"),
    LabelDef("BS07", "血品裝箱小標籤",          80, 35,  2, "BS"),

    # TL — 檢驗檢體
    LabelDef("TL01", "檢驗檢體標籤",            45, 15,  2, "TL"),
]

# 快速查找 dict
LABEL_MAP: dict[str, LabelDef] = {d.code: d for d in LABEL_DEFS}

# 不重複的尺寸清單（用於尺寸 ComboBox）
PAPER_SIZES: list[tuple[int, int]] = sorted(
    set((d.width_mm, d.height_mm) for d in LABEL_DEFS)
)

# 群組清單
LABEL_GROUPS: list[str] = sorted(set(d.group for d in LABEL_DEFS))
