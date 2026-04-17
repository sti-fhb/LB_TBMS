"""
LBSB01 認證模組。

啟動時發 GET 健康檢查至中央，判定線上/離線。
TOKEN 永久有效，硬寫於常數 HARDCODED_TOKEN。
"""

from __future__ import annotations
import configparser
import logging
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path


def _app_dir() -> Path:
    """取得執行檔所在目錄（dev mode 與 PyInstaller onefile 皆正確）。"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).parent

log = logging.getLogger(__name__)

# config.ini 路徑（與執行檔同目錄）
_CONFIG_FILE = _app_dir() / "config.ini"

# ── 硬寫常數（待主專案配發後填入） ──────────────────────────
HARDCODED_TOKEN   = "PLACEHOLDER"               # Bearer TOKEN，永久有效
CENTRAL_API_BASE  = "http://localhost:8000"      # 中央 API Base URL
HEALTH_CHECK_PATH = "/api/health"               # 健康檢查端點

# config.ini 預設內容（只保留 [site]）
_DEFAULTS = {
    "site": {
        "site_id": "S01",
        "site_name": "總院捐血中心",
    },
}


@dataclass
class Session:
    """認證 Session（LBSB01 24x7 常駐）。"""
    site_id: str
    site_name: str
    token: str
    expires_in: int
    online: bool          # True=線上模式；False=離線模式
    error_message: str    # 失敗原因（online=True 時為空）


def _read_config() -> configparser.ConfigParser:
    """讀取 config.ini；不存在則建立預設檔。"""
    cfg = configparser.ConfigParser()

    if _CONFIG_FILE.exists():
        cfg.read(_CONFIG_FILE, encoding="utf-8")
        log.debug("已讀取 config.ini: %s", _CONFIG_FILE)
    else:
        log.info("config.ini 不存在，建立預設檔: %s", _CONFIG_FILE)

    # 確保 [site] section / key 存在（補齊缺漏）；舊格式 [api]/[token] 忽略不處理
    changed = False
    for section, keys in _DEFAULTS.items():
        if not cfg.has_section(section):
            cfg.add_section(section)
            changed = True
        for key, val in keys.items():
            if not cfg.has_option(section, key):
                cfg.set(section, key, val)
                changed = True

    if changed:
        _write_config(cfg)

    return cfg


def _write_config(cfg: configparser.ConfigParser) -> None:
    """寫入 config.ini。"""
    with open(_CONFIG_FILE, "w", encoding="utf-8") as f:
        f.write("; LBSB01 標籤服務程式設定檔\n")
        f.write("; [site] 由管理者依站點設定\n\n")
        cfg.write(f)
    log.debug("config.ini 已寫入: %s", _CONFIG_FILE)


def authenticate() -> Session:
    """LBSB01 啟動認證流程。

    1. 讀取 config.ini [site]
    2. 發 GET 健康檢查至中央
    3. 成功 → Session(online=True)；失敗 → Session(online=False，離線模式)
    """
    cfg = _read_config()
    site_id = cfg.get("site", "site_id")
    site_name = cfg.get("site", "site_name")

    online = _health_check()

    if online:
        log.info("健康檢查成功: site=%s", site_id)
    else:
        log.error("健康檢查失敗 → 進入離線模式")

    return Session(
        site_id=site_id,
        site_name=site_name,
        token=HARDCODED_TOKEN,
        expires_in=0,
        online=online,
        error_message="" if online else "無法連線至中央服務",
    )


def _health_check() -> bool:
    """發 GET 至健康檢查端點，回傳是否可達。"""
    url = f"{CENTRAL_API_BASE}{HEALTH_CHECK_PATH}"
    log.info("健康檢查: %s", url)
    req = urllib.request.Request(
        url,
        method="GET",
        headers={"Authorization": f"Bearer {HARDCODED_TOKEN}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status == 200
    except Exception as e:
        log.warning("健康檢查失敗: %s", e)
        return False
