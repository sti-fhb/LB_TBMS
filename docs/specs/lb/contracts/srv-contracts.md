# 內部服務契約：標籤模組（LB）

**建立日期**: 2026-04-15
**涵蓋服務**: SRVLB001, 011, 091–094

> 內部服務（SRV）供模組間呼叫，其他模組不直接存取 LB Table。
> LBSB01 端程式一律透過 SRV 存取中央 DB（不可直接連線）。

---

## SRVLB001 — 標籤列印通用API

**呼叫方**: Client 端各模組（BC/CP/BS/TL）、LBSB01 標籤測試頁
**部署位置**: 中央 DP Server
**存取 Table**: LB_PRINT_LOG（新增）、LB_PRINTER（查詢 SERVER_IP）
**依賴 SRV**: SRVDP010（標籤印表機查詢服務）→ 解析 Client IP + bar_type → PRINTER_ID

### Request

| 參數 | 型態 | 必填 | 說明 |
|------|------|------|------|
| bar_type | string | Y | 條碼處理種類（標籤代碼，如 CP11、TL01） |
| site_id | string | Y | 資料站點 |
| specimen_no | string | N | 檢體號碼 |
| data_1 ~ data_19 | string | N | 條碼處理資料（依標籤類型填入對應欄位） |
| status | int | N | 初始狀態：0=Online Queue（預設）、2=Offline Queue（測試頁用） |

> **printer_id 不由 Client 傳入**，由中央 SRVLB001 透過 SRVDP010 自動解析（Client IP + bar_type → PRINTER_ID）。

### Response

| 回傳 | 型態 | 說明 |
|------|------|------|
| success | boolean | 是否成功 |
| uuid | string | 新增記錄的 UUID（成功時回傳） |
| printer_id | string | 解析出的印表機編號（成功時回傳） |
| message | string | 訊息（失敗時為錯誤說明） |

### 處理流程（中央派送 + LBSB01 接收）

```
Client（BC/CP/BS/TL）
  │
  │ Call SRVLB001（bar_type=CP11, site_id=S01, data...）
  │  ※ 不傳 printer_id
  ▼
中央 Server（DP）— SRVLB001 處理：
  │
  ├─ 1. 取得 Client IP（從 HTTP Request）
  │
  ├─ 2. Call SRVDP010（client_ip, bar_type）
  │     → 查詢 DP_COMPDEVICE_LABEL 對應表
  │     → 找出該工作站 + 該標籤類型 → PRINTER_ID
  │
  ├─ 2a. 找不到對應 → 回傳 Client 失敗
  │      { success: false, message: "資訊設備標籤要先設定" }
  │
  ├─ 3. 產生 UUID
  ├─ 4. INSERT INTO LB_PRINT_LOG（全欄位 + Status + PRINTER_ID）
  ├─ 5. 查詢 LB_PRINTER WHERE PRINTER_ID=:printer_id
  │     → 取得 SERVER_IP（該印表機所屬的 Printer Server IP）
  │
  ├─ 6. HTTP POST 轉發 Task 到 Printer Server
  │     → http://{SERVER_IP}:9200/api/lb/task
  │     Header: Authorization: Bearer <token>
  │     Body: { uuid, printer_id, bar_type, site_id, data_1~19, status }
  │
  ├─ 7a. Printer Server 回應 success → 回傳 Client 成功
  └─ 7b. Printer Server 不可達 → 回傳 Client 錯誤（或排入重試）
```

### SRVDP010 印表機解析邏輯

```
SRVDP010（client_ip, bar_type）
  │
  ├─ 查 DP_COMPDEVICE_LABEL
  │   WHERE CLIENT_IP = :client_ip
  │   AND BAR_TYPE = :bar_type
  │
  ├─ 找到 → 回傳 PRINTER_ID
  └─ 找不到 → 回傳 null（SRVLB001 回報 "資訊設備標籤要先設定"）
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

格式：`[VERSION] + ['F'?固定參數] + 'W'[寬] + 'H'[長] + 'L'[左位移] + 'T'[上位移] + 'D'[明暗值] + [備註]`

VERSION 取自 `version.py` 的 `VERSION` 常數（目前 `v1.1r1`）。組 RESULT 一律透過 `local_db.build_result()` 函式。

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
| 刪除 | `local_db.remove_printer(site, pid, online)` | 刪 Cache + 排 SRVDP020 + DELETE |

> 離線時所有寫入操作排入 PENDING_OPS，上線後依 SEQ 順序 replay 回中央 DB。

---

## 跨模組 SRV（LB 相關的 DP 服務）

> **認證方式變更（2026-04-17）**：LB 不再呼叫 APIDP001 取得 TOKEN。
> TOKEN 與中央 API Base URL 皆**硬寫於 LBSB01 程式常數**（`login.py`）。
> 線上/離線改由「健康檢查端點」判定。

### 健康檢查端點（待主專案定義）

**提供方**: DP 模組
**呼叫方**: LBSB01（啟動時 + 每 60 秒）
**用途**: 判定中央是否可達 → 決定 `session.online`

| 項目 | 值 |
|------|-----|
| 方法 | `GET /api/health`（路徑待主專案定義） |
| 認證 | `Authorization: Bearer <硬寫 TOKEN>` |
| 成功回應 | 200 OK（任意 body） |
| 失敗判定 | 連線逾時 / 4xx / 5xx → 視為離線 |

### SRVDP010 — 標籤印表機查詢服務（印表機解析）

**提供方**: DP 模組
**呼叫場景**: SRVLB001 內部呼叫，解析 Client IP + bar_type → PRINTER_ID
**呼叫方**: 中央 SRVLB001（非 LBSB01 直接呼叫）

| 參數 | 型態 | 必填 | 說明 |
|------|------|------|------|
| client_ip | string | Y | 呼叫端工作站 IP |
| bar_type | string | Y | 標籤代碼（如 CP11、TL01） |

| 回傳 | 型態 | 說明 |
|------|------|------|
| found | boolean | 是否找到對應 |
| printer_id | string | 對應的印表機編號（found=true 時） |

**處理**: 查詢 DP_COMPDEVICE_LABEL WHERE CLIENT_IP = :client_ip AND BAR_TYPE = :bar_type

> 對應關係由管理者在「資訊設備」功能中設定。若未設定，SRVLB001 回傳 "資訊設備標籤要先設定"。

### SRVDP020 — 刪除元件設備標籤對應

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
