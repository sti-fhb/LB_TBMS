# ISLB001 — TOKEN 與中央 URL 硬寫變更

**建立日期**: 2026-04-17
**優先順序**: HIGH
**類型**: 架構變更
**狀態**: 待實作

---

## 1. 背景

原設計：LBSB01 啟動時呼叫 **APIDP001-外部系統資料接收介面** 取得 TOKEN，認證失敗則進入離線模式，60 秒自動重連。

**變更原因**：
- TOKEN 永久有效（不需動態換發）
- 簡化部署（不需在 DP_EXT_API_KEY 參數表維護 CODE / PASSCODE）
- 中央 URL 也改為硬寫於程式，避免誤改 config.ini 導致無法連線

## 2. 設計決策

| 項目 | 新設計 |
|------|--------|
| TOKEN | 硬寫於 `login.py` 常數 `HARDCODED_TOKEN`，永久有效 |
| 中央 API Base URL | 硬寫於 `login.py` 常數 `CENTRAL_API_BASE` |
| 健康檢查路徑 | 硬寫於 `login.py` 常數 `HEALTH_CHECK_PATH` |
| 線上/離線判定 | 啟動時及每 60 秒 ping `GET {CENTRAL_API_BASE}{HEALTH_CHECK_PATH}` |
| config.ini | **只保留 `[site]`**（移除 `[token]` 與 `[api]` sections） |

## 3. 實作範圍

### 3.1 `Source/Python/LBSB01/login.py`

**新增常數（module 層級）**：

```python
HARDCODED_TOKEN = "<待主專案配發>"       # Bearer TOKEN，永久有效
CENTRAL_API_BASE = "http://<host>:<port>"  # 中央 API Base URL
HEALTH_CHECK_PATH = "/api/health"         # 待主專案定義確切路徑
```

**修改 `authenticate()` 函式**：
- 移除 `_apidp001_get_token()` 呼叫
- 改為：讀 config.ini `[site]` → 載入常數 TOKEN → 呼叫健康檢查
- 回傳 Session 時 token 欄位填 `HARDCODED_TOKEN`
- 依健康檢查結果設定 `online` 旗標

**移除**：
- `API_CODE = "LB_PRINT"` 常數
- `API_PASSCODE = "stark123"` 常數
- `_apidp001_get_token()` 函式
- `_DEFAULTS` 裡的 `[api]` 與 `[token]` sections

**新增**：
- `_health_check() -> bool` 函式：發 GET 請求到健康檢查端點，回傳是否可達

### 3.2 `Source/Python/LBSB01/main.py`

**修改 `_try_reconnect()`**：
- 從呼叫 `authenticate()` 取得新 Session，改為只做健康檢查
- 成功時只需切換 `session.online = True` + 觸發 `_sync_local_to_db()`

**修改 Splash 文字**：
- 「正在登入主系統 DB ...」→「正在檢查主系統連線 ...」
- 「APIDP001-外部系統資料接收介面 認證中」→「健康檢查中」

### 3.3 `Source/Python/LBSB01/central_api.py`

**修改 `_derive_base_url()`**：
- 原本從 `config.ini [api] url` 推導 base → 改為直接讀 `login.CENTRAL_API_BASE` 常數
- 或將此函式整個移除，改用 `login.CENTRAL_API_BASE` 常數

**修改 `call_central()` / `replay_op()`**：
- 不再接受 `api_url` 參數，改用 `login.CENTRAL_API_BASE`

**修改 `main.py` 呼叫處**：
- `_sync_local_to_db()` 內原本呼叫 `_read_config()` 取 `api_url`，改為直接使用 `login.CENTRAL_API_BASE`

### 3.4 config.ini 遷移

**新 config.ini 格式**：

```ini
; LBSB01 標籤服務程式設定檔
; [site] 由管理者依站點設定

[site]
site_id = S01
site_name = 總院捐血中心
```

**移除 sections**：
- `[api]`
- `[token]`

**向下相容**：
- 啟動時若讀到舊格式 config.ini（有 `[api]` 或 `[token]`），**忽略**這些 sections
- 不主動刪除，避免破壞使用者檔案

---

## 4. 驗收條件

- [ ] 啟動時不再呼叫 APIDP001 端點
- [ ] Log 出現 "健康檢查" 相關訊息，不再有 "APIDP001 認證" 字眼
- [ ] config.ini 預設產生時只有 `[site]` section
- [ ] 網路通 → 標題【線上】；網路斷 → 標題【離線】
- [ ] 離線期間 60 秒後自動重試健康檢查
- [ ] 重新連上中央後 `_sync_local_to_db()` 仍能正常 replay PENDING_OPS
- [ ] `login.HARDCODED_TOKEN` 可被 Task Listener 與 central_api 共用
- [ ] 所有主動呼叫中央的地方（健康檢查、SRVDP020、同步）都帶 `Authorization: Bearer <HARDCODED_TOKEN>`

---

## 5. 相依（待主專案定義）

| 項目 | 主專案待辦 | 影響 |
|------|----------|------|
| 健康檢查端點路徑 | 需定義 `GET /api/health` 或類似端點 | 填入 `HEALTH_CHECK_PATH` 常數 |
| LBSB01 專用 TOKEN 值 | 管理者配發固定 TOKEN | 填入 `HARDCODED_TOKEN` 常數 |
| 中央 API Base URL | 正式環境確切 URL | 填入 `CENTRAL_API_BASE` 常數 |
| SRVDP020 實際 API path | 目前程式假設 `/api/dp/srvdp020` | 確認後更新 `central_api._SRV_PATH_MAP` |
| LB_PRINTER / LB_PRINT_LOG CRUD API | 目前程式假設 `/api/lb/printer` 等 | 確認後更新 `central_api._TABLE_PATH_MAP` |

> 主專案未定義這些項目前，LB 可先填入假值（如 `HARDCODED_TOKEN = "PLACEHOLDER"`），功能上仍會運作（健康檢查失敗 → 離線模式）。

---

## 6. 相關文件

- [docs/LBSB01-開發者指南.md](../LBSB01-開發者指南.md) — Section 3 config.ini、Section 4 啟動流程、Section 8.1 健康檢查
- [docs/LBSB01-操作手冊.md](../LBSB01-操作手冊.md) — Section 2.2 認證機制、Section 2.3 config.ini
- [docs/specs/lb/spec.md](../specs/lb/spec.md) — R02 / R03 核心特性
- [docs/specs/lb/contracts/srv-contracts.md](../specs/lb/contracts/srv-contracts.md) — 健康檢查端點
- [docs/images/offline-reconnect.png](../images/offline-reconnect.png) — 離線重連流程圖

---

## 7. 不在本 Issue 範圍

- SRV 契約調整（由主專案負責）
- 主專案的健康檢查端點實作
- 主專案的 SRVDP020 端點實作
- 主專案的 LB Table CRUD API 實作
