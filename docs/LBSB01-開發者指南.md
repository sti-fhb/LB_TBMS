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
8. [Queue 三層架構](#8-queue-三層架構)
9. [標籤印表機設定](#9-標籤印表機設定)
10. [標籤測試頁](#10-標籤測試頁)
11. [編譯為 EXE](#11-編譯為-exe)
12. [注意事項與規則](#12-注意事項與規則)

---

## 1. 專案架構

```
_LB/
├── Source/Python/LBSB01/        ← Python 原始碼
│   ├── main.py                  ← 程式進入點（App 主視窗）
│   ├── login.py                 ← 認證模組（APIDP001 自動認證 + config.ini）
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
│   ├── LBSB01-操作手冊.md       ← 操作人員用
│   ├── LBSB01-開發者指南.md     ← ← 本文件
│   └── specs/lb/
│       ├── spec.md              ← 功能規格
│       └── contracts/
│           └── srv-contracts.md ← SRV 契約（完整 I/O 定義）
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

首次執行會自動建立 `config.ini`（預設值）。修改 `[site]` 與 `[api]` 後重啟即可。

### 2.4 開發用 stub 模式

目前所有 SRV 呼叫為 **Python stub**（本地模擬，不需中央服務）。stub 行為：

| SRV | stub 行為 |
|-----|----------|
| APIDP001 | code=LB_PRINT + passcode=stark123 → 回模擬 token |
| SRVLB091 | 本地 list 唯一性檢查 |
| SRVLB092 | 直接回 OK |
| SRVLB093 | 從 `_sample_rows()` 篩選 site_id |
| SRVLB094 | 驗證 IP/Driver 互斥後回 OK |
| SRVDP018 | 直接回 OK |

> stub 讓開發者不需中央服務即可開發 UI 與流程邏輯。正式上線時將 stub 替換為 HTTP 呼叫。

---

## 3. config.ini 設定

設定檔位於**執行檔同目錄**，INI 格式（UTF-8）。

```ini
; LBSB01 標籤服務程式設定檔
; [site] 與 [api] 由管理者設定；[token] 由程式自動回寫

[site]
site_id = S01
site_name = 總院捐血中心

[api]
url = http://192.168.1.100:8000/api/ext/auth/token

[token]
; 以下由程式認證後自動回寫，不需手動編輯
value =
expires_in = 3600
```

| Section | Key | 說明 | 維護者 |
|---------|-----|------|--------|
| `[site]` | `site_id` | 站點代碼（須與中央 DP 一致） | 管理者 |
| `[site]` | `site_name` | 站點中文名稱 | 管理者 |
| `[api]` | `url` | APIDP001 認證端點 URL | 管理者 |
| `[token]` | `value` | TOKEN（程式自動回寫） | 程式 |
| `[token]` | `expires_in` | TOKEN 有效秒數 | 程式 |

> 程式啟動時若 config.ini 不存在，會自動建立預設檔。缺漏的 key 也會自動補齊。

---

## 4. 啟動流程與認證

```
main.py 啟動
  │
  ├─ 顯示 Splash：「正在登入主系統 DB ...」
  │
  ├─ login.authenticate()
  │    ├─ 讀 config.ini（[site] + [api]）
  │    ├─ Call APIDP001（POST /api/ext/auth/token）
  │    │    Body: { code: "LB_PRINT", passcode: "stark123" }
  │    │
  │    ├─ 成功 → Session(online=True)，token 回寫 config.ini
  │    └─ 失敗 → Session(online=False, error_message=原因)
  │
  ├─ 移除 Splash
  │
  ├─ online=True  → 顯示「認證成功」+ 標題【線上】（綠色）
  └─ online=False → 顯示「認證失敗（離線模式）」+ 標題【離線】（紅色）
       │
       └─ 程式仍可執行（僅本地 Queue 功能可用）
```

### Session 結構

```python
@dataclass
class Session:
    site_id: str          # 站點代碼（from config.ini）
    site_name: str        # 站點名稱
    token: str            # APIDP001 TOKEN（離線時為空）
    expires_in: int       # TOKEN 有效秒數
    online: bool          # True=線上 / False=離線
    error_message: str    # 失敗原因（online=True 時為空）
```

### 認證參數

| 項目 | 值 | 來源 |
|------|-----|------|
| CODE | `LB_PRINT` | login.py 常數 |
| PASSCODE | `stark123` | login.py 常數 |
| EA 對應 | `{1BEF51C7-CD73-44e6-8D3B-CD134B3D388D}` | 標籤印表機服務登入 |
| DP 參數表 | `DP_PARAM_D` WHERE `PARAM_ID='DP_EXT_API_KEY'` AND `PARAM_KEY='LB_PRINT'` | 中央 DB |

---

## 5. DB 存取規則與 SRV 架構

### 核心規則

> **自家模組（LB）可直接存取自家 Table；跨模組 Table 仍需透過 SRV。**

| 存取對象 | 方式 | 說明 |
|---------|------|------|
| **LB_PRINTER**（自家） | 直接 SQL | 透過 `local_db.py` 讀寫本地 SQLite Cache，線上時同步中央 |
| **LB_PRINT_LOG**（自家） | 直接 SQL | 同上 |
| **DP_COMPDEVICE_LABEL**（跨模組） | Call **SRVDP018** | 離線時排入 PENDING_OPS |
| **其他模組呼叫 LB** | 透過 **SRVLB001** | LB 提供的對外服務（列印指令接收） |

```
LBSB01 (Python)
  │
  ├─ APIDP001（啟動認證取 TOKEN）
  │
  ├─ local_db.py（本地 SQLite）
  │   ├─ LB_PRINTER_CACHE      ← 自家 Table 直接讀寫
  │   ├─ LB_PRINT_LOG_CACHE    ← 自家 Table 直接讀寫
  │   ├─ ONLINE_QUEUE / OFFLINE_QUEUE
  │   └─ PENDING_OPS           ← 離線暫存佇列
  │
  ├─ 線上時：直接寫中央 LB Table + Call 跨模組 SRV
  └─ 離線時：寫 Local Cache + 排入 PENDING_OPS
                                     │
              上線後 replay ──────────┘
```

### SRV 清單（僅保留對外服務 + 跨模組呼叫）

| 編碼 | 名稱 | 類別 | 說明 |
|------|------|------|------|
| **SRVLB001** | 標籤列印通用API | 對外提供 | 其他模組（BC/CP/BS/TL）Call LB 送列印指令 |
| **APIDP001** | 外部系統資料接收介面 | 跨模組呼叫 | 啟動認證（CODE=LB_PRINT） |
| **SRVDP018** | 刪除元件設備標籤對應 | 跨模組呼叫 | 刪除印表機時先清 DP 子表 |

> 自家 Table 的 CRUD（新增/查詢/更新/刪除印表機、LOG 更新）不需 SRV，由 `local_db.py` 直接操作。

---

## 6. 離線暫存與同步架構（local.db）

### 設計原則

LBSB01 為 24x7 常駐程式，必須在**網路中斷時仍能正常運作**。所有資料操作遵循：

1. **先寫 Local**（即時生效，畫面不卡）
2. **線上 → 同步寫中央**（直接 SQL 或 Call SRV）
3. **離線 → 排入 PENDING_OPS**（上線後依序 replay）

### local.db 結構（SQLite，WAL mode）

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

### 操作流程

```
使用者操作（新增/修改/刪除印表機、列印完成更新 LOG...）
  │
  ├─ 寫入 Local Cache（即時生效）
  │   └─ LB_PRINTER_CACHE / LB_PRINT_LOG_CACHE
  │
  ├─ session.online?
  │   ├─ YES → 直接寫中央 DB（或 Call 跨模組 SRV）
  │   └─ NO  → INSERT INTO PENDING_OPS（暫存等 replay）
  │
  ▼
```

### 上線後同步（_sync_local_to_db）

```
重連成功（每 60 秒自動嘗試）
  │
  ├─ 1. 讀 PENDING_OPS WHERE STATUS=0 ORDER BY SEQ
  │
  ├─ 2. 逐筆 replay：
  │      ├─ OP_TYPE = INSERT/UPDATE/DELETE
  │      │   → 直接 SQL 寫中央 LB Table
  │      │
  │      └─ OP_TYPE = CALL_SRV
  │          → HTTP Call 跨模組 SRV（如 SRVDP018）
  │
  ├─ 3. 成功 → STATUS=1；失敗 → STATUS=2（保留重試）
  │
  └─ 4. 從中央 DB 全量刷新 Local Cache（確保一致）
```

### 離線範例：刪除印表機

```python
# local_db.remove_printer(site_id, printer_id, online=False)

# 1. 刪 Local Cache（畫面即時反映）
DELETE FROM LB_PRINTER_CACHE WHERE PRINTER_ID='PRN-004'

# 2. 排入 PENDING_OPS（順序保證）
SEQ=1: CALL_SRV / SRVDP018 / {"site_id":"S01","printer_id":"PRN-004"}  ← 先清 DP 子表
SEQ=2: DELETE   / LB_PRINTER / {"printer_id":"PRN-004"}                 ← 再刪主表

# 3. 上線後按 SEQ 順序 replay
```

### local_db.py 主要 API

| 方法 | 用途 |
|------|------|
| `add_printer(data, online)` | 新增印表機：寫 Cache + 離線排 PENDING_OPS |
| `save_printer(data, online)` | 更新印表機：寫 Cache + 離線排 PENDING_OPS |
| `remove_printer(site, pid, online)` | 刪除印表機：刪 Cache + 離線排 SRVDP018 + DELETE |
| `list_printers(site_id)` | 查詢站點印表機（讀 Local Cache） |
| `enqueue_op(op_type, target, payload)` | 直接排入 PENDING_OPS |
| `get_pending_ops()` | 取得待同步操作清單 |
| `mark_op_synced(seq)` / `mark_op_failed(seq)` | 標記同步結果 |
| `replace_all_printers(site_id, list)` | 全量刷新 Cache（上線同步後用） |

### 衝突處理

| 情境 | 策略 |
|------|------|
| 離線期間修改了印表機，中央也被改 | 上線同步後**全量刷新 Cache**，以中央為準 |
| PENDING_OPS 某筆 replay 失敗 | 標記 STATUS=2，不阻塞後續；下次同步重試 |
| 離線刪了印表機，但中央已不存在 | DELETE 失敗（不存在）→ 忽略，標記 STATUS=1 |

---

## 7. SRV 清單速查

### 對外提供（其他模組 Call LB）

| 編碼 | 名稱 | 說明 |
|------|------|------|
| **SRVLB001** | 標籤列印通用API | BC/CP/BS/TL 送列印指令；Status=0 進 Online、Status=2 進 Offline |

### 跨模組呼叫（LB Call DP）

| 編碼 | 名稱 | 呼叫場景 | 離線處理 |
|------|------|---------|---------|
| **APIDP001** | 外部系統資料接收介面 | 啟動認證 + 60 秒重連 | 認證失敗 → 離線模式 |
| **SRVDP018** | 刪除元件設備標籤對應 | 刪除印表機時 | 排入 PENDING_OPS |

### 自家模組直接操作（不需 SRV）

| Table | 操作 | 模組 |
|-------|------|------|
| LB_PRINTER | CRUD | `local_db.py` 直接讀寫 |
| LB_PRINT_LOG | INSERT / UPDATE | `local_db.py` 直接讀寫 |

> 完整 SRV 契約見 `docs/specs/lb/contracts/srv-contracts.md`

---

## 8. Queue 三層架構

```
Client 端（BC/CP/BS/TL）
  │
  │ Call SRVLB001 (Status=0)
  ▼
┌─────────────────────────────┐
│  Online Queue（本地暫存）     │  Status = 0（待列印）
│  自動排隊 / 手動選取列印      │
├─────────────────────────────┤
│        ↕ 雙擊移動            │
├─────────────────────────────┤
│  Offline Queue（本地暫存）    │  Status = 2（離線區）
│  離線重印 / 測試頁進件        │
└─────────────────────────────┘
  │
  │ 列印完成 / 刪除 → Call SRVLB011
  ▼
┌─────────────────────────────┐
│  DB Log（中央 LB_PRINT_LOG） │  Status = 1（終態）
└─────────────────────────────┘
```

### 狀態流轉

| 動作 | Status 變更 | SRV | RES_ID 備註 |
|------|------------|-----|------------|
| Client 進件 | → 0 | SRVLB001 | — |
| 測試頁進件 | → 2 | SRVLB001 | — |
| 列印完成 | 0/2 → 1 | SRVLB011 | W/H/L/T/D 列印參數 |
| 移至離線 | 0 → 2 | SRVLB011 | `-OffLine` |
| 移至線上 | 2 → 0 | SRVLB011 | `-OnLine` |
| Online 刪除 | 0 → 1 | SRVLB011 | `-Delete` |
| Offline 刪除 | 2 → 1 | SRVLB011 | `-Off_DEL` |

---

## 9. 標籤印表機設定

### 功能對應 SRV

| 操作 | SRV | 說明 |
|------|-----|------|
| 開啟頁面 / 重新整理 | SRVLB093 | 依 session.site_id 篩選 |
| 新增 → 存檔 | SRVLB091 | 含編號唯一性檢查 |
| 編輯 → 存檔 | SRVLB094 | 含 IP/Driver 互斥驗證 |
| 刪除 | SRVDP018 → SRVLB092 | 兩段式：先刪 DP 對應再刪印表機 |

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

## 10. 標籤測試頁

- 測試頁 Call **SRVLB001** with `status=2`（直接進 Offline Queue）
- 與 Client 端走同一條 SRV，不另開獨立列印路徑
- 測試項目在主畫面 Offline Queue 可見

---

## 11. 編譯為 EXE

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

## 12. 注意事項與規則

### 必遵守

1. **不可直接連中央 DB** — 所有存取一律透過 SRV（stub 或 HTTP）
2. **所有子視窗為 Modal** — `transient(master)` + `grab_set()`，開啟期間主畫面不可操作
3. **SRV 命名規範** — `SRV{模組代碼}{seq:03}-{說明}`（如 SRVLB091-新增印表機）
4. **Status 語意** — 0=待列印、1=終態、2=離線區；具體動作由 RES_ID 備註區分
5. **config.ini [token] 不可手動修改** — 由程式認證後自動回寫

### 開發流程

1. 以 stub 模式開發 UI 與流程邏輯（不需中央服務）
2. 實作 SRV HTTP Client（替換 stub → 正式呼叫）
3. 聯調測試（連接中央 DP/LB Services）
4. 編譯為 .exe + config.ini 隨附部署

### 參考文件

| 文件 | 路徑 | 用途 |
|------|------|------|
| 操作手冊 | `docs/LBSB01-操作手冊.md` | 操作人員使用說明 |
| SRV 契約 | `docs/specs/lb/contracts/srv-contracts.md` | 完整 I/O 規格 |
| 功能規格 | `docs/specs/lb/spec.md` | SA 設計 |
| EA Model | `C:\TSBMS\EA_Model\TSBMS三總捐供血R.eap` | 流程圖 / ERD（需 EA 授權） |
