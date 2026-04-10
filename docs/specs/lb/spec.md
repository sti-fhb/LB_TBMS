# 功能規格：標籤列印模組（LB）

**目錄**: `specs/lb/`
**建立日期**: 2026-04-10
**狀態**: 草稿
**來源**: VB6 ALLB01-BarcodeServer 移植 + 新架構設計
**程式代號**: LBSB01-標籤服務程式

---

## 系統概述

LBSB01 為部署於各工作站的**標籤列印客戶端程式**，負責接收列印指令、管理列印佇列、驅動 GoDEX 條碼印表機輸出血品/檢體/設備標籤。

### 核心特性

- **本地運作**：不直接存取中央資料庫，所有資料交換透過 API
- **離線容錯**：網路斷線時仍可從離線佇列列印，恢復後自動同步
- **指令可追溯**：所有進出與異動皆透過 API 記錄至中央 DB

---

## 三層 Queue 架構

### 架構圖

```
                    ┌─────────────────────┐
  API 傳入指令 ──→  │  1. Online Queue     │ ──→ 印表機列印
                    │     (本地暫存)       │
                    └──────────┬──────────┘
                               │ 可搬移
                    ┌──────────▼──────────┐
                    │  2. Offline Queue    │ ──→ 印表機列印
                    │     (本地暫存)       │
                    └─────────────────────┘

  指令進入/異動/完成/刪除 ──→  ┌──────────────────────┐
                              │  3. DB Log Queue      │ ──→ Call API 寫入中央 DB
                              │     (本地暫存,         │
                              │      背景非同步消化)    │
                              └──────────────────────┘
```

### 本地持久化（防斷電）

三個 Queue 的內容皆持久化於本地 SQLite（檔案型資料庫），確保斷電或程式異常重啟後資料不遺失。

**為什麼 Queue 不實作在中央 DB？**

LBSB01 為部署於各工作站的**獨立列印主機**。實際運作場景：

```
  中央 Server (DB + API)
         │
    WAN / VPN（可能斷線）
         │
  ┌──────┴──────┐
  │  工作站 LAN  │ ← Local LAN 有通
  │  ┌────────┐ │
  │  │ LBSB01 │ │ ← 列印主機
  │  └────┬───┘ │
  │       │     │
  │  ┌────┴───┐ │
  │  │ 印表機  │ │ ← GoDEX 條碼機（USB / LAN IP）
  │  └────────┘ │
  └─────────────┘
```

- **斷網時**：Local LAN 仍通，LBSB01 仍可驅動印表機列印
- **Queue 若在中央 DB**：斷網 → 無法取得待印資料 → 無法列印
- **Queue 在 Local SQLite**：斷網 → 已接收的指令仍在本地 → 照常列印 → 列印結果暫存 DB Log Queue → 恢復網路後自動回寫中央 DB

### Queue 1: Online Queue（線上排隊列印佇列）

**職責：負責對印表機作輸出。** 這是唯一會驅動印表機列印的佇列。

| 項目 | 說明 |
|------|------|
| 資料來源 | 外部系統透過 API 傳入列印指令 |
| 儲存位置 | 本地 SQLite（持久化，防斷電） |
| 職責 | **唯一負責驅動印表機輸出的佇列** |
| 列印方式 | 選取後按「列印線上指定項目」執行；Auto 模式下自動依序消化 |
| 列印失敗處理 | 目標印表機故障（未開機/卡紙/離線）時，**自動將該 Task 移至 Offline Queue**，使佇列中下一個 Task 可繼續列印，不阻塞整條佇列 |
| 其他操作 | 手動刪除、手動搬移至 Offline Queue |

### Queue 2: Offline Queue（故障暫存佇列）

**職責：暫存印表機故障時無法列印的 Task。** 故障排除後由操作者將 Task 移回 Online Queue 重新列印。

| 項目 | 說明 |
|------|------|
| 資料來源 | 列印失敗時由 Online Queue **自動移入**；或操作者手動搬移 |
| 儲存位置 | 本地 SQLite（持久化，防斷電） |
| 職責 | **暫存故障 Task，不直接列印** |
| 操作 | 故障排除後，操作者將 Task 移回 Online Queue（雙擊）重新列印；可變更目標印表機後再移回；可刪除 |
| 不會列印 | Offline Queue 本身**不驅動印表機**，必須移回 Online Queue 才能列印 |

