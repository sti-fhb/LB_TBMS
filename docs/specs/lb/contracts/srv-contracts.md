# 服務契約：標籤模組（LB）

**建立日期**: 2026-04-15
**涵蓋**: 對內 SRV（SRVLB001、SRVLB012）+ 對外 API（APILB001~006）

> 2026-04-21 調整（SRV/API 命名對齊，對應主專案 #332）：
> - **SRV 對內、API 對外**。Client 前端 → 中央為 SRV；LBSB01 → 中央為 API。
> - 印表機 CRUD 拆為 5 支 APILB：APILB001（查清單）/ APILB002（查單筆）/ APILB003（新增 POST）/ APILB004（修改 PATCH）/ APILB005（刪除 DELETE 軟刪）。
> - 原 `SRVLB093` → `APILB001`；原 `SRVLB091`（upsert）拆為 `APILB003`（POST 新增）+ `APILB004`（PATCH 修改）；原 `SRVLB092` → `APILB005`；原 `SRVLB011-標籤列印LOG更新` → `APILB006-回報列印事件`（append-only 事件流）。
> - SRVLB001 格式二輸入改為 `PRINTER_ID + LOG_UUID`（中央依 UUID 讀 LB_PRINT_LOG 取原 BAR_TYPE + data_*，不重傳標籤資料）。
> - SRVDP010 回傳擴充為印表機完整連線資訊（PRINTER_ID + SERVER_IP + port + 校正參數）。

> **對內 SRV**：Client 前端各模組 / 中央 UI 呼叫，存於此檔。
> **對外 API（APILB001~006）**：LBSB01 本地 → 中央 TBMS，Bearer Token 認證。本檔目前先收錄 APILB006 供對照，完整 APILB 契約另於 `api-contracts.md`（規劃中）。

---

## SRVLB001 — 標籤列印通用API

**呼叫方**: Client 端各模組（BC/CP/BS/TL）、LBSB01 標籤測試頁、歷史查詢「補印」功能（UCLB002）
**部署位置**: 中央 DP Server
**存取 Table**: LB_PRINT_LOG（新增 + 更新；格式二另需讀取）、LB_PRINTER（格式二直接讀取）
**依賴 SRV**: SRVDP010（資訊設備標籤印表機查詢；僅格式一使用）

### 兩種輸入模式

| 模式 | 必填參數組合 | 使用情境 |
|------|------------|----------|
| **格式一**（一般列印）| `bar_type` + `site_id` +（Client IP 由 HTTP 自動取得）+ `data_*` | Client 模組列印；中央透過 SRVDP010 自動解析 PRINTER_ID / SERVER_IP / 參數 |
| **格式二**（補印）| `printer_id` + `log_uuid` | UCLB002 補印；依 `log_uuid` 讀 LB_PRINT_LOG 取回原 BAR_TYPE + data_*（不重傳）；PRINTER_ID 可與原紀錄不同 |

格式由傳入參數判定：有 `log_uuid` 即走格式二；否則走格式一。

### Request

| 參數 | 型態 | 必填 | 說明 |
|------|------|------|------|
| bar_type | string | 格式一 Y / 格式二 N | 條碼處理種類（格式二由原 LOG 帶出，不需傳）|
| site_id | string | 格式一 Y / 格式二 N | 資料站點（格式二由原 LOG 帶出）|
| printer_id | string | 格式二必填 | 指定印表機編號；格式一由中央解析 |
| log_uuid | string | 格式二必填 | 原 LB_PRINT_LOG 的 UUID；中央據此取回原 data_* |
| specimen_no | string | N | 檢體號碼（格式一）|
| data_1 ~ data_19 | string | 格式一 N / 格式二不傳 | 標籤資料（格式二由原 LOG 帶出） |
| status | int | N | 初始狀態：0=Online Queue（預設）、2=Offline Queue（測試頁用） |

> 格式一：`printer_id` 不由 Client 傳入，中央透過 SRVDP010 依 Client IP + bar_type 解析（同時取回 SERVER_IP / 參數）。
> 格式二：Client 指定 `printer_id` + `log_uuid`（UCLB002 補印），SRVDP010 不介入；中央讀 LB_PRINT_LOG(log_uuid) 取回 BAR_TYPE + data_*，讀 LB_PRINTER(printer_id) 取 SERVER_IP + 參數。

