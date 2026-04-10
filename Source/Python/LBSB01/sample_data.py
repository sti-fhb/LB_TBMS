"""
各標籤類型的測試資料。

依 EA 代碼表「標籤類別」(LB_TYPE) 16 筆標籤，
建構合理的測試資料供 Demo 列印。
"""

from __future__ import annotations
from dataclasses import dataclass


@dataclass
class LabelData:
    """通用標籤資料（對應 VB6 BMS_QC_BARCODE recordset）。"""
    label_type: str = ""
    bag_no: str = ""
    data_1: str = ""
    data_2: str = ""
    data_3: str = ""
    data_4: str = ""
    data_5: str = ""
    data_6: str = ""
    data_7: str = ""
    data_8: str = ""
    data_9: str = ""
    data_10: str = ""
    data_11: str = ""
    data_12: str = ""
    data_13: str = ""
    data_14: str = ""
    data_15: str = ""
    data_16: str = ""
    data_17: str = ""
    data_18: str = ""
    data_19: str = ""


def build_sample(label_code: str, bag_no: str = "TW2024050001") -> LabelData:
    """依標籤代碼產生對應的測試資料。"""
    builder = _SAMPLE_BUILDERS.get(label_code, _default_sample)
    return builder(label_code, bag_no)


# ── CP 群組 ──────────────────────────────────────────────────

def _sample_cp01(code: str, bag_no: str) -> LabelData:
    """CP01 — 血品小標籤（舊 L00）。"""
    return LabelData(
        label_type=code,
        bag_no=bag_no,
        data_1=f"{bag_no}|18721|20180207|01|1|S",
        data_3="2018/02/07 10:11:12",
        data_4="1",
        data_5="+",
        data_6="分離",
        data_7="O",
        data_8="MCS",
        data_10="M33",
        data_11="0607A6999",
        data_12="1",
        data_19="18721",
    )


def _sample_cp02(code: str, bag_no: str) -> LabelData:
    """CP02 — 血品小標籤A（舊 L00A）。"""
    return LabelData(
        label_type=code,
        bag_no=bag_no,
        data_1=f"{bag_no}|18721|20180207|01|1|S",
        data_3="2018/02/07",
        data_4="1",
        data_5="+",
        data_6="分離",
        data_7="O",
        data_8="MCS",
        data_10="M33",
        data_11="0607A6999",
        data_12="",
        data_19="18721",
    )


def _sample_cp11(code: str, bag_no: str) -> LabelData:
    """CP11 — 血品核對標籤-合格（舊 L01）。
    對應 VB6 Bar_L01_300DPI 使用的全部欄位。
    Sample data 取自 SPEC1.jpg 實際標籤內容。
    """
    return LabelData(
        label_type=code,
        bag_no=bag_no,
        data_1="0822505751",                   # 血袋號（左側條碼）
        data_2="0883305737",                   # 相關血袋號（右側條碼）
        data_3="05001",                        # 血品3碼（條碼）
        data_4="紅血球濃厚液",                  # 血品名稱（旋轉文字）
        data_5="AB-",                          # 血型（AB 空心字 + Rh D 陰性反白）
        data_6="T88661921675600D",             # ISBT DIN13(13碼) + Flag(2碼) + Check(1碼)
        data_7="E0212V00",                     # ISBT PD5
        data_8="Mia  -2C    +2c    -1E    -2e    +1M    +2Jka  +1Jkb  -2",  # 抗原（每7碼一組，9組63字元）
        data_9="2019/07/21",                   # 採血日期
        data_10="2019/08/25",                  # 保存截止日
        data_11="注意事項：\\n1.於2~6℃冷藏貯存。\\n2.總重量約250公克。\\n3.抗凝血劑名稱:CPDA-1。\\n4.本血品係由500mL全血分離，\\n僅供輸血使用。\\n5.捐血人未經特殊免疫處理。\\n6.檢驗項目HBV、HCV、HIV、HTLV等\\n病毒之檢驗結果為陰性。",
        data_12="本血品含有3.0E+11個血小板。\\n抗凝血劑: ACD-A",
        data_13="台灣血液基金會台北捐血中心\\n地址:台北市北投區立德路123號",
        data_14="1",                           # 生物危害標誌（1=顯示）
        data_15="1",                           # 自體捐血（1=顯示）
        data_17="",                            # 製備日期（採血日期優先時留空）
        data_19="18721",
    )


def _sample_cp12(code: str, bag_no: str) -> LabelData:
    """CP12 — 血品核對標籤-特殊標識（舊 L02）。"""
    return LabelData(
        label_type=code,
        bag_no=bag_no,
        data_1=f"{bag_no}|18721|20180207|01|1|S",
        data_2="洗滌紅血球濃厚液",
        data_3="05002",
        data_4="洗滌紅血球濃厚液",
        data_5="250",
        data_6="2018/08/07",
        data_7="05002V00",
        data_8="A",
        data_9="-",
        data_10="CPDA-1",
        data_17="特殊處理",
        data_19="18721",
    )