**Online / Offline Queue 協作流程：**

```
Online Queue                          Offline Queue
┌──────────┐                         ┌──────────┐
│ Task A   │──→ 列印 ──→ 成功 ✓     │          │
│ Task B   │──→ 列印 ──→ 失敗 ✗     │          │
│          │      │ 印表機故障        │          │
│          │      └──→ 自動移入 ───→ │ Task B   │
│ Task C   │──→ 列印 ──→ 成功 ✓     │          │（不阻塞）
│ Task D   │──→ 列印 ──→ 成功 ✓     │          │
└──────────┘                         │          │
                                     │ Task B   │ ← 故障排除後
              ┌──── 操作者移回 ────── │          │    操作者移回
              ▼                      └──────────┘
┌──────────┐
│ Task B   │──→ 列印 ──→ 成功 ✓
└──────────┘
```

### Queue 3: DB Log Queue（資料庫記錄佇列）

| 項目 | 說明 |
|------|------|
| 觸發時機 | 任何指令進入 Online Queue 時立即寫入（同步）；後續異動/完成/刪除時追加 |
| 儲存位置 | 本地 SQLite（持久化，防斷電） |
| 消化方式 | 背景 Thread 非同步呼叫中央 API 寫入 DB |
| 重試機制 | API 呼叫失敗時保留在佇列，定時重試直到成功 |
| 斷網行為 | 累積在本地 SQLite，恢復網路後自動批次回寫 |

### 為什麼需要 DB Log Queue？

**設計理由**：

1. **明確記錄 Client 傳進來的指令** — 每一筆 API 傳入的列印指令都必須被記錄在中央 DB，無論最終是否被列印
2. **指令可被修改覆蓋** — Queue 中的指令可能被修改（換印表機）、搬移（Online→Offline）、最終送出或被刪除，這些異動都必須記錄在 DB 的同一筆 Record 上
3. **斷電保護** — 如果等 Queue 消化印出才記錄 DB，中間若斷電該筆資料就找不到。因此**指令一進來就同步寫入 DB Log Queue**（本地持久化），再由背景 Thread 呼叫 API 回寫中央 DB
4. **斷網容錯** — 即使中央 API 不通，DB Log Queue 仍持久保存在本地 SQLite，恢復網路後自動回寫，不會遺失任何記錄

### 指令生命週期與 DB Log 記錄時機

```
API 傳入指令
  │
  ├─→ 寫入 Online Queue（本地 SQLite）
  ├─→ 寫入 DB Log Queue（ACTION=RECEIVED）
  │     └─→ 背景 Thread → Call API 寫入中央 DB
  │
  ▼ Online Queue 消化列印
  │
  ├─ 列印成功 ──→ 從 Online Queue 移除
  │               └─→ DB Log Queue（ACTION=PRINTED）
  │
  ├─ 列印失敗（印表機故障）──→ 自動移至 Offline Queue
  │                            └─→ DB Log Queue（ACTION=PRINT_FAILED, MOVED_OFFLINE）
  │                            ※ 不阻塞，Online Queue 繼續消化下一個 Task
  │
  ▼ Offline Queue 中的 Task
  │
  ├─ 故障排除 → 操作者移回 Online Queue → DB Log Queue（ACTION=MOVED_ONLINE）
  │              └─→ 回到 Online Queue 排隊重新列印
  ├─ 變更印表機 → DB Log Queue（ACTION=MODIFIED）
  └─ 刪除       → DB Log Queue（ACTION=DELETED）

  ▼ 其他操作（Online Queue 或 Offline Queue 皆適用）
  │
  ├─ 手動搬移至 Offline → DB Log Queue（ACTION=MOVED_OFFLINE）
  └─ 手動刪除           → DB Log Queue（ACTION=DELETED）
```

**本作業不可直接 Access DB** — 所有 DB 操作必須透過中央 API 呼叫，由後端統一管理。

---

## 印表機支援

| 項目 | 說明 |
|------|------|
| 印表機品牌 | GoDEX |
| 控制語言 | EZPL (GoDEX Extended Print Language) |
| DLL | EZio64.dll（64-bit）/ Ezio32.dll（32-bit），自動偵測 |

### 三種連線方式

每一台裝有 LBSB01 的服務主機，其下皆會接標籤印表機。依實際部署環境，印表機有三種連接方式：