### Response

| 回傳 | 型態 | 說明 |
|------|------|------|
| success | boolean | 是否成功 |
| uuid | string | 新增記錄的 UUID（成功時回傳） |
| printer_id | string | 解析出的印表機編號（成功時回傳） |
| message | string | 訊息（失敗時為錯誤說明） |

### 處理流程（中央派送 + LBSB01 接收）

```
Client（BC/CP/BS/TL 一般列印 / UCLB002 補印）
  │
  │ Call SRVLB001（格式一：bar_type+site_id+data_*；格式二：printer_id+log_uuid）
  ▼
中央 Server（DP）— SRVLB001 處理：
  │
  ├─ 1. 依傳入格式一/二 取得 PRINTER_ID、SERVER_IP、印表機參數
  │     ├─ 格式一：Call SRVDP010(client_ip, bar_type)
  │     │         → 回 {PRINTER_ID, SERVER_IP, printer_params}
  │     │         BAR_TYPE + data_* 由呼叫端傳入
  │     │
  │     └─ 格式二：讀 LB_PRINT_LOG(WHERE UUID=log_uuid)
  │               → 取回 {原 BAR_TYPE, data_1~19}
  │               讀 LB_PRINTER(WHERE PRINTER_ID=:printer_id)
  │               → 取回 {SERVER_IP, printer_params}
  │
  ├─ 2. 驗證 PRINTER_ID 是否有值
  │     ├─ 空白 → 回傳 MSG「資訊設備需先設定」→ 結束（不寫 LB_PRINT_LOG）
  │     └─ 有值 → 繼續
  │
  ├─ 3. INSERT INTO LB_PRINT_LOG（新 UUID、BAR_TYPE、PRINTER_ID、STATUS=0 RECEIVED、…）
  │     ※ 補印亦新增一筆（非更新原紀錄）；以 RES_ID / 備註可追溯原 log_uuid
  │
  ├─ 4. HTTP POST 轉發 Task 到 Printer Server
  │     → http://{SERVER_IP}:9200/api/lb/task
  │     Header: Authorization: Bearer <token>
  │     Body: { uuid（新）, printer_id, bar_type, site_id, data_1~19, status }
  │
  └─ 5. 判斷 POST Error？
        ├─ Error → 5a. UPDATE 同一筆 LB_PRINT_LOG（依新 UUID）：
        │              STATUS=1, RESULT=POST_ERROR:{Error Code}
        │          → 5b. 回傳 MSG「標籤列印送出失敗：可能為網路問題或標籤服務沒連 IP:{SERVER_IP}」
        │          → 結束
        └─ 成功 → 回傳新 UUID + 成功訊息
```

### SRVDP010 印表機解析邏輯（格式一）

```
SRVDP010（client_ip, bar_type）
  │
  ├─ Step 1：查 DP_COMPDEVICE_LABEL
  │          WHERE CLIENT_IP = :client_ip AND BAR_TYPE = :bar_type
  │          → 取得 PRINTER_ID
  │
  ├─ Step 2：查 LB_PRINTER
  │          WHERE PRINTER_ID = :printer_id
  │          → 取得 SERVER_IP、SERVER_PORT、printer_params
  │
  ├─ 找到 → 回傳 {printer_id, server_ip, server_port, printer_params}
  └─ 找不到 → 回 404（SRVLB001 回報 "資訊設備需先設定"）
```

> DP_COMPDEVICE_LABEL 由管理者在「資訊設備」功能中設定，
> 建立「哪台工作站 + 哪種標籤 → 由哪台印表機列印」的對應關係。

### LBSB01 端接收（Task Listener :9200）

```
LBSB01 HTTP Listener（port 9200，固定）
  │
  ├─ POST /api/lb/task
  ├─ 驗證 Bearer Token
  ├─ 寫入 local.db：
  │   ├─ LB_PRINT_LOG_CACHE（完整 Task 資料）
  │   └─ Status=0 → ONLINE_QUEUE
  │      Status=2 → OFFLINE_QUEUE
  └─ 通知 GUI 刷新（<<TaskReceived>> event）
```

