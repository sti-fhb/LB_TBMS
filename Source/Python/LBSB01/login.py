"""
LBSB01 認證模組。

啟動時自動以 APIDP001 取得 TOKEN，不顯示登入畫面。
認證參數：
  - CODE    : LB_PRINT
  - PASSCODE: stark123
  - 對應 EA 元素 GUID: {1BEF51C7-CD73-44e6-8D3B-CD134B3D388D}（標籤印表機服務登入）

設定檔：config.ini（與執行檔同目錄）。
認證失敗時程式仍可執行（離線模式），差異在無法存取中央 DB。
"""

from __future__ import annotations
import configparser
import json
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

# config.ini 路徑（與執行檔同目錄；編譯為 .exe 後亦同）
_CONFIG_FILE = _app_dir() / "config.ini"

# APIDP001 認證參數（對應 EA {1BEF51C7-CD73-44e6-8D3B-CD134B3D388D}）
API_CODE = "LB_PRINT"
API_PASSCODE = "stark123"

# config.ini 預設內容
_DEFAULTS = {
    "site": {
        "site_id": "S01",
        "site_name": "總院捐血中心",
    },
    "api": {
        "url": "http://localhost:8000/api/external/auth/token",
    },
    "token": {
        "value": "",
        "expires_in": "3600",
    },
}


@dataclass
class Session:
    """認證 Session（LBSB01 24x7 常駐）。"""
    site_id: str
    site_name: str
    token: str
    expires_in: int
    online: bool          # True=線上模式（認證成功）；False=離線模式（認證失敗）
    error_message: str    # 認證失敗原因（online=True 時為空）


def _read_config() -> configparser.ConfigParser:
    """讀取 config.ini；不存在則建立預設檔。"""
    cfg = configparser.ConfigParser()

    if _CONFIG_FILE.exists():
        cfg.read(_CONFIG_FILE, encoding="utf-8")
        log.debug("已讀取 config.ini: %s", _CONFIG_FILE)
    else:
        log.info("config.ini 不存在，建立預設檔: %s", _CONFIG_FILE)

    # 確保所有 section / key 都存在（補齊缺漏）
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
        f.write("; [site] 與 [api] 由管理者設定；[token] 由程式自動回寫\n\n")
        cfg.write(f)
    log.debug("config.ini 已寫入: %s", _CONFIG_FILE)


def authenticate() -> Session:
    """LBSB01 啟動認證流程。

    1. 讀取 config.ini（[site] 站點、[api] 端點）
    2. 呼叫 APIDP001 以 CODE + PASSCODE 取得 TOKEN
    3. 成功 → 回傳 Session(online=True)，TOKEN 回寫 config.ini [token]
    4. 失敗 → 回傳 Session(online=False)，程式以離線模式繼續運行
    """
    cfg = _read_config()
    site_id = cfg.get("site", "site_id")
    site_name = cfg.get("site", "site_name")
    api_url = cfg.get("api", "url")

    # Call APIDP001
    ok, result = _apidp001_get_token(api_url, API_CODE, API_PASSCODE)

    if not ok:
        err = result.get("message", "未知錯誤")
        log.error("APIDP001 認證失敗: %s → 進入離線模式", err)
        return Session(
            site_id=site_id,
            site_name=site_name,
            token="",
            expires_in=0,
            online=False,
            error_message=err,
        )

    token = result["token"]
    expires_in = result.get("expires_in", 3600)

    # 回寫 token 到 config.ini [token] section
    cfg.set("token", "value", token)
    cfg.set("token", "expires_in", str(expires_in))
    _write_config(cfg)

    log.info("APIDP001 認證成功: code=%s site=%s token=%s...",
             API_CODE, site_id, token[:8] if len(token) > 8 else token)
    return Session(
        site_id=site_id,
        site_name=site_name,
        token=token,
        expires_in=expires_in,
        online=True,
        error_message="",
    )


# ── APIDP001 呼叫 ─────────────────────────────────────────────

def _apidp001_get_token(
    api_url: str, code: str, passcode: str
) -> tuple[bool, dict]:
    """APIDP001-外部系統資料接收介面。

    POST /api/external/auth/token
    Body: { "code": "LB_PRINT", "passcode": "stark123" }

    實際嘗試 HTTP 連線中央 DP；連不上則回傳失敗（程式進入離線模式）。
    """
    log.info("APIDP001 認證: code=%s url=%s", code, api_url)

    payload = json.dumps({"code": code, "passcode": passcode}).encode("utf-8")
    req = urllib.request.Request(
        api_url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            token = body.get("token", "")
            if not token:
                return False, {"message": "回傳 Token 為空"}
            return True, body

    except urllib.error.HTTPError as e:
        msg = f"HTTP {e.code}"
        try:
            err_body = json.loads(e.read().decode("utf-8"))
            msg = err_body.get("message", msg)
        except Exception:
            pass
        log.warning("APIDP001 HTTP 錯誤: %s", msg)
        return False, {"message": msg}

    except urllib.error.URLError as e:
        msg = f"無法連線至 {api_url}（{e.reason}）"
        log.warning("APIDP001 連線失敗: %s", msg)
        return False, {"message": msg}

    except Exception as e:
        msg = f"認證異常: {e}"
        log.warning("APIDP001 異常: %s", msg)
        return False, {"message": msg}