| # | 連線方式 | 接法 | 驅動方式 | DLL 呼叫 |
|---|---------|------|---------|---------|
| 1 | **TCP/IP（固定 IP）** | 印表機接在 LAN 上，設定固定 IP | 直接打 IP + Port 輸出 | `OpenNet(ip, port)` |
| 2 | **USB** | 實體 USB 線路連到主機 | DLL 透過 USB Port 輸出 | `openport("6")` 或 `OpenUSB(usbID)` |
| 3 | **藍牙（Bluetooth）** | 與主機藍牙配對，OS 層命名印表機 | 以 OS 印表機名稱連線輸出 | `OpenDriver(printerName)` |

**部署拓撲：**

```
  ┌─────────────────────────────────────┐
  │          LBSB01 服務主機             │
  │                                     │
  │  ┌─── USB ──→ [GoDEX 印表機 A]     │  ← 實體線路
  │  │                                  │
  │  ├── LAN IP → [GoDEX 印表機 B]     │  ← 固定 IP（如 192.168.1.50:9100）
  │  │                                  │
  │  └── 藍牙 ──→ [GoDEX 印表機 C]     │  ← OS 命名（如 "GoDEX_BT_01"）
  │                                     │
  └─────────────────────────────────────┘
```

### 印表機主檔（中央 DB Table — 全域共用）

印表機主檔儲存在**中央 DB**，為全域 Table，所有 AP 皆可參考（查詢可用印表機清單）。但**印表機設定功能只實作在 LBSB01 上**，原因是印表機實體接在 Local 主機，只有 LBSB01 能實際驅動與校正。

LBSB01 **不直接 Access DB**，而是透過 API 取得/更新印表機清單並快取於本地。

### 印表機定址格式

印表機接在 Local 主機上，完整定址需包含兩部分：**Printer Server（哪台主機）** + **印表機連線方式（怎麼接）**。

```
定址格式：
  [Printer Server IP] + [#{Windows Printer Name} / 'USB']
  [Printer Server IP] + {Printer IP}    ← 若有填則優先採用
```

**解析規則：**

| 情境 | PRINTER_IP 欄位 | 定址方式 | 說明 |
|------|----------------|---------|------|
| 印表機有固定 IP | `192.168.1.50` | 直接連 Printer IP:Port | **優先採用**，不經 Server 轉發 |
| USB 直連 | （空白） | Server IP + `USB` | LBSB01 主機 USB Port 輸出 |
| 藍牙/驅動程式 | （空白） | Server IP + `#GoDEX_BT_01` | OS 層印表機名稱（# 前綴識別） |

**定址範例：**

```
PRN-001: 192.168.1.10 + USB
  → LBSB01 主機(192.168.1.10) 的 USB Port 直連印表機

PRN-002: 192.168.1.10 + 192.168.1.50
  → 印表機自己有 IP(192.168.1.50)，直接連（優先）
  → Printer Server IP(192.168.1.10) 記錄歸屬但不經轉發

PRN-003: 192.168.1.10 + #GoDEX_MX30_BT01
  → LBSB01 主機(192.168.1.10) 透過 OS 藍牙印表機名稱連線
```

**DB Table 結構（LB_PRINTER）：**

| 欄位 | 型態 | 必填 | 說明 | 範例 |
|------|------|------|------|------|
| PRINTER_ID | VARCHAR(20) | Y | 印表機代碼（PK，唯一識別） | `PRN-001` |
| PRINTER_NAME | VARCHAR(100) | Y | 印表機名稱 | `血庫一樓條碼機` |
| SITE_ID | VARCHAR(10) | Y | 所屬站點 FK→DP_SITE | `S01` |
| SERVER_IP | VARCHAR(45) | Y | Printer Server IP（LBSB01 主機 IP） | `192.168.1.10` |
| PRINTER_IP | VARCHAR(45) | N | 印表機固定 IP（**有填則優先採用**） | `192.168.1.50` |
| PRINTER_PORT | INT | N | 印表機 Port（PRINTER_IP 有填時，預設 9100） | `9100` |
| PRINTER_DRIVER | VARCHAR(100) | N | Windows 印表機名稱（USB/藍牙時，# 前綴） | `#GoDEX_MX30_BT01` 或 `USB` |
| SHIFT_LEFT | INT | N | 左位移（公差校正，預設 0） | `2` |
| SHIFT_TOP | INT | N | 上位移（公差校正，預設 0） | `-3` |
| DARKNESS | INT | N | 明暗（公差校正，預設 12） | `14` |
| PRINTER_MODEL | VARCHAR(100) | N | 印表機型號 | `GoDEX EZ2250i` |
| IS_ACTIVE | INT | Y | 啟用狀態（1=啟用, 0=停用） | `1` |
| NOTE | VARCHAR(200) | N | 說明 | `血庫一樓護理站旁` |