### 多台 Printer Server 路由

```
中央 SRVLB001 依 LB_PRINTER.SERVER_IP 路由：

  PRN-001（SERVER_IP=192.168.1.10）→ POST http://192.168.1.10:9200/api/lb/task
  PRN-002（SERVER_IP=192.168.1.10）→ POST http://192.168.1.10:9200/api/lb/task（同一台）
  PRN-101（SERVER_IP=192.168.2.10）→ POST http://192.168.2.10:9200/api/lb/task
```

### Port 規則

| Port | 用途 | 可設定 |
|------|------|--------|
| 9100 | GoDEX 印表機 TCP 列印 | 印表機端固定 |
| **9200** | LBSB01 HTTP Listener（接收 Task） | **固定，不可設定** |

---

## APILB007 — 新增列印事件

> **2026-04-22 新增**：單獨抽出「進件寫 LOG」為獨立端點，與 APILB006「狀態變更事件」配對。SRVLB001 於 [Step 3] 進件寫 Log 時呼叫本服務。

**呼叫方**:
- 中央 SRVLB001（標籤列印通用 API）處理 Client 列印請求時進件（格式一、格式二皆於 [Step 3] 呼叫）
- LBSB01 本地測試頁 / 離線列印等需直接新增 LOG 的情境（若有）

**部署位置**: 中央 DP Server
**存取 Table**: LB_PRINT_LOG（新增）
**HTTP 路由**: `POST /api/lb/print-logs`（進件寫新 UUID）

### Request

| 參數 | 型態 | 必填 | 說明 |
|------|------|------|------|
| uuid | string | Y | 新 LOG 的 UUID（由呼叫端產生，供冪等與追溯）|
| bar_type | string | Y | 標籤類別代碼（LB_TYPE） |
| printer_id | string | Y | 印表機編號；**保留字 `"USB"` 代表本機 USB 直連**，跳過 LB_PRINTER 驗證 |
| site_id | string | Y | 站點代碼 |
| data_1 ~ data_19 | string | N | 標籤列印資料 |
| status | int | Y | 初始狀態：0=RECEIVED（Online Queue）、2=Offline Queue（測試頁用）|
| ref_log_uuid | string | N | 格式二補印時帶入原 LOG UUID（寫入 RES_ID），供稽核追溯 |
| specimen_no | string | N | 檢體號碼（若有）|

### Response

| 欄位 | 型態 | 說明 |
|------|------|------|
| success | boolean | 是否成功 |
| uuid | string | 寫入的 UUID（回傳供呼叫端確認）|
| message | string | 錯誤訊息 |

### 處理

1. 驗證 `printer_id`：保留字 `"USB"` 跳過驗證；其他值需存在於 LB_PRINTER 且未刪除
2. INSERT INTO LB_PRINT_LOG（UUID、BAR_TYPE、PRINTER_ID、SITE_ID、Data1~19、STATUS、RES_ID=`ref_log_uuid`、CREATED_USER/DATE/SITE 標準欄位…）
3. 回傳 success + 該筆 UUID

### 錯誤情境

| 情境 | HTTP | 說明 |
|------|------|------|
| UUID 重複 | 409 | 冪等處理：回原 UUID 或 ignore 再寫 |
| bar_type 不支援 | 400 | 標籤類別代碼錯誤 |
| printer_id 未登錄且非保留字 "USB" | 404 | LB_PRINTER 查不到且不是 USB 直連 |

### 與 APILB006 的差異

| 項目 | APILB007（本服務） | APILB006 |
|------|--------------------|---------|
| 動作 | INSERT 新 LOG | UPDATE 既有 LOG |
| 時機 | 列印進件首次寫入 | 狀態變更（完成 / 移動 / 刪除）|
| 關鍵欄位 | UUID + 業務欄位 + Data_* | UUID（定位）+ STATUS + RESULT |
| 資料模型語意 | 事件起點 | append-only 事件流 |

---

## APILB006 — 回報列印事件（原 SRVLB011）

