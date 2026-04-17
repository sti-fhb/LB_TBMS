"""
LBSB01 中央 API 呼叫模組。

負責向中央 DP Server 發送 HTTP 請求：
  - 自家 Table（LB_PRINTER / LB_PRINT_LOG）的 INSERT / UPDATE / DELETE
  - 跨模組 SRV 呼叫（如 SRVDP020-刪除元件設備標籤對應）

API Base URL 從 config.ini [api] url 推導（去除路徑，保留 scheme+host+port）。
所有呼叫帶 Bearer Token（from Session）。
"""

from __future__ import annotations
import json
import logging
import urllib.error
import urllib.request
from urllib.parse import urlparse

log = logging.getLogger(__name__)


def _derive_base_url(api_url: str) -> str:
    """從 APIDP001 URL 推導 API Base URL。

    例: http://192.168.1.100:8000/api/external/auth/token → http://192.168.1.100:8000
    """
    parsed = urlparse(api_url)
    return f"{parsed.scheme}://{parsed.netloc}"


def call_central(
    api_url: str,
    token: str,
    method: str,
    path: str,
    payload: dict | None = None,
    timeout: int = 10,
) -> tuple[bool, dict]:
    """發送 HTTP 請求到中央 DP Server。

    Args:
        api_url: config.ini 的 [api] url（用於推導 base）
        token: Session TOKEN（Bearer）
        method: HTTP method（POST / PUT / DELETE）
        path: API 路徑（如 /api/lb/printer、/api/dp/srvdp020）
        payload: JSON Body（可為 None）
        timeout: 逾時秒數

    Returns:
        (success, response_dict)
    """
    base = _derive_base_url(api_url)
    url = f"{base}{path}"

    body = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload else None
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        method=method,
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            resp_body = json.loads(resp.read().decode("utf-8"))
            return True, resp_body

    except urllib.error.HTTPError as e:
        msg = f"HTTP {e.code}"
        try:
            err_body = json.loads(e.read().decode("utf-8"))
            msg = err_body.get("message", msg)
        except Exception:
            pass
        log.warning("中央 API 錯誤 [%s %s]: %s", method, path, msg)
        return False, {"message": msg}

    except urllib.error.URLError as e:
        msg = f"連線失敗: {e.reason}"
        log.warning("中央 API 連線失敗 [%s %s]: %s", method, path, msg)
        return False, {"message": msg}

    except Exception as e:
        msg = f"異常: {e}"
        log.warning("中央 API 異常 [%s %s]: %s", method, path, msg)
        return False, {"message": msg}


# ── PENDING_OPS Replay 用的 Dispatcher ────────────────────

# SRV 呼叫路徑對照（TARGET → API Path）
_SRV_PATH_MAP: dict[str, str] = {
    "SRVDP020": "/api/dp/srvdp020",
}

# Table 操作路徑對照（TARGET → API Path）
_TABLE_PATH_MAP: dict[str, str] = {
    "LB_PRINTER": "/api/lb/printer",
    "LB_PRINT_LOG": "/api/lb/print-log",
}


def replay_op(
    api_url: str,
    token: str,
    op_type: str,
    target: str,
    payload: dict,
) -> tuple[bool, str]:
    """Replay 單筆 PENDING_OPS 到中央。

    Args:
        api_url: config.ini [api] url
        token: Bearer TOKEN
        op_type: INSERT / UPDATE / DELETE / CALL_SRV
        target: Table 名稱或 SRV 編碼
        payload: JSON 參數

    Returns:
        (success, message)
    """
    if op_type == "CALL_SRV":
        path = _SRV_PATH_MAP.get(target)
        if not path:
            return False, f"未知的 SRV: {target}"
        ok, resp = call_central(api_url, token, "POST", path, payload)
        return ok, resp.get("message", "OK" if ok else "失敗")

    # INSERT / UPDATE / DELETE
    path = _TABLE_PATH_MAP.get(target)
    if not path:
        return False, f"未知的 Table: {target}"

    method_map = {"INSERT": "POST", "UPDATE": "PUT", "DELETE": "DELETE"}
    http_method = method_map.get(op_type, "POST")

    body = {"op_type": op_type, **payload}
    ok, resp = call_central(api_url, token, http_method, path, body)
    return ok, resp.get("message", "OK" if ok else "失敗")
