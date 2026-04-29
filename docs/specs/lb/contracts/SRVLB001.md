# API 契約：標籤列印通用 API

**編碼**: SRVLB001
**日期**: 2026-04-23
**對應 FR**: UCLB001（標籤列印），UCLB002（歷史查詢補印）
**介接方向**: Client 前端（BC / CP / BS / TL）/ LBSB01 標籤測試頁 → 中央 DP Server
**類型**: 內部服務（SRV）— 模組間溝通
**提供方**: DP 模組（中央 Server）
**呼叫方**: Client 前端各模組、LBSB01 標籤測試頁、歷史查詢補印（UCLB002）

---

## 概述

中央統一的標籤列印入口。接收 Client 端的列印請求，解析目標印表機後將 Task POST 至對應 LBSB01 Listener（`:9200/api/lb/task`），並寫入 `LB_PRINT_LOG`（進件事件經 APILB007）。

支援兩種輸入模式：
- **格式一（一般列印）**：`bar_type` + `site_id` + `data_*`，中央透過 SRVDP010 依 Client IP + bar_type 解析 PRINTER_ID / SERVER_IP / 參數。
- **格式二（補印）**：`printer_id` + `log_uuid`，中央依 `log_uuid` 讀 `LB_PRINT_LOG` 取回原 `bar_type` + `data_*`（不重傳），可指定新印表機。

格式由傳入參數判定：有 `log_uuid` 即走格式二；否則走格式一。

**存取 Table**:
- `LB_PRINT_LOG`（經 APILB007 寫進件，經 APILB006 寫狀態事件；格式二另需讀取）
- `LB_PRINTER`（格式二直接讀取）

**依賴服務**: SRVDP010（僅格式一）、APILB007（進件寫 LOG）

![SRVLB001-標籤列印通用API](./SRVLB001-標籤列印通用API.png)

---

## Request

| 參數 | 型態 | 必填 | 說明 |
|------|------|------|------|
| bar_type | string | 格式一 Y / 格式二 N | 條碼處理種類（格式二由原 LOG 帶出） |
| site_id | string | 格式一 Y / 格式二 N | 資料站點（格式二由原 LOG 帶出） |
| printer_id | string | 格式二必填 | 指定印表機編號；格式一由中央解析 |
| log_uuid | string | 格式二必填 | 原 `LB_PRINT_LOG` 的 UUID；中央據此取回原 `data_*` |
| specimen_no | string | N | 檢體號碼（格式一） |
| data_1 ~ data_19 | string | 格式一 N / 格式二不傳 | 標籤資料（格式二由原 LOG 帶出） |
| status | int | N | 初始狀態：`0`=Online Queue（預設）、`2`=Offline Queue（測試頁用） |

> 格式一：`printer_id` 不由 Client 傳入，中央透過 SRVDP010（Client IP + bar_type）解析；同時取回 `SERVER_IP` / 參數。
> 格式二：Client 指定 `printer_id` + `log_uuid`（UCLB002 補印），SRVDP010 不介入；中央讀 `LB_PRINT_LOG(log_uuid)` 取回 BAR_TYPE + data_*，讀 `LB_PRINTER(printer_id)` 取 SERVER_IP + 參數。

---

## Response

| 欄位 | 型態 | 說明 |
|------|------|------|
| success | boolean | 是否成功 |
| uuid | string | 新增 `LB_PRINT_LOG` 的 UUID（成功時） |
| printer_id | string | 解析出的印表機編號（成功時） |
| message | string | 訊息（失敗時為錯誤說明） |

---

## 處理流程（中央派送 + LBSB01 接收）

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
  ├─ 3. 呼叫 APILB007 進件寫 LOG（新 UUID、BAR_TYPE、PRINTER_ID、STATUS=0 RECEIVED、ref_log_uuid=log_uuid（若格式二））
  │     ※ 補印亦新增一筆（非更新原紀錄）；以 RES_ID 可追溯原 log_uuid
  │
  ├─ 4. HTTP POST 轉發 Task 到 Printer Server（LBSB01 Listener）
  │     → http://{SERVER_IP}:9200/api/lb/task
  │     Header: Authorization: Bearer <token>
  │     Body: { uuid（新）, printer_id, bar_type, site_id, data_1~19, status }
  │
  └─ 5. 判斷 POST Error？
        ├─ Error → 5a. 呼叫 APILB006 回報失敗（依新 UUID）：
        │              status=1, result_memo=POST_ERROR:{Error Code}
        │          → 5b. 回傳 MSG「標籤列印送出失敗：可能為網路問題或標籤服務沒連 IP:{SERVER_IP}」
        │          → 結束
        └─ 成功 → 回傳新 UUID + 成功訊息
```

---

## SRVDP010 印表機解析邏輯（格式一）

```
SRVDP010（client_ip, bar_type）
  │
  ├─ Step 1：以 client_ip 中介取 CDE_ID（查 DP_COMPDEVICE.IP）
  │          再查 DP_COMPDEVICE_LABEL
  │          WHERE CDE_ID = :cde_id AND LABEL_TYPE = :bar_type
  │          → 取得 PRINTER_ID
  │
  ├─ Step 2：查 LB_PRINTER
  │          WHERE PRINTER_ID = :printer_id
  │          → 取得 SERVER_IP、SERVER_PORT、printer_params
  │
  ├─ 找到 → 回傳 {printer_id, server_ip, server_port, printer_params}
  └─ 找不到 → 回 404（SRVLB001 回報「資訊設備需先設定」）
```

> `DP_COMPDEVICE_LABEL` 由管理者在「資訊設備」功能中設定，建立「哪台工作站 + 哪種標籤 → 由哪台印表機列印」的對應關係。詳見 [SRVDP010](./SRVDP010.md)。

---

## LBSB01 端接收（Task Listener :9200）

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

## 多台 Printer Server 路由

中央 SRVLB001 依 `LB_PRINTER.SERVER_IP` 路由：

```
PRN-001（SERVER_IP=192.168.1.10）→ POST http://192.168.1.10:9200/api/lb/task
PRN-002（SERVER_IP=192.168.1.10）→ POST http://192.168.1.10:9200/api/lb/task（同一台）
PRN-101（SERVER_IP=192.168.2.10）→ POST http://192.168.2.10:9200/api/lb/task
```

## Port 規則

| Port | 用途 | 可設定 |
|------|------|--------|
| 9100 | GoDEX 印表機 TCP 列印 | 印表機端固定 |
| **9200** | LBSB01 HTTP Listener（接收 Task） | **固定，不可設定** |

---

## 錯誤情境

| 情境 | HTTP | 處理 |
|------|------|------|
| 格式一：SRVDP010 回 404 | 200 + `success=false` | MSG「資訊設備需先設定」，不寫 LOG |
| 格式二：`log_uuid` 查不到 | 200 + `success=false` | MSG「原列印紀錄不存在」 |
| 格式二：`printer_id` 查不到 | 200 + `success=false` | MSG「指定印表機不存在」 |
| POST Task 至 LBSB01 失敗 | 200 + `success=false` | 依 APILB006 寫 `status=1, result=POST_ERROR:{code}`，回 MSG「標籤列印送出失敗…」 |