> **2026-04-21 重新命名**：原 `SRVLB011-標籤列印LOG更新` → `APILB006-回報列印事件`（對外 API，LBSB01 → 中央 TBMS）。語意從「更新 LOG」調整為「append-only 事件流」：LBSB01 對此資料只寫、不讀、不改舊紀錄，以單一 endpoint 配合 action 欄位分流各類事件。

**呼叫方**:
- LBSB01 列印完成後（事件：PRINTED，Status → 1，RESULT 寫入列印參數）
- 使用者於 Online / Offline Queue 上操作（事件：MOVED_OFFLINE / MODIFIED / DELETED）
- 其他需記錄列印事件的流程

**部署位置**: 中央 DP Server
**存取 Table**: LB_PRINT_LOG（依 UUID 更新 STATUS + RESULT；語意為 append-only 事件流）
**HTTP 路由**: `POST /api/lb/print-events`（由 LBSB01 `central_api.replay_op` replay 進來）

### Request

| 參數 | 型態 | 必填 | 說明 |
|------|------|------|------|
| uuid | string | Y | LB_PRINT_LOG 的 UUID（主鍵） |
| status | int | N | 新狀態（0=Online 待列印、1=終態、2=離線區；空=不更新） |
| result_memo | string | N | RESULT 備註段（見下方 RESULT 格式；空=保持原 RESULT） |

### Response

| 欄位 | 型態 | 說明 |
|------|------|------|
| success | boolean | 是否成功 |
| affected_rows | int | 更新筆數（預期為 1） |
| message | string | 訊息（失敗時為錯誤說明） |

### Status 狀態機

| Status | 語意 |
|--------|------|
| 0 | 待列印（Online Queue 中） |
| 1 | 終態（印出成功 or 人工刪除） |
| 2 | 離線區（Offline Queue） |

### RESULT 寫入格式

LB_PRINT_LOG.RESULT 欄位寫入格式：

```
[程式版本號]+'-'+[如果勾固定參數本欄為'F']+'W'+[寬]+'H'+[長]+'L'+[左位移]+'T'+[上位移]+'D'+[明暗值]+[備註]
```

程式版本號取自 LBSB01 `version.py` 的 `VERSION` 常數。組 RESULT 一律透過 LBSB01 端 `local_db.build_result()` 函式，中央 APILB006 直接寫入前端組好的字串。

| 備註代碼 | 意義 | Status 變更 |
|---------|------|-----------|
| `OnLine` | 工作被移至 Online 區 | 保持 |
| `OffLine` | 工作被移至離線區 | → 2 |
| `Delete` | 工作被人工刪除（Online 區） | → 1 |
| `Off_DEL` | 工作在 Offline 區被刪除 | → 1 |

**範例**：
- 已印出（Status→1）：`v1.1r1-W80H35L40T0D8`
- 勾選固定參數：`v1.1r1-FW80H35L40T0D8`（`F` 僅於勾選「固定參數」時加入）
- 移至離線（Status→2）：`v1.1r1-OffLine`

### 處理流程

```
LBSB01（列印完成 / 移動 / 刪除）
  │
  ├─ local_db.update_print_log(uuid, status, result)  ← 本地 Cache 即時更新
  ├─ 排入 PENDING_OPS（op_type=UPDATE, target=LB_PRINT_LOG）
  ▼
central_api.replay_op → POST /api/lb/print-events（帶 Bearer Token）
  │
  ▼
中央 Server（DP）— APILB006 處理：
  1. 以 UUID 鎖定該筆 LB_PRINT_LOG
  2. 依傳入 status / result_memo 更新欄位
  3. 更新 UPDATED_USER / UPDATED_DATE / UPDATED_SITE 標準欄位
  4. 回傳 success + affected_rows
```

---

## SRVLB012 — 標籤列印紀錄查詢

**呼叫方**: 「LBSR01-歷史標籤查詢及補印作業」畫面（UCLB002）
**部署位置**: 中央 DP Server
**存取 Table**: LB_PRINT_LOG（讀取）、LB_PRINTER（Join 取得印表機名稱）、DP_SITE（Join 取得站點名稱）

### Request（至少一項查詢條件）