**連線方式解析邏輯（LBSB01 列印時）：**

```python
if printer.PRINTER_IP:
    # 有填印表機 IP → 優先直連（TCP/IP）
    link_type = LinkType.TCP
    target_ip = printer.PRINTER_IP
    target_port = printer.PRINTER_PORT or 9100
elif printer.PRINTER_DRIVER == "USB":
    # USB 直連
    link_type = LinkType.USB
elif printer.PRINTER_DRIVER.startswith("#"):
    # OS 印表機名稱（藍牙/驅動程式）
    link_type = LinkType.BT
    bt_name = printer.PRINTER_DRIVER[1:]  # 去掉 # 前綴
```

**Client 下指令時帶印表機編號：**

外部系統透過 API 傳入列印指令時，Task 中包含 `PRINTER_ID` 欄位，指定該筆標籤要由哪台印表機輸出。LBSB01 收到後依 `PRINTER_ID` 查本地快取的印表機設定，解析定址方式，取得連線參數與公差參數。

```
Client API 傳入 Task
  │
  │  { type: "CP11", bag_no: "...", printer_id: "PRN-002", ... }
  │
  ▼
LBSB01 收到 → 寫入 Online Queue
  │
  ▼ 列印時
  │
  ├─ 查本地印表機快取: PRINTER_ID = "PRN-002"
  │   → SERVER_IP=192.168.1.10, PRINTER_IP=192.168.1.50, PORT=9100
  │   → PRINTER_IP 有值 → 優先直連 TCP/IP
  │   → SHIFT_LEFT=2, SHIFT_TOP=-3, DARKNESS=14
  │
  ├─ GodexPrinter(LinkType.TCP).open(ip="192.168.1.50", tcp_port=9100)
  ├─ label_setup(width=80, height=75, gap=3, darkness=14)
  ├─ 列印（帶入 shift_left=2, shift_top=-3）
  └─ close()
```

**印表機清單同步機制：**

| 時機 | 動作 |
|------|------|
| LBSB01 啟動時 | Call API 取得印表機清單 → 寫入本地快取（SQLite） |
| 定時（每 N 分鐘） | 背景 Thread 呼叫 API 更新本地快取 |
| 網路斷線時 | 使用本地快取（最後一次成功同步的資料） |
| Menu「設定→印表機設定」 | 手動觸發同步 + 顯示本地快取清單 |

> 三種連線方式都必須被測試覆蓋（TCP/IP、USB、藍牙各至少一台實機測試）。

### DLL 函式對照

| DLL 函式 | Python 封裝 | 用途 |
|----------|------------|------|
| `openport` / `closeport` | `GodexPrinter.open()` / `.close()` | 連線管理 |
| `sendcommand` | `GodexPrinter._send_cmd()` | 送出控制指令 |
| `setup` | `GodexPrinter.label_setup()` | 標籤設定（尺寸/間隙/明暗/速度） |
| `ecTextOut` | `GodexPrinter.text_out()` | TrueType 文字輸出 |
| `ecTextOutR` | `GodexPrinter.text_out_r()` | 旋轉文字 |
| `ecTextOutFine` | `GodexPrinter.text_out_fine()` | 精細文字（反白/底線/斜體） |
| `Bar` | `GodexPrinter.barcode()` | 條碼輸出（Code 128 等） |
| `putimage` | `GodexPrinter.put_image()` | 圖片輸出 |
| `DrawHorLine` / `DrawVerLine` | `GodexPrinter.draw_hor_line()` / `.draw_ver_line()` | 畫線 |
| `DrawRec` | `GodexPrinter.draw_rec()` | 畫矩形 |

---

## 標籤類型

標籤定義儲存於 EA 代碼表「標籤類別」(Code: LB_TYPE)，共 16 種：

