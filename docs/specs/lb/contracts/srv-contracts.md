# 內部服務契約：標籤模組（LB）

**建立日期**: 2026-04-15
**來源**: EA Model Services/LB-標籤（SRVLB001, 011, 091–094）

> 內部服務（SRV）供模組間呼叫，其他模組不直接存取 LB Table。
> LBSB01 端程式一律透過 SRV 存取中央 DB（不可直接連線）。

---

## SRVLB001 — 標籤列印通用API

**呼叫方**: Client 端各模組（BC/CP/BS/TL）、LBSB01 標籤測試頁
**部署位置**: 中央 DP Server
**存取 Table**: LB_PRINT_LOG（新增）、LB_PRINTER（查詢 SERVER_IP）

### Request

| 參數 | 型態 | 必填 | 說明 |
|------|------|------|------|
| bar_type | string | Y | 條碼處理種類（標籤代碼，如 CP11、TL01） |
| site_id | string | Y | 資料站點 |
| printer_id | string | Y | 指定印表機編號 |
| specimen_no | string | N | 檢體號碼 |
| data_1 ~ data_19 | string | N | 條碼處理資料（依標籤類型填入對應欄位） |
| status | int | N | 初始狀態：0=Online Queue（預設）、2=Offline Queue（測試頁用） |

### Response

| 回傳 | 型態 | 說明 |
|------|------|------|
| success | boolean | 是否成功 |
| uuid | string | 新增記錄的 UUID |
| message | string | 訊息 |

### 處理流程（中央派送 + LBSB01 接收）

```
Client（BC/CP/BS/TL）
  │
  │ Call SRVLB001（printer_id=PRN-002, bar_type=CP11, data...）
  ▼
中央 Server（DP）— SRVLB001 處理：
  │
  ├─ 1. 產生 UUID
  ├─ 2. INSERT INTO LB_PRINT_LOG（全欄位 + Status）
  ├─ 3. 查詢 LB_PRINTER WHERE PRINTER_ID=:printer_id
  │     → 取得 SERVER_IP（該印表機所屬的 Printer Server IP）
  │
  ├─ 4. HTTP POST 轉發 Task 到 Printer Server
  │     → http://{SERVER_IP}:9200/api/lb/task
  │     Header: Authorization: Bearer <token>
  │     Body: { uuid, printer_id, bar_type, site_id, data_1~19, status }
  │
  ├─ 5a. Printer Server 回應 success → 回傳 Client 成功
  └─ 5b. Printer Server 不可達 → 回傳 Client 錯誤（或排入重試）
```

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

## 自家模組直接操作（不需 SRV）

以下操作由 LBSB01 透過 `local_db.py` 直接讀寫，不經過 SRV：

### LB_PRINT_LOG — 列印 LOG

| 操作 | 方法 | 說明 |
|------|------|------|
| 新增 | `local_db.insert_print_log(data)` | Task Listener 收到 Task 時寫入 |
| 更新 Status + RES_ID | `local_db.update_print_log(uuid, status, res_id)` | 列印完成/移動/刪除時更新 |

#### Status 狀態機

| Status | 語意 |
|--------|------|
| 0 | 待列印（Online Queue 中） |
| 1 | 終態（印出成功 or 人工刪除） |
| 2 | 離線區（Offline Queue） |

#### RES_ID 寫入格式

格式：`[VERSION] + ['F'?固定參數] + 'W'[寬] + 'H'[長] + 'L'[左位移] + 'T'[上位移] + 'D'[明暗值] + [備註]`

VERSION 取自 `version.py` 的 `VERSION` 常數（目前 `v1.1r1`）。組 RES_ID 一律透過 `local_db.build_res_id()` 函式。

| 備註代碼 | 意義 | Status 變更 |
|---------|------|-----------|
| `-OnLine` | 移至 Online 區 | 保持 |
| `-OffLine` | 移至離線區 | → 2 |
| `-Delete` | Online 人工刪除 | → 1 |
| `-Off_DEL` | Offline 刪除 | → 1 |

**範例**:
- 已印出：`v1.1r1W80H35L40T0D8`
- 移至離線：`v1.1r1-OffLine`

### LB_PRINTER — 印表機設定

| 操作 | 方法 | 說明 |
|------|------|------|
| 查詢 | `local_db.list_printers(site_id)` | 讀 Local Cache |
| 新增 | `local_db.add_printer(data, online)` | 寫 Cache + 離線排 PENDING_OPS |
| 更新 | `local_db.save_printer(data, online)` | 寫 Cache + 離線排 PENDING_OPS |
| 刪除 | `local_db.remove_printer(site, pid, online)` | 刪 Cache + 排 SRVDP018 + DELETE |

> 離線時所有寫入操作排入 PENDING_OPS，上線後依 SEQ 順序 replay 回中央 DB。

---

## 跨模組 SRV（LB 會呼叫的 DP 服務）

### APIDP001 — 外部系統資料接收介面（認證）

**提供方**: DP 模組
**呼叫場景**: LBSB01 啟動時取得 TOKEN

| 參數 | 型態 | 必填 | 說明 |
|------|------|------|------|
| code | string | Y | 外部系統識別碼：`LB_PRINT` |
| passcode | string | Y | 通關密碼：`stark123` |

| 回傳 | 型態 | 說明 |
|------|------|------|
| token | string | 存取 TOKEN |
| expires_in | int | 有效秒數（預設 3600） |
| token_type | string | `Bearer` |

**端點**: `POST /api/ext/auth/token`
**EA 認證參數**: `{1BEF51C7-CD73-44e6-8D3B-CD134B3D388D}`（Code=LB_PRINT, Passcode=stark123）

### SRVDP018 — 刪除元件設備標籤對應

**提供方**: DP 模組
**呼叫場景**: 刪除印表機時先清子表

| 參數 | 型態 | 必填 | 說明 |
|------|------|------|------|
| site_id | string | Y | 站點代碼 |
| printer_id | string | Y | 印表機編號 |

| 回傳 | 型態 | 說明 |
|------|------|------|
| success | boolean | 是否成功 |
| deleted_count | int | 刪除筆數 |
| message | string | 訊息 |

**處理**: DELETE FROM DP_COMPDEVICE_LABEL WHERE SITE_ID = :site_id AND PRINTER_ID = :printer_id
**EA Element ID**: -69055610