def _sample_cp19(code: str, bag_no: str) -> LabelData:
    """CP19 — 血品核對標籤-不適輸用（舊 L09）。

    對應 VB6 BAR_L09_300DPI 使用的欄位：
      Data_9  = 採血日期（標籤左上方）
      Data_16 = 左半文字（多行，\\n 分隔）
      Data_4  = 血品名稱（右半，自動換行）
      Data_12 = 右半文字（多行，\\n 分隔）
      Data_13 = 地址（含 Logo）
      Data_6  = ISBT DIN13（13碼+Flag2碼+Check1碼）
      Data_7  = ISBT PD5
    """
    return LabelData(
        label_type=code,
        bag_no=bag_no,
        data_4="FFP from WB52 in 8hrs 新鮮冷凍血漿",  # 血品名稱
        data_6="T88661921675600D",                     # ISBT DIN13(13) + Flag(2) + Check(1)
        data_7="E0212V00",                             # ISBT PD5
        data_9="2019/07/21",                              # 採血日期
        data_12="本血品含有3.0E+11個血小板。\\n抗凝血劑: ACD-A",  # 右半文字
        data_13="台灣血液基金會台北捐血中心\\n地址:台北市北投區立德路123號",  # 地址
        data_16="不適輸用\\nHBsAg 檢驗陽性",            # 左半文字
        data_19="18721",
    )


def _sample_cp91(code: str, bag_no: str) -> LabelData:
    """CP91 — 成分藍色籃號（舊 CP01）。"""
    return LabelData(
        label_type=code,
        bag_no=bag_no,
        data_1=f"{bag_no}|CP91",
        data_2="成分處理",
        data_3="籃號-C01",
    )


def _sample_cp92(code: str, bag_no: str) -> LabelData:
    """CP92 — 細菌小標籤（舊 BC03）。"""
    return LabelData(
        label_type=code,
        bag_no=bag_no,
        data_1=f"{bag_no}|18721",
    )


# ── BC 群組 ──────────────────────────────────────────────────

def _sample_bc(code: str, bag_no: str) -> LabelData:
    """BC01/BC02 — 檢體標籤。"""
    return LabelData(
        label_type=code,
        bag_no=bag_no,
        data_1=f"{bag_no}|18721",
    )


# ── BS 群組 ──────────────────────────────────────────────────

def _sample_bs01(code: str, bag_no: str) -> LabelData:
    """BS01 — 運送器材借用標籤。"""
    return LabelData(
        label_type=code,
        data_1="BOX-2024-001",
        data_2="冷藏運送箱",
        data_3="台北捐血中心",
        data_4="三軍總醫院",
        data_5="2024/05/15 08:30",
        data_6="紅血球×5, 血小板×2",
    )


def _sample_bs02(code: str, bag_no: str) -> LabelData:
    """BS02 — 運送器材條碼。"""
    return LabelData(
        label_type=code,
        bag_no=bag_no,
        data_1="TRANS-20240515-001",
        data_2="冷藏箱 #12",
    )


def _sample_bs03(code: str, bag_no: str) -> LabelData:
    """BS03 — 血品裝箱大標籤 (100x200mm)。"""
    return LabelData(
        label_type=code,
        bag_no=bag_no,
        data_1="SHIP-20240515-001",
        data_2="台北捐血中心",
        data_3="三軍總醫院血庫",
        data_4="紅血球濃厚液 O+ ×10",
        data_5="2024/05/15",
        data_6="冷藏 2-6°C",
        data_7="緊急",
    )


def _sample_bs04(code: str, bag_no: str) -> LabelData:
    """BS04 — 供應籃號標籤。"""
    return LabelData(
        label_type=code,
        data_1="BASKET-A01",
        data_2="O型 Rh+",
        data_3="紅血球區",
        data_5="12",
    )


def _sample_bs05(code: str, bag_no: str) -> LabelData:
    """BS05 — 供應特殊血品標籤。"""
    return LabelData(
        label_type=code,
        bag_no=bag_no,
        data_1=f"{bag_no}|BS05",
        data_2="減除白血球之分離術血小板",
        data_3="05010",
        data_4="特殊血品",
        data_5="250",
        data_6="2024/05/20",
        data_7="05010V00",
        data_8="AB",
    )


def _sample_bs07(code: str, bag_no: str) -> LabelData:
    """BS07 — 血品裝箱小標籤。"""
    return LabelData(
        label_type=code,
        bag_no=bag_no,
        data_1=f"{bag_no}|BOX-S",
        data_3="2024/05/15",
    )


# ── TL 群組 ──────────────────────────────────────────────────

def _sample_tl01(code: str, bag_no: str) -> LabelData:
    """TL01 — 檢驗檢體標籤。"""
    return LabelData(
        label_type=code,
        bag_no=bag_no,
        data_1=f"{bag_no}|TL|20180207",
    )


# ── Default ──────────────────────────────────────────────────

def _default_sample(code: str, bag_no: str) -> LabelData:
    """未特別定義 → 基本資料。"""
    return LabelData(
        label_type=code,
        bag_no=bag_no,
        data_1=f"{bag_no}|{code}|SAMPLE",
    )


# ── 對照表 ──

_SAMPLE_BUILDERS: dict[str, callable] = {
    # CP
    "CP01": _sample_cp01,
    "CP02": _sample_cp02,
    "CP11": _sample_cp11,
    "CP12": _sample_cp12,
    "CP19": _sample_cp19,
    "CP91": _sample_cp91,
    "CP92": _sample_cp92,
    # BC
    "BC01": _sample_bc,
    "BC02": _sample_bc,
    # BS
    "BS01": _sample_bs01,
    "BS02": _sample_bs02,
    "BS03": _sample_bs03,
    "BS04": _sample_bs04,
    "BS05": _sample_bs05,
    "BS07": _sample_bs07,
    # TL
    "TL01": _sample_tl01,
}