| 群組 | Code | 名稱 | 寬(mm) | 長(mm) |
|------|------|------|--------|--------|
| CP | CP01 | 血品小標籤 | 80 | 35 |
| CP | CP02 | 血品小標籤A | 80 | 35 |
| CP | CP11 | 血品核對標籤-合格 | 80 | 75 |
| CP | CP12 | 血品核對標籤-特殊標識 | 80 | 75 |
| CP | CP19 | 血品核對標籤-不適輸用 | 80 | 75 |
| CP | CP91 | 成分藍色籃號 | 80 | 35 |
| CP | CP92 | 細菌小標籤 | 45 | 15 |
| BC | BC01 | 檢體小標籤 | 45 | 15 |
| BC | BC02 | 187標籤 | 80 | 35 |
| BS | BS01 | 運送器材借用標籤 | 80 | 75 |
| BS | BS02 | 運送器材條碼 | 80 | 35 |
| BS | BS03 | 血品裝箱大標籤 | 100 | 200 |
| BS | BS04 | 供應籃號標籤 | 80 | 75 |
| BS | BS05 | 供應特殊血品標籤 | 80 | 75 |
| BS | BS07 | 血品裝箱小標籤 | 80 | 35 |
| TL | TL01 | 檢驗檢體標籤 | 45 | 15 |

### 字型對照

| 代號 | 字型名稱 | 用途 |
|------|---------|------|
| sFont0 | 標楷體 | 一般文字 |
| sFont1 | 細明體 | 血品名稱（旋轉文字） |
| sFont2 | 微軟正黑體 | — |
| sFontB | Arial Black | 粗體文字 |
| sFontS | Arial Rounded MT Bold | 血型（Rh+ 實心） |
| sFontEpt | Swis721 BdOul BT | 血型（Rh- 空心字） |

---

## 畫面結構

### LBSB01 主畫面

```
┌────────────────────────────────────────────────────────────┐
│ LBSB01-標籤服務程式   ○USB ○IP   □印出後清除 □Auto     時間│
├──────────────────────┬─────────────────────────────────────┤
│ 線上列印項目明細 (A) │ 線上排隊列印項目 (Online Queue) (B) │
│ 時間序/條碼種類/     │ [ListBox]                           │
│ 待列印張數/列印者/   │ [     列印線上指定項目     ]         │
│ 印表機編號/UUID      │                                     │
│ 指定印表機 [▼]      │                                     │
├──────────────────────┴─────────────────────────────────────┤
│ 紙張輸出規格: 標籤[▼] 尺寸[▼] 寬[] 高[] 左位移[] 上位移[] │
├──────────────────────┬─────────────────────────────────────┤
│ 離線列印項目明細 (C) │ 離線等待重印項目 (Offline Queue) (D)│
│ (同 A 結構)          │ [ListBox]                           │
├──────────────────────┴─────────────────────────────────────┤
│ [訊息 ListBox]       │ 列印測試資料 [文字] [列印]           │
├────────────────────────────────────────────────────────────┤
│ 可用標籤: CP01-血品小標籤, CP02-血品小標籤A, ...           │
└────────────────────────────────────────────────────────────┘
Menu: 設定 | 標籤測試頁 | 列印空白NG標籤 | 查詢歷史記錄
```

**區域 A（線上列印項目明細）互動規則：**

| 情境 | 明細顯示 | 指定印表機 | 列印按鈕 |
|------|---------|-----------|---------|
| Auto **未勾** + 點選 Queue Task | 顯示該 Task 明細 | **可變更**（覆寫該 Task 的目標印表機） | **啟用**（按下列印當下選取的那一筆） |
| Auto **已勾**（自動列印中） | 顯示正在列印的那一筆（隨佇列消化自動切換） | **不可變更**（Disabled） | **不可按**（Disabled） |

**手動列印流程（Auto 未勾）：**

```
1. 操作者點選 Online Queue (B) 中的一筆 Task
2. 區域 A 顯示該 Task 明細
3. （選填）操作者在區域 A 變更「指定印表機」
4. 操作者按「列印線上指定項目」按鈕
5. 該筆 Task 送至印表機列印
   ├─ 成功 → 從 Online Queue 移除
   └─ 失敗 → 自動移至 Offline Queue
```

**自動列印流程（Auto 已勾）：**

```
1. 系統自動從 Online Queue 頭部取出 Task
2. 區域 A 顯示該 Task 明細（操作者僅能觀看，不可操作）
3. 送至印表機列印
   ├─ 成功 → 從 Queue 移除 → 自動取下一筆
   └─ 失敗 → 自動移至 Offline Queue → 自動取下一筆
4. Queue 清空後停止，等待新 Task 進入
```