| 參數 | 型態 | 必填 | 說明 |
|------|------|------|------|
| date_from | date | N | 列印時間起（CREATED_DATE >= date_from） |
| date_to | date | N | 列印時間迄（CREATED_DATE <= date_to） |
| site_id | string | N | 資料站點 |
| printer_id | string | N | 印表機編號 |
| bar_type | string | N | 標籤類別（CP01 / CP11 / TL01 …） |
| status | int | N | 0=待列印 / 1=終態 / 2=離線區（空=全部） |
| specimen_no | string | N | 檢體號碼 |
| page | int | N | 分頁頁碼（預設 1） |
| limit | int | N | 每頁筆數（預設 20，最大 100） |

### Response

| 欄位 | 型態 | 說明 |
|------|------|------|
| data | object[] | 紀錄清單 |
| meta | object | `{ total, page, limit, total_pages }` |

`data[]` 欄位：`uuid`、`bar_type`、`site_id`、`site_name`、`printer_id`、`printer_name`、`specimen_no`、`data_1`~`data_19`、`status`、`result`、`created_date`、`created_user`

### 處理流程

```
1. 驗證至少一項查詢條件（否則 400）
2. 組 SELECT，JOIN LB_PRINTER (PRINTER_NAME)、JOIN DP_SITE (SITE_NAME)
3. 依 CREATED_DATE DESC 排序
4. 分頁回傳
```

### 補印連動

使用者在結果清單選取要補印的紀錄，前端以該筆的 `printer_id` + `log_uuid`（即該筆 LB_PRINT_LOG 的 UUID）**以格式二呼叫 SRVLB001**。中央依 `log_uuid` 讀 LB_PRINT_LOG 取回原 `bar_type` + `data_*`（不重傳），跳過 SRVDP010 解析，直接派送 Task 至指定印表機。補印時可指定不同於原紀錄的印表機。

---

## 自家模組直接操作（不需 SRV）

以下操作由 LBSB01 透過 `local_db.py` 直接讀寫，不經過 SRV：

### LB_PRINT_LOG — 列印 LOG

| 操作 | 方法 | 說明 |
|------|------|------|
| 新增 | `local_db.insert_print_log(data)` | Task Listener 收到 Task 時寫入 |
| 更新 Status + RESULT | `local_db.update_print_log(uuid, status, result)` | 列印完成/移動/刪除時更新 |

#### Status 狀態機

| Status | 語意 |
|--------|------|
| 0 | 待列印（Online Queue 中） |
| 1 | 終態（印出成功 or 人工刪除） |
| 2 | 離線區（Offline Queue） |

#### RESULT 寫入格式

```
[程式版本號]+'-'+[如果勾固定參數本欄為'F']+'W'+[寬]+'H'+[長]+'L'+[左位移]+'T'+[上位移]+'D'+[明暗值]+[備註]
```

程式版本號取自 `version.py` 的 `VERSION` 常數（目前 `v1.1r1`）。組 RESULT 一律透過 `local_db.build_result()` 函式。

| 備註代碼 | 意義 | Status 變更 |
|---------|------|-----------|
| `OnLine` | 工作被移至 Online 區 | 保持 |
| `OffLine` | 工作被移至離線區 | → 2 |
| `Delete` | 工作被人工刪除（Online 區） | → 1 |
| `Off_DEL` | 工作在 Offline 區被刪除 | → 1 |

**範例**:
- 已印出：`v1.1r1-W80H35L40T0D8`
- 勾選固定參數：`v1.1r1-FW80H35L40T0D8`（`F` 僅於勾選「固定參數」時加入）
- 移至離線：`v1.1r1-OffLine`

### LB_PRINTER — 印表機設定

| 操作 | 方法 | 說明 |
|------|------|------|
| 查詢 | `local_db.list_printers(site_id)` | 讀 Local Cache |
| 新增 | `local_db.add_printer(data, online)` | 寫 Cache + 離線排 PENDING_OPS |
| 更新 | `local_db.save_printer(data, online)` | 寫 Cache + 離線排 PENDING_OPS |
| 刪除 | `local_db.remove_printer(site, pid, online)` | 刪 Cache + 排 1 筆 PENDING_OPS（DELETE LB_PRINTER 經 APILB005，後端 cascade 清子表）|

