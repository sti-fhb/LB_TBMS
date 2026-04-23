# LBSB01 標籤服務程式 — 開發者指南

**適用對象**: LB 模組開發者（無法存取主專案 TSBMS_SA）
**程式語言**: Python 3.12+
**交付型態**: 編譯為 .exe（PyInstaller / Nuitka），config.ini 隨附

---

## 目錄

1. [專案架構](#1-專案架構)
2. [開發環境設定](#2-開發環境設定)
3. [config.ini 設定](#3-configini-設定)
4. [啟動流程與認證](#4-啟動流程與認證)
5. [DB 存取規則與 SRV 架構](#5-db-存取規則與-srv-架構)
6. [離線暫存與同步架構（local.db）](#6-離線暫存與同步架構localdb)
7. [SRV 清單速查](#7-srv-清單速查)
8. [API 呼叫模式](#8-api-呼叫模式)
9. [Queue 三層架構](#9-queue-三層架構)
10. [標籤印表機設定](#10-標籤印表機設定)
11. [標籤測試頁](#11-標籤測試頁)
12. [編譯為 EXE](#12-編譯為-exe)
13. [注意事項與規則](#13-注意事項與規則)

---

## 1. 專案架構

```
_LB/
├── Source/Python/LBSB01/        ← Python 原始碼
│   ├── main.py                  ← 程式進入點（App 主視窗）
│   ├── login.py                 ← 認證模組（TOKEN + 中央 URL 硬寫常數；無 Login、無健康檢查）
│   ├── local_db.py              ← 本地 SQLite 封裝（Cache + Queue + PENDING_OPS）
│   ├── printer_setting.py       ← 印表機設定頁面
│   ├── sample_data_print.py     ← 標籤測試頁
│   ├── labels.py                ← 標籤定義（目前啟用 4 種：TL01, CP01, CP11, CP19）
│   ├── sample_data.py           ← 標籤樣本資料
│   ├── ezpl.py                  ← GoDEX EZPL DLL 封裝
│   ├── config.ini               ← 本機設定（站點 + API URL，隨執行檔部署）
│   ├── local.db                 ← SQLite 本地資料庫（程式自動建立）
│   └── Log/
│       └── LBSB01{YYYYMMDD}.log ← 每日系統 Log
│
├── docs/
│   └── specs/lb/
│       ├── LBSB01-操作手冊.md       ← 操作人員用
│       ├── LBSB01-開發者指南.md     ← ← 本文件
│       ├── SRVLB001-標籤列印整合指南.md
│       ├── spec.md                  ← 功能規格
│       ├── data-model.md            ← 資料模型 + ERD
│       └── contracts/
│           └── srv-contracts.md     ← SRV 契約（完整 I/O 定義）
```

---

## 2. 開發環境設定

### 2.1 前置需求

| 項目 | 版本 | 說明 |
|------|------|------|
| Python | 3.12+ | 使用 dataclass, `X \| None` 語法 |
| tkinter | 內建 | GUI 框架 |
| pystray | 0.19+ | 系統匣 icon（最小化到工作列右下角） |
| Pillow | 10+ | Tray icon 圖像處理 |
| GoDEX EZIO DLL | 官方 SDK | 標籤印表機驅動（見 2.2 下載說明） |

安裝 Python 套件：
```bash
pip install pystray Pillow
```

### 2.2 GoDEX EZIO DLL 下載

EZIO 是 GoDEX 官方提供的印表機 SDK DLL（`EZio32.dll` / `EZio64.dll`），用於控制 GoDEX 標籤印表機（G500 / G530 / EZ 系列等）。

**官方下載位置**：

| 管道 | 網址 |
|------|------|
| GoDEX 全球官網（英文）| https://www.godexintl.com/ → `Support` → `Download Center` → `SDK` |
| 科誠科技（台灣）| https://www.godexintl.com.tw/ → `技術支援` → `下載專區` → `SDK` |

**檔名**：
- `EZio32.dll`（32-bit Python 用）
- `EZio64.dll`（64-bit Python 用）
- 程式會依 Python 位元自動偵測載入

**部署**：DLL 檔必須與 `LBSB01.exe`（或 `main.py`）**放在同一目錄**，或在 Windows `PATH` 環境變數可搜尋到的位置。

> **建議**：首次部署時連同印表機隨附光碟或向 GoDEX 經銷商索取最新版 SDK。使用與印表機韌體匹配的 DLL 版本可避免相容性問題。

### 2.3 快速啟動

```bash
cd Source/Python/LBSB01
python main.py
```

首次執行會自動建立 `config.ini`（預設值）。修改 `[site]` 後重啟即可。

### 2.4 開發用離線模式

網路不通或中央服務未啟動時，**Call APILB 失敗（連線逾時 / 5xx）** → 程式進入**離線模式**（`session.online = False`）：

- 印表機設定 CRUD → 寫 Local Cache + 排 PENDING_OPS
- 標籤測試頁 → POST localhost:9200 走本機迴路（正常可用）
- Queue 操作（移動/刪除/列印）→ 操作 local.db
- 中央 API 呼叫（APILB001~007）→ 排入 PENDING_OPS，待同步時 replay

> 離線模式讓開發者不需中央服務即可開發 UI 與流程邏輯。離線時 Timer **每 3 分鐘**、或使用者按主畫面 **[更新]** 按鈕，才觸發同步；同步動作即執行 replay，並依 API 回應得知當下是否回復線上。成功後靜默切換線上模式（不 Prompt）。

---

## 3. config.ini 設定

設定檔位於**執行檔同目錄**，INI 格式（UTF-8）。

> **設計變更（2026-04-17）**：TOKEN 與中央 API Base URL 已改為**硬寫於 `login.py` 常數**，不再寫入 config.ini。
> config.ini 只保留 `[site]`。

```ini
; LBSB01 標籤服務程式設定檔
; [site] 由管理者依站點設定

[site]
site_id = S01
site_name = 總院捐血中心
```

| Section | Key | 說明 | 維護者 |
|---------|-----|------|--------|
| `[site]` | `site_id` | 站點代碼（須與中央 DP 一致） | 管理者 |
| `[site]` | `site_name` | 站點中文名稱 | 管理者 |

### 程式內硬寫常數（login.py）

| 常數 | 說明 |
|------|------|
| `HARDCODED_TOKEN` | 供 Task Listener 驗證 + 主動呼叫中央時帶入 Bearer |
| `CENTRAL_API_BASE` | 中央 API Base URL（例：`http://192.168.1.100:8000`） |

> ⚠ **URL 對齊規則**：未來任何 URL 變更（APIDP/SRV 路徑等），一律**以主專案 infra 文件為準**（`c:\TSBMS\TBMS\docs\specs\dp\contracts\api-contracts.md` 等）。
> 不得自行決定路徑規則，避免與主專案不一致。
>
> **無健康檢查端點**（2026-04-22 對齊 EA 離線原則）：LBSB01 不做獨立健康檢查 ping，線上/離線狀態由實際 Call APILB 的結果決定。

> 程式啟動時若 config.ini 不存在，會自動建立預設 `[site]`。

---

## 4. 啟動流程與認證

> **無 Login 動作**：Call APILB 一律用 Bearer Token，程式不做獨立健康檢查 ping；離線狀態由**首次真正呼叫 APILB** 的結果決定（EA 離線原則 R03 / UCLB101）。

```
main.py 啟動
  │
  ├─ 顯示 Splash：「正在啟動 ...」
  │
  ├─ login.authenticate()
  │    ├─ 讀 config.ini（[site]）
  │    ├─ 載入 HARDCODED_TOKEN（login.py 常數）
  │    └─ 組 Session（online 暫設 True，待首次 API 呼叫後修正）
  │
  ├─ 移除 Splash
  │
  ├─ 主畫面開啟，背景啟動：
  │    ├─ Task Listener（:9200）
  │    └─ 首次同步：替代「健康檢查」的角色 — Call APILB001（取印表機清單）
  │         ├─ 成功 → online=True，標題【線上】（綠色），刷新 Local Cache
  │         └─ 失敗（連線逾時 / 5xx）→ online=False，標題【離線】（紅色），
  │                                     啟動 OffLine Retry Timer（3 分鐘）
  └─ 離線時程式仍可執行（本地 Queue + 印表機 CRUD；異動排入 PENDING_OPS）
```

### Session 結構

```python
@dataclass
class Session:
    site_id: str          # 站點代碼（from config.ini）
    site_name: str        # 站點名稱
    token: str            # from login.HARDCODED_TOKEN（永久有效）
    online: bool          # True=線上 / False=離線（依 APILB 呼叫結果）
    error_message: str    # 連線失敗原因（online=True 時為空）
```

### 認證機制

| 項目 | 值 | 來源 |
|------|-----|------|
| TOKEN | 硬寫字串 | `login.HARDCODED_TOKEN` |
| 中央 Base URL | 硬寫字串 | `login.CENTRAL_API_BASE` |

> **變更紀錄**：
> - 2026-04-17：原呼叫 APIDP001 取動態 TOKEN 改為硬寫 `HARDCODED_TOKEN`（永久有效）。
> - 2026-04-22：移除健康檢查端點（`HEALTH_CHECK_PATH`）；線上/離線改由實際 Call APILB 結果判定，對齊 EA UCLB101「離線原則」Rule。

---

## 5. DB 存取規則與 SRV 架構

### 核心規則

> **自家模組（LB）可直接存取自家 Table；跨模組 Table 仍需透過 SRV。**

| 存取對象 | 方式 | 說明 |
|---------|------|------|
| **LB_PRINTER**（自家） | 直接 SQL | 透過 `local_db.py` 讀寫本地 SQLite Cache，線上時同步中央 |
| **LB_PRINT_LOG**（自家） | 直接 SQL | 同上 |
| **DP_COMPDEVICE_LABEL**（跨模組） | 由 **APILB005** 後端 cascade 清除，LBSB01 不直接呼叫 | 刪除印表機時後端一併清子表 |
| **其他模組呼叫 LB** | 透過 **SRVLB001** | LB 提供的對外服務（列印指令接收） |

```
LBSB01 (Python)
  │
  ├─ TOKEN + 中央 URL 硬寫於 login.py 常數
  ├─ 離線偵測：Call APILB 失敗（逾時/5xx）→ session.online=False
  │
  ├─ local_db.py（本地 SQLite）
  │   ├─ LB_PRINTER_CACHE      ← 自家 Table 直接讀寫
  │   ├─ LB_PRINT_LOG_CACHE    ← 自家 Table 直接讀寫
  │   ├─ ONLINE_QUEUE / OFFLINE_QUEUE
  │   └─ PENDING_OPS           ← 同步操作佇列
  │
  ├─ 寫入一律先寫 Local Cache + 排 PENDING_OPS（Local-first）
  └─ 同步時機（僅這兩個時機）：
        ├─ OffLine Retry Timer（每 3 分鐘）
        └─ 使用者按主畫面 [更新] 按鈕
              │
              ▼
        replay PENDING_OPS（帶 Bearer TOKEN）
        策略：一律以 Local DB 蓋中央 DB
```

### SRV 清單（僅保留對外服務 + 跨模組呼叫）

| 編碼 | 名稱 | 類別 | 說明 |
|------|------|------|------|
| **SRVLB001** | 標籤列印通用API | 對外提供 | 其他模組（BC/CP/BS/TL）Call LB 送列印指令 |
| **SRVDP010** | 資訊設備標籤印表機查詢 | 由 SRVLB001 呼叫 | LB 不直接呼叫 |
| **APILB001~005** | 印表機 CRUD（複數 REST 端點）| 對外提供 | 印表機查清單/單筆/新增/修改/刪除 |
| **APILB006** | 回報列印事件（UPDATE LB_PRINT_LOG）| 對外提供 | LBSB01 回寫列印完成/狀態變更 |
| **APILB007** | 新增列印事件（INSERT LB_PRINT_LOG）| 對外提供 | 測試頁/離線新增 LOG（或中央 SRVLB001 進件）|

> 自家 Table 的 CRUD（新增/查詢/更新/刪除印表機、LOG 更新）走 Local Cache + PENDING_OPS，由 OffLine Retry Timer（3 分鐘）或 [更新] 按鈕觸發 replay 至中央。
>
> **已棄用**：APIDP001（TOKEN 改硬寫，不再呼叫）；健康檢查端點（離線偵測改由 Call APILB 結果判定）。

---

## 6. 離線暫存與同步架構（local.db）

### 6.1 設計原則（EA UCLB101「離線原則」Rule）

LBSB01 為 24x7 常駐程式，必須在**網路中斷時仍能正常運作**。所有資料操作遵循：

1. **無 Login 動作** — CALL API 一律帶 Bearer Token（`HARDCODED_TOKEN`）；當 **Call APILB 連不上中央 DB 時才會知道當下是離線**（無獨立健康檢查 ping）。
2. **同步時機僅兩種** — 離線時啟動 Timer **每 3 分鐘**，或使用者按主畫面 **[更新]** 按鈕；**只有這兩個時機才 replay PENDING_OPS**，並由 API 回應得知當下線上/離線。
3. **Local-first + 一律以 Local 蓋中央** — 不管線上或離線，Call APILB **前先寫 Local DB**；待連線時再 Sync 更新。**一律以 Local DB 蓋中央 DB**（不做欄位合併/衝突解析），使離線時可修改印表機、列印測試標籤。

### 6.2 local.db 結構（SQLite，WAL mode）

```
local.db
│
├── LB_PRINTER_CACHE        ← 中央 LB_PRINTER 的本地鏡像（離線可讀寫）
├── LB_PRINT_LOG_CACHE      ← 中央 LB_PRINT_LOG 的本地鏡像
├── ONLINE_QUEUE            ← Online Queue（列印佇列，本地持久化）
├── OFFLINE_QUEUE           ← Offline Queue（離線重印佇列）
│
└── PENDING_OPS             ← 待同步操作佇列
    ├── SEQ         INTEGER PRIMARY KEY AUTOINCREMENT
    ├── OP_TYPE     TEXT    -- INSERT / UPDATE / DELETE / CALL_SRV
    ├── TARGET      TEXT    -- Table 名稱或 SRV 編碼
    ├── PAYLOAD     TEXT    -- JSON（完整參數）
    ├── CREATED_AT  TEXT    -- ISO 時間戳
    └── STATUS      INTEGER -- 0=待同步, 1=已同步, 2=失敗
```

> 資料庫採 WAL mode（`PRAGMA journal_mode=WAL`），允許 Task Listener Thread 寫入的同時，Main Thread 可安全讀取。

### 6.3 線上/離線模式判定

![LBSB01 內部功能流程（UCLB101，離線原則權威圖）](usecase/UCLB101-LBSB01內部功能流程.png)

> **離線判定**：不做獨立 `GET /api/health` ping。程式 Call APILB（如 APILB001 取清單、APILB006 回報事件）時：
> - 成功（200） → `session.online = True`
> - 連線逾時 / 5xx → `session.online = False`，啟動 OffLine Retry Timer

**離線模式下仍可使用的功能**：

| 功能 | 可用 | 說明 |
|------|------|------|
| 接收外部 Task | △ | Listener 仍運行，但中央通常也不可達 |
| 標籤測試頁 | ✓ | POST localhost:9200 走本機迴路 |
| Queue 操作（移動/刪除） | ✓ | 操作 local.db |
| 印表機設定 CRUD | ✓ | 寫 Local Cache + 排 PENDING_OPS |
| GoDEX 列印（USB/TCP） | ✓ | 與印表機的通訊不經中央 |

### 6.4 同步機制（OffLine Retry Timer 3 分鐘 + 手動 [更新]）

離線時，以下**兩個時機**會觸發同步動作（包含 replay PENDING_OPS 並由 API 回應判定線上/離線）：

1. **OffLine Retry Timer**：離線時啟動，每 **3 分鐘**執行一次；回復線上後關閉 Timer
2. **主畫面 [更新] 按鈕**：使用者手動觸發同步

**程式對應**（[main.py](Source/Python/LBSB01/main.py)）：

```python
OFFLINE_RETRY_INTERVAL_MS = 3 * 60 * 1000   # 3 分鐘（EA 離線原則 R03）

def _start_offline_retry_timer(self):
    """離線時啟動 OffLine Retry Timer（每 3 分鐘觸發 _do_sync）"""
    self._retry_id = self.after(OFFLINE_RETRY_INTERVAL_MS, self._do_sync)

def _on_refresh_clicked(self):
    """主畫面 [更新] 按鈕：手動觸發同步"""
    self._do_sync()

def _do_sync(self):
    """唯一同步入口：replay PENDING_OPS → 依 API 回應判定線上/離線"""
    ok = self._sync_local_to_db()       # 實際 Call APILB；一律以 Local 蓋中央
    self.session.online = ok
    self._update_mode_display()
    if ok:
        self._stop_offline_retry_timer()
    else:
        self._start_offline_retry_timer()
```

> 同步使用 Tkinter 的 `after()` 排程，不另開 Thread。`after()` 在 Main Thread 執行，與 UI 操作無衝突。
> **不設其他背景 Timer**：不做獨立健康檢查 ping、不做額外 30 秒週期 replay；同步只能由 3 分鐘 Timer 或 [更新] 按鈕觸發。

### 6.5 操作流程（online 旗標分流）

每個寫入操作都帶 `online` 參數，決定是否同步到中央：

```
使用者操作（新增/修改/刪除印表機、列印完成更新 LOG...）
  │
  ├─ 1. 寫入 Local Cache（即時生效，畫面立刻反映）
  │      └─ LB_PRINTER_CACHE / LB_PRINT_LOG_CACHE
  │
  ├─ 2. session.online?
  │      │
  │      ├─ YES → HTTP Call 中央 API（APILB001~007）寫中央 DB
  │      │
  │      └─ NO  → INSERT INTO PENDING_OPS
  │               OP_TYPE: INSERT / UPDATE / DELETE / CALL_SRV
  │               TARGET:  Table 名稱 or SRV 編碼
  │               PAYLOAD: JSON（完整參數，可原樣 replay）
  │
  ▼
```

**程式範例**（[local_db.py](Source/Python/LBSB01/local_db.py)）：

```python
def add_printer(self, data: dict, online: bool):
    # 1. 永遠先寫 Local Cache
    self.insert_printer(data)
    # 2. 離線時排入 PENDING_OPS
    if not online:
        self.enqueue_op("INSERT", "LB_PRINTER", data)

def remove_printer(self, site_id, printer_id, online: bool):
    # 1. 永遠先刪 Local Cache
    self.delete_printer(printer_id)
    # 2. 離線時排入一筆 PENDING_OPS（APILB005 後端 cascade 清子表）
    if not online:
        self.enqueue_op("DELETE", "LB_PRINTER",         # APILB005 後端 cascade 清 DP_COMPDEVICE_LABEL
                        {"printer_id": printer_id})
```

### 6.6 同步動作（_sync_local_to_db）

由 OffLine Retry Timer（3 分鐘）或 [更新] 按鈕觸發時執行，replay 累積的 PENDING_OPS；策略為「**一律以 Local DB 蓋中央 DB**」。

**同步步驟**：

1. 讀取 `PENDING_OPS WHERE STATUS=0 ORDER BY SEQ`
2. 逐筆取出 `(OP_TYPE, TARGET, PAYLOAD)`
3. 依 OP_TYPE 呼叫對應 APILB：
   - `INSERT` → `POST /api/lb/...`（對應 APILB003 / APILB007）
   - `UPDATE` → `PATCH /api/lb/...`（對應 APILB004 / APILB006）
   - `DELETE` → `DELETE /api/lb/...`（對應 APILB005）
4. 執行結果處理：
   - 成功 → `mark_op_synced(seq)`，STATUS → 1
   - 失敗（非 404）→ `mark_op_failed(seq)`，STATUS → 2，不阻塞後續
   - UPDATE / DELETE 回 404 → 視為同步成功（中央已無該筆，Local-first 語意）
5. 全部處理完畢，不從中央刷新 Local（以 Local 為準）

> 離線流程權威圖見 [UCLB101 內部功能流程](usecase/UCLB101-LBSB01內部功能流程.png)。

### 6.7 離線範例：刪除印表機

完整流程展示「Local 即時 + 離線暫存 + 上線 replay」三段式架構：

```python
# 情境：使用者在離線狀態下刪除印表機 PRN-004
# 呼叫：local_db.remove_printer("S01", "PRN-004", online=False)

# ── Step 1: Local Cache 即時刪除（畫面立刻消失）──
DELETE FROM LB_PRINTER_CACHE WHERE PRINTER_ID='PRN-004'

# ── Step 2: 排入 PENDING_OPS（一筆即可，APILB005 後端 cascade）──
SEQ=1: DELETE / LB_PRINTER / {"printer_id":"PRN-004"}   ← 對應 APILB005

# ── Step 3: 上線後 replay（_sync_local_to_db）──
SEQ=1 → HTTP DELETE /api/lb/printers/PRN-004
        APILB005 後端 Transaction：
          ① DELETE FROM DP_COMPDEVICE_LABEL WHERE PRINTER_ID='PRN-004'（先清子表）
          ② DELETE FROM LB_PRINTER WHERE PRINTER_ID='PRN-004'（硬刪主表）
        → 成功 → PENDING_OPS.STATUS=1
```

> **架構簡化（2026-04-22）**：原本兩段式（SRVDP020 + SRVLB092）已統一到 APILB005 單一端點，由後端 Transaction 保證 cascade 原子性。LBSB01 端只需排一筆 PENDING_OPS，不再有順序相依問題。

### 6.8 local_db.py 主要 API

| 方法 | 用途 |
|------|------|
| `add_printer(data, online)` | 新增印表機：寫 Cache + 離線排 PENDING_OPS |
| `save_printer(data, online)` | 更新印表機：寫 Cache + 離線排 PENDING_OPS |
| `remove_printer(site, pid, online)` | 刪除印表機：刪 Cache + 離線排一筆 DELETE PENDING_OPS（對應 APILB005，後端 cascade 清子表）|
| `list_printers(site_id)` | 查詢站點印表機（讀 Local Cache） |
| `insert_print_log(data)` | Task 寫入 LOG（Task Listener 呼叫） |
| `update_print_log(uuid, status, result)` | 更新 LOG 狀態 + RESULT |
| `delete_queue_task(uuid, online)` | 從 Queue 移除 + Status→1 |
| `move_task_to_offline(uuid)` | Online→Offline（Status 0→2） |
| `move_task_to_online(uuid)` | Offline→Online（Status 2→0） |
| `override_task_printer(uuid, new_pid)` | 覆寫 Task 的目標印表機 |
| `enqueue_op(op_type, target, payload)` | 直接排入 PENDING_OPS |
| `get_pending_ops()` | 取得待同步操作清單（STATUS=0） |
| `mark_op_synced(seq)` / `mark_op_failed(seq)` | 標記同步結果 |
| `replace_all_printers(site_id, list)` | 全量刷新 Cache（上線同步後用） |
| `build_result(...)` | 組 RESULT（見 Section 9.8） |

### 6.9 衝突處理（一律以 Local DB 蓋中央 DB）

EA UCLB101「離線原則」明定「一律以 Local DB 蓋中央 DB 即可」，不做欄位層級合併或以中央為準的覆蓋；實作時：

| 情境 | 策略 |
|------|------|
| 離線期間修改了印表機，中央也被改 | 以 Local 蓋中央（PENDING_OPS 的 UPDATE 直接 PATCH/upsert）|
| PENDING_OPS 某筆 replay 失敗 | 標記 STATUS=2，不阻塞後續；下次同步時機再重試 |
| 離線刪了印表機，但中央已不存在 | DELETE 回 404 視為成功，標記 STATUS=1 |
| 離線新增印表機，中央已有同 ID | 改以 UPDATE（upsert 語意），仍以 Local 值覆蓋中央 |

> **不做「上線後全量從中央拉取刷新 Local」**。Local 即為最終狀態，中央只是 Local 的異地備份。

---

## 7. SRV 清單速查

### 對外提供（其他模組 Call LB）

| 編碼 | 名稱 | 說明 |
|------|------|------|
| **SRVLB001** | 標籤列印通用API | BC/CP/BS/TL 送列印指令；Status=0 進 Online、Status=2 進 Offline |

### 跨模組呼叫（LB Call DP）

| 編碼 | 名稱 | 呼叫場景 | 離線處理 |
|------|------|---------|---------|
| **APILB005** | 刪除印表機（後端 cascade 清 DP_COMPDEVICE_LABEL）| 刪除印表機時 | 排入一筆 DELETE PENDING_OPS |

> **已棄用**：
> - APIDP001-外部系統資料接收介面（TOKEN 改硬寫於 `login.py`，不再呼叫）
> - 健康檢查端點（離線偵測改由實際 Call APILB 結果判定，EA UCLB101 離線原則）

### 自家模組直接操作（不需 SRV）

| Table | 操作 | 模組 |
|-------|------|------|
| LB_PRINTER | CRUD | `local_db.py` 直接讀寫 |
| LB_PRINT_LOG | INSERT / UPDATE | `local_db.py` 直接讀寫 |

> 完整 SRV 契約見 `docs/specs/lb/contracts/srv-contracts.md`

---

## 8. API 呼叫模式

本節說明 LBSB01 涉及的三種 API 呼叫模式：**同步 API 呼叫（兼作離線偵測）**、**被動接收**、**本機迴路**。

> **無獨立健康檢查端點**（EA UCLB101 離線原則）：LBSB01 **不做** `GET /api/health` 之類的 ping。線上/離線由**實際 Call APILB 的結果**決定，並且同步僅由 OffLine Retry Timer（3 分鐘）或主畫面 [更新] 觸發。

### 8.1 同步 API 呼叫（LBSB01 → 中央；兼作離線偵測）

同步時機觸發 `_sync_local_to_db()`，依序 replay PENDING_OPS；每支 HTTP 呼叫的結果即視同「線上偵測」：

```
LBSB01                                     中央 TBMS
──────                                     ──────────
OffLine Retry Timer 3 分鐘 觸發
  或 使用者按 [更新] 觸發
  │
  ▼ 逐筆 replay PENDING_OPS（Bearer HARDCODED_TOKEN）
HTTP {POST|PATCH|DELETE} /api/lb/...
                                   ──→ APILB001~007
                                   ←── 200 OK / 4xx / 5xx / timeout

[任一筆成功] → session.online = True，停 Retry Timer
[全部失敗 / 逾時] → session.online = False，繼續 3 分鐘後重試
```

**呼叫時機**：

| 時機 | 說明 |
|------|------|
| 程式啟動後首次同步 | 主畫面開啟完成時觸發一次，兼作開機連線探測 |
| OffLine Retry Timer | 離線時每 **3 分鐘**觸發 |
| 主畫面 [更新] 按鈕 | 使用者手動觸發 |

**TOKEN 與 URL 來源**：

| 項目 | 來源 | 說明 |
|------|------|------|
| TOKEN | `login.HARDCODED_TOKEN` | 硬寫於程式，永久有效 |
| 中央 Base URL | `login.CENTRAL_API_BASE` | 硬寫於程式 |

**失敗處理**：
- 連線逾時 / 5xx / 拒絕 → `session.online = False`，離線模式續跑
- HTTP 4xx 單筆 → 該 PENDING_OP 標記 STATUS=2（失敗），不阻塞其他筆；不自動切離線
- 4xx 中 401/403（罕見，TOKEN 應永久有效）→ 記錄 ERROR 至 Log，繼續視為離線

> **變更紀錄**：
> - 2026-04-17：原呼叫 APIDP001 取動態 TOKEN 改為硬寫 TOKEN。
> - 2026-04-22：移除 `GET /api/health` 健康檢查端點；離線偵測改由實際 Call APILB 結果判定；Timer 由 60 秒改為 **3 分鐘**、加入 [更新] 手動同步（對齊 EA UCLB101 離線原則 Rule）。

### 8.2 Task Listener 被動接收（中央 → LBSB01）

LBSB01 不主動輪詢中央，而是開啟 HTTP Server **被動等待**中央派送列印指令：

```
外部模組（BC/CP）                中央 SRVLB001            LBSB01 (:9200)
────────────────                ──────────────            ──────────────
Call SRVLB001
  printer_id=PRN-002
  bar_type=CP11
  data_1~19=...
                    ──→ 產生 UUID
                        INSERT LB_PRINT_LOG
                        查 LB_PRINTER
                          .SERVER_IP
                    ──→ POST http://{SERVER_IP}:9200/api/lb/task
                        Authorization: Bearer <token>
                        Body: { uuid, printer_id, bar_type,
                                site_id, data_1~19, status }
                                                          ──→ 驗證 TOKEN
                                                              寫 local.db
                                                              通知 GUI
                                                          ←── 200 OK
                    ←── 回傳 Client 成功
```

**端點規格**（詳見 Section 9.3）：

| 項目 | 值 |
|------|-----|
| URL | `POST /api/lb/task` |
| Port | 9200（固定） |
| 認證 | `Authorization: Bearer {session.token}` |
| Body | JSON（uuid, bar_type, printer_id, data_1~19, status, ...） |

**本機測試頁也走同一端點**（POST `localhost:9200`，Status=2），確保整條路徑可驗證。

### 8.3 中央 API 呼叫（LBSB01 → 中央）

刪除印表機等操作透過 APILB005 單一端點進行（後端 Transaction cascade 清子表）：

```
LBSB01                                     中央 TBMS
──────                                     ──────────
[線上] HTTP DELETE /api/lb/printers/PRN-004
  Authorization: Bearer <硬寫 Token>
                                   ──→ APILB005 後端 Transaction：
                                       ① DELETE FROM DP_COMPDEVICE_LABEL
                                          WHERE PRINTER_ID='PRN-004'
                                       ② DELETE FROM LB_PRINTER
                                          WHERE PRINTER_ID='PRN-004'（硬刪）
                                   ←── { success: true, deleted_label_rows: 3 }

[離線] 不呼叫，排入 PENDING_OPS：
  SEQ=N: DELETE / LB_PRINTER / {"printer_id":"PRN-004"}  ← 對應 APILB005
  → 上線後 _sync_local_to_db() replay（一筆即可）
```

### 8.4 呼叫模式對照表

| 模式 | 方向 | 觸發 | 離線處理 | 範例 |
|------|------|------|---------|------|
| 同步 + 線上偵測 | LBSB01 → 中央 | OffLine Retry Timer（3 分鐘）/ [更新] 按鈕 | 呼叫失敗 → 保持離線、Timer 重試 | APILB001~007 |
| 被動接收 | 中央 → LBSB01 | 中央 SRVLB001 轉發 | Listener 仍運行，但中央不可達 | Task Listener :9200 |
| 本機迴路 | LBSB01 → LBSB01 | 測試頁送件 | 正常可用（localhost） | POST localhost:9200 |
| 自家 Table 寫入 | LBSB01 → local.db（+ 同步時回寫中央）| 使用者操作（新增/改/刪印表機、列印完成）| 寫 Local + 排 PENDING_OPS | LB_PRINTER, LB_PRINT_LOG |

---

## 9. Queue 三層架構

### 9.1 架構總覽

![SRVLB001 架構圖](contracts/SRVLB001-標籤列印通用API.png)

### 9.2 SRVLB001 中央派送流程

外部模組（BC/CP/BS/TL）不直接與 LBSB01 通訊，一律透過中央 SRVLB001 進行路由：

```
Client(BC/CP/BS/TL)  →  中央 SRVLB001  →  LBSB01(:9200)  →  印表機
                        ├─ 解析 PRINTER_ID（SRVDP010）
                        ├─ INSERT LB_PRINT_LOG（Status=0）
                        └─ POST /api/lb/task
```

完整處理流程見 `contracts/srv-contracts.md` §SRVLB001；SRVLB001 內部步驟（判斷格式一/二、POST 錯誤回寫 Log 等）見 [UCLB001](images/uclb001-flow.png) 左側 Block 內 Drill-Down 圖 `SRVLB001-標籤列印通用API`（CompositeStructure）。

> 一台 LBSB01 可管理多台實體印表機，中央以 `LB_PRINTER.SERVER_IP` 決定派送到哪台 LBSB01。

### 9.3 Task Listener 端點規格

LBSB01 啟動時開啟 HTTP Server，接收中央或本機的列印指令：

| 項目 | 值 |
|------|-----|
| Port | **9200**（固定，不可設定） |
| 綁定 | `0.0.0.0:9200` |
| 端點 | `POST /api/lb/task` |
| 認證 | `Authorization: Bearer <token>`（離線時略過驗證） |
| Content-Type | `application/json` |

**Request Body**：

```json
{
  "uuid": "f47ac10b-58cc...",
  "bar_type": "CP11",
  "site_id": "S01",
  "printer_id": "PRN-002",
  "specimen_no": "SPC-2026-0001",
  "data_1": "...", "data_2": "...",
  "status": 0,
  "created_user": "NurseA",
  "server_ip": "192.168.1.10"
}
```

**Response**：

```json
{ "success": true, "uuid": "f47ac10b-58cc..." }
```

**Listener 收到 Task 後的處理流程**（含 GUI Thread-Safe 通知機制）：

```
HTTP POST /api/lb/task 進入
  │
  ├─ 驗證 Bearer Token（離線時略過）
  ├─ 解析 Body JSON → Task
  ├─ local_db.insert_print_log(task)            # 寫 LB_PRINT_LOG_CACHE
  ├─ local_db.enqueue(task)                     # Status=0 → ONLINE_QUEUE / Status=2 → OFFLINE_QUEUE
  ├─ app._task_event_queue.put_nowait("...")    # 放旗標，由 Main Thread poll 後刷新 GUI
  └─ 回傳 { success: true, uuid }
```

### 9.4 GUI 通知機制（Thread-Safe）

Task Listener 運行在背景 Thread，不可直接操作 Tkinter UI。採用 `queue.Queue` + 主 Thread 定時 poll 的模式（見上圖下半部）。

**程式對應**（[task_listener.py](Source/Python/LBSB01/task_listener.py)）：

```python
# Listener Thread 端 — 放旗標進 queue
app._task_event_queue.put_nowait("task_received")

# Main Thread 端 — 定時 poll（main.py:_poll_task_events）
def _poll_task_events(self):
    while True:
        self._task_event_queue.get_nowait()  # 非阻塞
        self._on_task_received()             # 刷新 Queue 畫面
    self.after(200, self._poll_task_events)   # 200ms 後再 poll
```

> **為何不用 `event_generate`？** Tkinter 的 `event_generate` 從 worker thread 呼叫時可能造成 deadlock（主 Thread 若同時在做阻塞操作如 `urlopen`）。queue.Queue 是 Python 內建的 thread-safe 結構，配合 `after()` poll 可確保穩定性。

### 9.5 標籤測試頁走 Queue 路徑

測試頁（[sample_data_print.py](Source/Python/LBSB01/sample_data_print.py)）不另開獨立列印通道，走**同一條 Task Listener 路徑**：

```
測試頁 → POST http://localhost:9200/api/lb/task   (Body: {uuid, bar_type, data_*, status=2, ...})
              │
              └─→ Task Listener 處理（同 §9.3）→ 寫 local.db → Status=2 進 Offline Queue
```

**這樣設計的好處**：
- 驗證整條路徑（Listener → local.db → Queue → GUI）是否正常
- 測試項目不會干擾 Online Queue 的正式列印作業（固定 Status=2 → Offline Queue）
- Offline Queue 可手動雙擊移至 Online Queue 排隊列印

### 9.6 狀態流轉（Status State Machine）

```
          insert_print_log(Status=0)
   ─────→  [0] 待列印 (Online Queue)
              │
              ├─ delete_queue_task(online=True) ──→ [1] 終態（RESULT=-Delete）
              ├─ move_task_to_offline() ─────────→ [2] 離線 (Offline Queue)
              └─ 列印完成 update_print_log ──────→ [1] 終態（RESULT=W..H..L..T..D..）

          insert_print_log(Status=2, 測試頁)
   ─────→  [2] 離線 (Offline Queue)
              │
              ├─ delete_queue_task(online=False) ─→ [1] 終態（RESULT=-Off_DEL）
              └─ move_task_to_online() ──────────→ [0] 待列印 (Online Queue)
```

| 動作 | Status 變更 | RESULT 寫入 | local_db 方法 |
|------|------------|------------|--------------|
| Client 進件 | → 0 | — | `insert_print_log()` + INSERT ONLINE_QUEUE |
| 測試頁進件 | → 2 | — | `insert_print_log()` + INSERT OFFLINE_QUEUE |
| 列印完成 | 0/2 → 1 | `v1.1r1W80H35L40T0D8` | `update_print_log(status=1, result=...)` |
| 移至離線 | 0 → 2 | `v1.1r1-OffLine` | `move_task_to_offline(uuid)` |
| 移至線上 | 2 → 0 | `v1.1r1-OnLine` | `move_task_to_online(uuid)` |
| Online 刪除 | 0 → 1 | `v1.1r1-Delete` | `delete_queue_task(uuid, online=True)` |
| Offline 刪除 | 2 → 1 | `v1.1r1-Off_DEL` | `delete_queue_task(uuid, online=False)` |
| 變更印表機 | 不變 | — | `override_task_printer(uuid, new_pid)` |

### 9.7 Queue 操作對應

| GUI 操作 | 觸發位置 | 動作 |
|---------|---------|------|
| 點選 Queue 項目 | Online/Offline ListBox | 左側明細區帶入該筆資料 |
| 雙擊 Online 項目 | Online ListBox | 移至 Offline Queue（Status 0→2） |
| 雙擊 Offline 項目 | Offline ListBox | 移至 Online Queue（Status 2→0） |
| 刪除單筆 | 按鈕 | Status→1（終態），從 Queue 移除 |
| 變更印表機 | 明細區下拉 + 存檔 | 覆寫 LB_PRINT_LOG_CACHE.PRINTER_ID |
| 列印線上指定項目 | 大按鈕 | 呼叫 GoDEX EZPL 列印 → Status→1 |

### 9.8 RESULT 寫入格式

RESULT 記錄每次狀態異動的來源資訊，格式由 `local_db.build_result()` 產生。

**格式**：

```
[程式版本號]+'-'+[如果勾固定參數本欄為'F']+'W'+[寬]+'H'+[長]+'L'+[左位移]+'T'+[上位移]+'D'+[明暗值]+[備註]
```

**備註代碼**（[備註] 內容，不含前置 `-`；`-` 為格式固定分隔符）：

| 代碼 | 意義 | Status 變更 |
|------|------|-----------|
| `OnLine` | 工作被移至 Online 區 | 保持 |
| `OffLine` | 工作被移至離線區 | → 2 |
| `Delete` | 工作被人工刪除（Online 區） | → 1 |
| `Off_DEL` | 工作在 Offline 區被刪除 | → 1 |

**範例**：

| 場景 | RESULT 範例 | 說明 |
|------|------------|------|
| 列印完成 | `v1.1r1-W80H35L40T0D8` | 帶完整列印參數 |
| 勾選固定參數 | `v1.1r1-FW80H35L40T0D8` | `F` 僅於勾選「固定參數」時加入 |
| 移至離線 | `v1.1r1-OffLine` | 僅帶備註 |
| 移至線上 | `v1.1r1-OnLine` | 僅帶備註 |
| Online 刪除 | `v1.1r1-Delete` | 僅帶備註 |
| Offline 刪除 | `v1.1r1-Off_DEL` | 僅帶備註 |

> 程式版本號取自 `version.py` 的 `VERSION` 常數（目前 `v1.1r1`），用於追蹤哪個版本的程式處理了該筆資料。

---

## 10. 標籤印表機設定

### 操作對應 local_db 方法

印表機設定為**自家模組直接操作**（不經 SRV），透過 `local_db.py` 讀寫 Local Cache：

| 操作 | local_db 方法 | 離線時 |
|------|--------------|--------|
| 開啟頁面 / 重新整理 | `list_printers(site_id)` | 讀 Local Cache，正常可用 |
| 新增 → 存檔 | `add_printer(data, online)` | 寫 Cache + 排 PENDING_OPS |
| 編輯 → 存檔 | `save_printer(data, online)` | 寫 Cache + 排 PENDING_OPS |
| 刪除 | `remove_printer(site, pid, online)` | 刪 Cache + 排一筆 DELETE PENDING_OPS（對應 APILB005，後端 cascade 清子表）|

> 刪除印表機由 APILB005 後端 Transaction cascade（先清 DP_COMPDEVICE_LABEL 子表再硬刪 LB_PRINTER），LBSB01 端只需排一筆 DELETE PENDING_OPS。

### Driver / 印表機 IP 互斥

| 連線方式 | Driver 欄位 | 印表機 IP 欄位 |
|---------|------------|---------------|
| USB | 填 `USB` | 留空（鎖定） |
| 藍芽 | 填 設備名稱 | 留空（鎖定） |
| IP 網路 | 留空（鎖定） | 填 IP 位址 |

### 新增預設值

| 欄位 | 預設 | 來源 |
|------|------|------|
| site_id | session.site_id | config.ini |
| server_ip | 本機 IP | `socket` 自動取得 |
| driver | 空白 | — |
| darkness | 12 | — |

---

## 11. 標籤測試頁

- 測試頁 Call **SRVLB001** with `status=2`（直接進 Offline Queue）
- 與 Client 端走同一條 SRV，不另開獨立列印路徑
- 測試項目在主畫面 Offline Queue 可見

---

## 12. 編譯為 EXE

預計使用 PyInstaller 或 Nuitka 編譯：

```bash
# PyInstaller 範例
pyinstaller --onefile --windowed --name LBSB01 main.py
```

部署結構：
```
部署目錄/
├── LBSB01.exe          ← 執行檔
├── config.ini          ← 設定檔（首次自動建立或隨附）
├── app.log             ← 執行紀錄（自動產生）
└── EzGoLabel_Wrap.dll  ← GoDEX DLL（依平台）
```

> `config.ini` 與 `app.log` 必須與 exe 同目錄；DLL 路徑依 GoDEX SDK 設定。

---

## 13. 注意事項與規則

### 必遵守

1. **不可直接連中央 DB** — 所有存取一律透過 SRV（stub 或 HTTP）
2. **所有子視窗為 Modal** — `transient(master)` + `grab_set()`，開啟期間主畫面不可操作
3. **SRV 命名規範** — `SRV{模組代碼}{seq:03}-{說明}`（如 SRVLB001-標籤列印通用API）
4. **Status 語意** — 0=待列印、1=終態、2=離線區；具體動作由 RESULT 備註區分
5. **config.ini [token] 不可手動修改** — 由程式認證後自動回寫

### 開發流程

1. 以 stub 模式開發 UI 與流程邏輯（不需中央服務）
2. 實作 SRV HTTP Client（替換 stub → 正式呼叫）
3. 聯調測試（連接中央 DP/LB Services）
4. 編譯為 .exe + config.ini 隨附部署

### 參考文件

| 文件 | 路徑 | 用途 |
|------|------|------|
| 操作手冊 | `docs/specs/lb/LBSB01-操作手冊.md` | 操作人員使用說明 |
| 整合指南 | `docs/specs/lb/SRVLB001-標籤列印整合指南.md` | 外部模組呼叫 SRVLB001 |
| SRV 契約 | `docs/specs/lb/contracts/srv-contracts.md` | 完整 I/O 規格 |
| 功能規格 | `docs/specs/lb/spec.md` | SA 設計 |
| ERD / 欄位明細 | `docs/specs/lb/data-model.md` | 資料模型與實體關聯（含 Mermaid ERD） |
