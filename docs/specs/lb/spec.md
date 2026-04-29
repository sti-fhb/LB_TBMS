# Feature Specification: 標籤列印模組（Label Printing）

**Feature Branch**: `lb-label-printing`
**Created**: 2026-04-10
**Status**: Draft
**Input**: VB6 ALLB01-BarcodeServer 移植 + 新架構設計；依據 `requirements/RQ0.md`、UseCase `UCLB001/UCLB002/UCLB101` 產出
**程式代號**: LBSB01-標籤服務程式

---

## 系統概述

LBSB01 為部署於各工作站的**標籤列印客戶端程式**，負責接收列印指令、管理列印佇列、驅動 GoDEX 條碼印表機輸出血品 / 檢體 / 設備標籤。

### 核心特性

- **本地運作**：不直接存取中央資料庫，所有資料交換透過 SRV（R01）
- **TOKEN 內建**：TOKEN 與中央 API Base URL 硬寫於程式（`login.py` 常數），**無 Login 動作、無健康檢查端點**；CALL API 一律帶 Bearer Token（R02）
- **離線行為**：採 Token-based 呼叫、Timer 3 分鐘補同步、Local-first 寫入 → 詳見 [§離線原則](#離線原則r03)（R03）
- **指令可追溯**：所有進出與異動皆透過 SRV 記錄至中央 DB

---

## 離線原則（R03）

LBSB01 的離線行為集中於此節定義，其他章節出現「離線」時一律依本節規則。本節為**離線行為的唯一權威來源**，UCLB101 內部流程圖與其他章節皆以本節規則為準。

1. **沒有 Login 動作**：Call API 一律帶 Token（無獨立 ping / 健康檢查端點）；**當 APILB 連不上中央 DB 時才會知道當下是離線**。
2. **離線補同步觸發**：離線後啟動 Retry Timer **每 3 分鐘**、或使用者按主畫面 **[更新]** 才觸發同步；同步動作本身就是下一次 Call API，**Call API 成功即視為回復線上**（靜默切換，不另外做連線測試）。
3. **Local-first 寫入**：不管線上或離線，Call APILB 之前一律**先寫 Local DB**；上線後 Sync 策略為「**一律以 Local DB 蓋中央 DB**」。此規則確保離線時仍可修改印表機資料、列印測試標籤。

### 內部流程（UCLB101）

![UCLB101-LBSB01 內部功能流程](./usecase/UCLB101-LBSB01內部功能流程.png)

上圖中以 `<<Rule>>` 明確標示「離線原則」適用範圍（啟動時處理未同步資料、OffLine Retry Timer 啟停、Online/Offline Queue 流向）。

---

## Clarifications

### Session 2026-04-22 (離線原則對齊 UCLB101)

- Q: 線上/離線判定是否要做獨立 `/api/health` ping？ → A: **不做**。線上/離線完全由 Call APILB 結果判定（成功=線上、失敗=離線）。ISLB001 健康檢查機制已撤回，被本節 R03 取代。
- Q: 離線後 Retry Timer 間隔? → A: **每 3 分鐘**（非 60 秒）。同步動作本身即為下一次 Call API，成功即視為回復線上，靜默切回綠燈。
- Q: 離線中本地資料與中央衝突如何處理? → A: **一律以 Local DB 蓋中央 DB**。離線時可修改印表機、列印測試標籤，上線後全部 replay 回中央。

### Session 2026-04-21 (SRV / API 對齊)

- Q: SRV 與 API 前綴用法? → A: **SRV=對內**（Client 前端各模組 / 中央 UI 呼叫），**API=對外**（LBSB01 本地 → 中央，Bearer Token 認證）。
- Q: 印表機 CRUD 如何拆分？ → A: 5 支 API（APILB001 查清單 / 002 查單筆 / 003 POST 新增 / 004 PATCH 修改 / 005 DELETE 硬刪 + cascade）。
- Q: 列印事件流的 INSERT 與 UPDATE 分開？ → A: **分開兩支**。APILB007 進件寫 LOG（INSERT）；APILB006 回報狀態事件（UPDATE，append-only 事件流）。

### Session 2026-04-17 (TOKEN 硬寫)

- Q: LBSB01 是否需要 Login / APIDP001 取 Token？ → A: **不需要**。Token 與中央 API Base URL 硬寫於 `login.py` 常數；LBSB01 是單一角色（列印服務），不需多帳號認證。

### Session 2026-04-22 (SRVDP020 廢除)

- Q: 刪除印表機是否要走「LBSB01 → SRVDP020 → SRVLB092」兩段式？ → A: **簡化為單端點**。SRVDP020 已廢除，LBSB01 PENDING_OPS 只排一筆 DELETE（對應 APILB005），由 APILB005 後端在 Transaction 內 cascade 清 `DP_COMPDEVICE_LABEL`。

---

## User Stories

| Story | UC 編號 | 名稱 | 優先級 | 子檔 |
|-------|---------|------|--------|------|
| 1 | UCLB001 | 標籤列印（Client 端觸發） | P1 | [spec_us1.md](spec_us1.md) |
| 2 | UCLB002 | 歷史查詢及補印 | P1 | [spec_us2.md](spec_us2.md) |
| 3 | UCLB101 | LBSB01 內部運作（離線 / 同步 / Queue） | P1 | [spec_us3.md](spec_us3.md) |
| 4 | —（功能作業）| 印表機設定作業（LBSB01 端） | P1 | [spec_us4.md](spec_us4.md) |
| 5 | —（功能作業）| 標籤測試與測試頁 | P2 | [spec_us5.md](spec_us5.md) |
| 6 | —（管理員作業）| 中央端印表機主檔管理 | P2 | [spec_us6.md](spec_us6.md) |

> US3 / US4 / US5 / US6 是 LB 模組的「支援面」：前兩個 UC（UCLB001/002）透過它們才能正常運作。所有 Story 皆共用 [§離線原則](#離線原則r03)。

---

## Functional Requirements

**LB-A：標籤列印（Client 觸發）** — 對應 US1（UCLB001）

- **FR-001**: 系統 MUST 提供 SRVLB001 通用列印 API，支援格式一（`bar_type` + `site_id` + `data_1~19`）供 Client 模組（BC/CP/BS/TL）呼叫
- **FR-002**: 系統 MUST 依 Client IP + `bar_type` 透過 SRVDP010 解析目標 `PRINTER_ID`、`SERVER_IP` 與印表機公差參數；查無對應時回 404，SRVLB001 回傳錯誤且**不**寫 `LB_PRINT_LOG`
- **FR-003**: 中央 MUST 將 Task 以 HTTP POST 派送至 LBSB01 Listener（`http://{SERVER_IP}:9200/api/lb/task`），並在成功派送後寫 `LB_PRINT_LOG`（`STATUS=0`）
- **FR-004**: LBSB01 MUST 維護 Online Queue 與 Offline Queue 兩層本地佇列；列印失敗的 Task 自動移入 Offline Queue，不阻塞後續 Online Queue 消化
- **FR-005**: LBSB01 MUST 支援 `Auto` 自動依序列印與手動列印兩種模式切換
- **FR-006**: 列印紙張規格 MUST 由三類參數組合：標籤尺寸（`LB_TYPE`）+ 印表機公差（`LB_PRINTER.SHIFT_LEFT/SHIFT_TOP/DARKNESS`）+ 固定參數 CheckBox（勾選時凍結畫面值）

**LB-B：歷史查詢及補印** — 對應 US2（UCLB002）

- **FR-007**: 系統 MUST 提供 SRVLB012 查詢 `LB_PRINT_LOG` 歷史紀錄（條件：日期、站點、印表機、標籤類別、檢體號碼）；無條件呼叫 MUST 回 400
- **FR-008**: 系統 MUST 支援 SRVLB001 格式二（`printer_id` + `log_uuid`）補印；中央依 `log_uuid` 讀回原 `bar_type` + `data_*`，Client 不需重傳資料
- **FR-009**: 補印 MUST 新增一筆 `LB_PRINT_LOG`（非 UPDATE 原紀錄），並以 `RES_ID` 追溯原 UUID

**LB-C：LBSB01 內部運作（離線/同步）** — 對應 US3（UCLB101）

- **FR-010**: LBSB01 MUST NOT 設獨立 `/api/health` 端點；線上/離線判定完全由 Call APILB 結果決定（成功=線上、失敗=離線）
- **FR-011**: 離線後 LBSB01 MUST 以 Retry Timer **每 3 分鐘** 或使用者按 `[更新]` 觸發下一次同步；同步動作本身即下一次 Call API，成功即靜默回復線上
- **FR-012**: LBSB01 MUST 採 Local-first 寫入（呼叫 APILB 前先寫 Local DB）；上線後 Sync 策略為「一律以 Local DB 蓋中央 DB」
- **FR-013**: LBSB01 MUST 將列印/移動/刪除等狀態變更事件透過 APILB006（UPDATE）/ APILB007（INSERT）append-only 回寫中央

**LB-D：印表機設定（LBSB01 端）** — 對應 US4

- **FR-014**: LBSB01 MUST 支援印表機 CRUD，連線方式包含 USB（`PRINTER_DRIVER='USB'`）/ 固定 IP / 藍牙
- **FR-015**: 印表機異動 MUST 先寫 Local SQLite Cache 並排入 `PENDING_OPS`；任何時候均可離線編輯
- **FR-016**: 上線後 `PENDING_OPS` MUST 依序經 APILB003（POST 新增）/ APILB004（PATCH 修改）/ APILB005（DELETE 硬刪）replay 回中央 `LB_PRINTER`

**LB-E：標籤測試** — 對應 US5

- **FR-017**: LBSB01 MUST 提供主畫面「列印測試資料」區與 Menu「標籤測試頁」子視窗，兩入口共用同一列印路徑（LBSB01 Listener `localhost:9200/api/lb/task`）
- **FR-018**: 測試列印 MUST 寫入 `LB_PRINT_LOG`（具完整稽核軌跡），可標記 `status=2` 走離線區避免干擾真實列印佇列

**LB-F：中央端印表機主檔管理** — 對應 US6

- **FR-019**: 中央 TBMS UI MUST 支援 `LB_PRINTER` 全域主檔 CRUD（新增/查詢/修改/刪除）
- **FR-020**: 中央 UI MUST 維護 `DP_COMPDEVICE_LABEL` 對應表（工作站 × 標籤類別 → 印表機），供 SRVDP010 解析印表機使用。**實作 PK 為 `(CDE_ID, LABEL_TYPE)`**；「工作站 IP」於 SRVDP010 內部透過 `DP_COMPDEVICE.IP → CDE_ID` 對照（IP 與 CDE_ID 在 `DP_COMPDEVICE` 為 1:1，但對應表本身以 `CDE_ID` 為 PK 維度，避免設備 IP 異動時連帶異動標籤對照）。**印表機下拉預設僅顯示 Session 登入站點之啟用印表機**（`APILB001` 帶 `site_id` 篩選），跨站點對照預設禁止以避免誤對照；具備 DP01 / DP06 高權限之資訊人員可顯式切換站點查全部
- **FR-021**: 刪除印表機 MUST 在同一 Transaction 中 cascade 清 `DP_COMPDEVICE_LABEL` 子表，避免孤立記錄

**LB-G：跨模組共通**

- **FR-022**: LBSB01 呼叫中央 API MUST 使用硬寫於原始碼的永不過期 Bearer Token（不走 APIDP001 換發流程）；Token 外洩處理見 [spec.md § API 認證](#api-認證)
- **FR-023**: LBSB01 Listener Port `9200` MUST 固定不可設定
- **FR-024**: `LB_PRINT_LOG` MUST 為 append-only（所有狀態事件以 APILB006/007 寫入），禁止硬刪

---

## 參考參數

### 標籤類型（LB_TYPE）

| 欄位 | 說明 |
|------|------|
| 參數代碼 | `LB_TYPE` |
| 參數名稱 | 標籤類別 |
| 用途 | 定義系統所有標籤類型的代碼、名稱、紙張尺寸，供列印時查詢標籤規格 |

| Code | 名稱 | 群組 | WIDTH(mm) | LENGTH(mm) | 狀態 |
|------|------|------|-----------|------------|------|
| TL01 | 檢驗檢體標籤 | TL | 45 | 15 | **啟用** |
| CP01 | 血品小標籤 | CP | 80 | 35 | **啟用** |
| CP11 | 血品核對標籤-合格 | CP | 80 | 75 | **啟用** |
| CP19 | 血品核對標籤-不適輸用 | CP | 80 | 75 | **啟用** |

> 啟用代碼僅 4 種（TL01、CP01、CP11、CP19），DB 中不再保留停用代碼（已於 2026-04-29 以 DELETE 清除舊 BMS_DP_PARAM_FUNC_D 殘留）。日後新增或重啟代碼一律走 DP09 系統參數維護作業。
>
> GAP 值不存於 LB_TYPE，由 LBSB01 程式碼依 LB_TYPE 取對照值（預設 3 dots，CP19/TL01 為 2 dots），不開放使用者調整。

### 字型對照

| 代號 | 字型名稱 | 用途 |
|------|---------|------|
| `sFont0` | 標楷體 | 一般文字 |
| `sFont1` | 細明體 | 血品名稱（旋轉文字） |
| `sFont2` | 微軟正黑體 | — |
| `sFontB` | Arial Black | 粗體文字 |
| `sFontS` | Arial Rounded MT Bold | 血型（Rh+ 實心） |
| `sFontEpt` | Swis721 BdOul BT | 血型（Rh- 空心字） |

---

## 系統關聯

### 中央 SRV / API 契約

| 對內 SRV | 用途 | 主要呼叫方 |
|---------|------|-----------|
| [SRVLB001](./contracts/SRVLB001.md) | 標籤列印通用 API（兩種輸入模式：一般列印 + 補印） | Client 前端（BC/CP/BS/TL）/ LBSB01 測試頁 |
| [SRVLB012](./contracts/SRVLB012.md) | 標籤列印紀錄查詢 | 「LBSR01-歷史標籤查詢及補印作業」畫面 |
| [SRVDP010](./contracts/SRVDP010.md) | 資訊設備標籤印表機查詢（Client IP + bar_type → PRINTER_ID）| 中央 SRVLB001 格式一內部呼叫 |

| 對外 API | HTTP 動作 | 用途 | 呼叫方 |
|---------|-----------|------|-------|
| [APILB001](./contracts/APILB001.md) | GET `/api/lb/printers` | 查詢印表機清單 | LBSB01 啟動 / 同步 |
| [APILB002](./contracts/APILB002.md) | GET `/api/lb/printers/{id}` | 查詢單筆印表機 | LBSB01 設定頁 |
| [APILB003](./contracts/APILB003.md) | POST `/api/lb/printers` | 新增印表機 | LBSB01 PENDING_OPS replay |
| [APILB004](./contracts/APILB004.md) | PATCH `/api/lb/printers/{id}` | 修改印表機 | LBSB01 PENDING_OPS replay |
| [APILB005](./contracts/APILB005.md) | DELETE `/api/lb/printers/{id}` | 刪除印表機（硬刪 + cascade）| LBSB01 PENDING_OPS replay |
| [APILB006](./contracts/APILB006.md) | POST `/api/lb/print-events` | 回報列印事件（append-only）| LBSB01 列印完成 / 移動 / 刪除 |
| [APILB007](./contracts/APILB007.md) | POST `/api/lb/print-logs` | 進件寫 LOG（INSERT） | 中央 SRVLB001 / LBSB01 測試頁 |

LB 專案端的 SRV/API 契約採「Client 使用視角」，主專案（TBMS）端為「Server 實作視角」——兩邊路徑相同、內容不同。

### Port 規則

| Port | 用途 | 可設定 |
|------|------|--------|
| 9100 | GoDEX 印表機 TCP 列印 | 印表機端固定 |
| **9200** | LBSB01 HTTP Listener（接收 Task） | **固定，不可設定** |

---

## 程式目錄結構

```
_LB/Source/Python/LBSB01/
├── main.py              # 主畫面（LBSB01）
├── printer_setting.py   # 印表機設定（子視窗）
├── sample_data_print.py # 標籤測試頁（子視窗）
├── labels.py            # 標籤定義（16 種，對應參考參數 LB_TYPE）
├── sample_data.py       # 各標籤測試資料
├── ezpl.py              # GoDEX DLL 封裝 + EZPL 指令產生器
├── bar_l00.py           # CP01 血品小標籤佈局（檔名 l00 沿用，原同時含 CP02；CP02 已於 PR #397 停用）
├── bar_cp11.py          # CP11 血品核對標籤-合格佈局（含子函式）
├── Fonts/               # 標籤列印用字型
├── images/              # 標籤圖片（biomedical、Logo）
│   ├── biomedical-25.JPG
│   ├── biomedical-50.JPG
│   └── Logo-18.jpg
└── app.log              # 執行日誌（runtime 產生）
```

---

## 資料模型

詳見 [data-model.md](./data-model.md)（`LB_PRINT_LOG` / `LB_PRINTER` 欄位、ERD、關聯說明）。