> 離線時所有寫入操作排入 PENDING_OPS，上線後依 SEQ 順序 replay 回中央 DB。

---

## 跨模組 SRV（LB 相關的 DP 服務）

> **認證方式變更**：
> - 2026-04-17：LB 不再呼叫 APIDP001 取得 TOKEN。TOKEN 與中央 API Base URL 皆**硬寫於 LBSB01 程式常數**（`login.py`）。
> - 2026-04-22：**移除獨立健康檢查端點**。線上/離線改由**實際 Call APILB 結果**判定（對齊 EA UCLB101「離線原則」Rule，GUID `{2B94E1A9-8051-4083-BA45-80732128CA0C}`）。

### 離線偵測規則（EA UCLB101 離線原則）

1. 沒有 Login 動作，Call API 一律帶 Bearer Token → **當 Call APILB 失敗才知道當下是離線**
2. 離線時啟動 Timer **每 3 分鐘**，或使用者按主畫面 **[更新]** 才觸發同步
3. 不管線上或離線，Call APILB 前**先寫 Local DB**；連線時再 Sync，**一律以 Local DB 蓋中央 DB**

### SRVDP010 — 資訊設備標籤印表機查詢

**提供方**: DP 模組
**呼叫場景**: SRVLB001 格式一內部呼叫；依 Client IP + bar_type 取得印表機完整連線資訊
**呼叫方**: 中央 SRVLB001（非 LBSB01 直接呼叫）

| 參數 | 型態 | 必填 | 說明 |
|------|------|------|------|
| client_ip | string | Y | 呼叫端工作站 IP |
| bar_type | string | Y | 標籤代碼（如 CP11、TL01） |

| 回傳 | 型態 | 說明 |
|------|------|------|
| printer_id | string | 印表機編號（LB_PRINTER.PRINTER_ID） |
| printer_name | string | 印表機名稱 |
| server_ip | string | 印表機主機 IP（LBSB01 本機 IP，SRVLB001 據此 HTTP POST）|
| server_port | int | 印表機主機 port（預設 9200） |
| printer_params | object | 印表機校正參數（左/上位移、明暗、DPI、材質…） |

**處理**:
1. 查 DP_COMPDEVICE_LABEL WHERE CLIENT_IP = :client_ip AND BAR_TYPE = :bar_type → 取得 PRINTER_ID
2. 若 PRINTER_ID = `"USB"`（保留字，本機 USB 直連）→ 跳過 LB_PRINTER 查詢，`server_ip` / `printer_params` 回傳空白
3. 否則：查 LB_PRINTER WHERE PRINTER_ID = :printer_id → 取得 SERVER_IP / SERVER_PORT / printer_params

**保留字**:
- `PRINTER_ID = "USB"`：代表 Client 端連接的本機 USB 印表機（無 SERVER_IP）。LB_PRINTER 查不到為**正常**，參數帶空白回傳，呼叫端據此走 USB 直連輸出路徑（不經 LBSB01 HTTP Listener）。

**錯誤**: 查無 DP_COMPDEVICE_LABEL 對應 → 404；LB_PRINTER 查無且 PRINTER_ID 非保留字 `"USB"` → 500（資料不一致）。

> 對應關係由管理者在「資訊設備」功能中設定。若未設定，SRVLB001 回 MSG「資訊設備需先設定」。

### ~~SRVDP020 — 刪除元件設備標籤對應~~（已廢除，2026-04-22）

> SRVDP020 已於 2026-04-22 從 EA 刪除。原「LBSB01 → SRVDP020 → SRVLB092」兩段式刪除流程簡化為「LBSB01 → APILB005」單一端點，由 APILB005 後端在 Transaction 內 cascade 清 `DP_COMPDEVICE_LABEL` 子表對應後硬刪 `LB_PRINTER`。LBSB01 PENDING_OPS 只需排一筆 `DELETE LB_PRINTER`（對應 APILB005），不再有跨模組 CALL_SRV 操作。詳見 APILB005 契約。