**區域 C（離線列印項目明細）互動規則：**

- **滑鼠指向 Offline Queue (D) 中的 Task** → 區域 C 即時顯示該 Task 的明細
- 可在區域 C 變更該 Task 的「指定印表機」後按「儲存」
- Offline Queue 不直接列印，必須移回 Online Queue 才能列印

**紙張輸出規格區互動規則：**

本區包含：標籤類型、尺寸、寬、高、左位移、上位移、明暗、固定參數 CheckBox。

| 欄位 | 資料來源 | 說明 |
|------|---------|------|
| 標籤類型 | Task 的條碼種類 | 自動帶入，對應 EA 代碼表 LB_TYPE |
| 尺寸/寬/高 | 標籤定義（LB_TYPE 的 WIDTH/LENGTH） | 依標籤類型自動帶入預設尺寸 |
| 左位移 | **印表機設定檔**（查表：該 Task 指定的印表機） | 印表機個別校正參數 |
| 上位移 | **印表機設定檔**（查表：該 Task 指定的印表機） | 印表機個別校正參數 |
| 明暗 | **印表機設定檔**（查表：該 Task 指定的印表機） | 印表機個別校正參數 |

**固定參數 CheckBox 行為：**

| 固定參數 | 效果 |
|---------|------|
| **未勾**（預設） | 本區自動反映目前 Online Queue 選取/正在列印的 Task：標籤類型 → 帶入尺寸；指定印表機 → 查印表機設定檔帶入左位移/上位移/明暗 |
| **已勾** | 本區所有欄位**凍結不自動更新**，操作者可手動調整；列印時使用畫面上的值而非自動帶入值 |

**為什麼需要左位移/上位移/明暗三個參數？**

印表機長年使用後，內部機械構造（送紙滾輪、列印頭位置、感熱元件）會產生**公差**（mechanical tolerance drift）。同一型號的兩台印表機，印出的標籤位置和濃度可能略有偏差。這三個參數用於逐台校正：

| 參數 | 用途 | 範例 |
|------|------|------|
| 左位移 | 補償列印頭水平偏移 | 印表機 A 偏右 → 左位移 +2 |
| 上位移 | 補償送紙垂直偏移 | 印表機 B 偏下 → 上位移 -3 |
| 明暗 | 補償感熱元件老化造成的濃度衰減 | 印表機 C 偏淡 → 明暗 14（加深） |

這三個參數儲存在**印表機設定檔**（以印表機代碼為 key），當 Task 指定印表機時自動查表帶入。列印時傳入 `label_setup()` 的 `darkness` 及 `shift_left` / `shift_top`。

**列印時參數取得流程：**

```
Task 指定印表機代碼
  │
  ├─→ 查印表機設定檔 → 取得 左位移 / 上位移 / 明暗
  ├─→ 查標籤定義     → 取得 寬 / 高 / gap
  │
  ▼
  GodexPrinter.label_setup(
      width=寬, height=高, gap=gap,
      darkness=明暗,       ← 印表機設定檔
      speed=2
  )
  GodexPrinter.open() 時帶入 shift_left / shift_top
  │
  ▼ 列印標籤內容
```

### 標籤測試頁（SampleDataPrint）

由 Menu「標籤測試頁」開啟的子視窗，提供：
- 標籤類型選擇（ComboBox）
- 紙張尺寸設定（ComboBox + 手動寬/高）
- 血袋編號輸入
- 產生 EZPL 檔案 / 列印
- EZPL 指令預覽

---

## 程式目錄結構

```
_LB/
├── main.py              # 主畫面（LBSB01）
├── sample_data_print.py # 標籤測試頁（子視窗）
├── labels.py            # 標籤定義（16 種，對應 EA 代碼表 LB_TYPE）
├── sample_data.py       # 各標籤測試資料
├── ezpl.py              # GoDEX DLL 封裝 + EZPL 指令產生器
├── bar_l00.py           # CP01/CP02 血品小標籤佈局
├── bar_cp11.py          # CP11 血品核對標籤-合格佈局（含子函式）
├── images/              # 標籤圖片（biomedical、Logo）
│   ├── biomedical-25.JPG
│   ├── biomedical-50.JPG
│   └── Logo-18.jpg
└── app.log              # 執行日誌
```
