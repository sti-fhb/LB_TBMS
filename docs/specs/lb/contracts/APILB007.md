# API 契約：新增列印事件

**編碼**: APILB007
**日期**: 2026-04-29（review 修訂）
**對應 FR**: FR-013（狀態變更事件 append-only 回寫）、FR-024（LB_PRINT_LOG append-only 寫入）、FR-001（SRVLB001 通用列印 API）
**對應 UseCase**: UCLB001（標籤列印）、UCLB002（補印）
**介接方向**: 中央 SRVLB001 → 中央 APILB007（同一 server 內部呼叫），或 LBSB01 → 中央
**類型**: 外部 API — Bearer Token 認證
**提供方**: 中央 DP Server
**呼叫方**:
- 中央 SRVLB001 於 [Step 3] 進件寫 LOG 時呼叫（格式一、格式二皆呼叫）
- LBSB01 本地測試頁 / 離線列印等需直接新增 LOG 的情境

---

## 概述

> **2026-04-22 新增**：單獨抽出「進件寫 LOG」為獨立端點，與 [APILB006](./APILB006.md) 「狀態變更事件」配對。

APILB007 是 `LB_PRINT_LOG` 的 **INSERT** 入口（事件起點）；APILB006 是 **UPDATE** 入口（append-only 事件流）。兩者職責明確切分。

**存取 Table**: `LB_PRINT_LOG`（新增）
**HTTP 路由**: `POST /api/lb/print-logs`

---

## Request

| 參數 | 型態 | 必填 | 說明 |
|------|------|------|------|
| uuid | string(36) | Y | 新 LOG 的 UUID（由呼叫端產生，供冪等與追溯） |
| bar_type | string(5) | Y | 標籤類別代碼（`LB_TYPE`，目前啟用 4 條：TL01 / CP01 / CP11 / CP19） |
| printer_id | string(20) | Y | 印表機編號（`LB_PRINTER.PRINTER_ID`，所有印表機—含 USB 連接者—皆為主檔內真實記錄；USB 直連由 `PRINTER_DRIVER='USB'` 識別）|
| site_id | string(9) | Y | 站點代碼（FK→`DP_SITE`）|
| data_1 ~ data_19 | string(512) | N | 標籤列印資料（依 `bar_type` 決定各欄位意義） |
| status | int | Y | 初始狀態：`0`=RECEIVED（Online Queue）、`2`=Offline Queue（測試頁用） |
| ref_log_uuid | string(36) | N | 格式二補印時帶入原 LOG UUID（寫入 `RES_ID`），供稽核追溯 |
| specimen_no | string(50) | N | 檢體號碼 |

**Header**: `Authorization: Bearer <token>`

---

## Response

| 欄位 | 型態 | 說明 |
|------|------|------|
| success | boolean | 是否成功 |
| uuid | string | 寫入的 UUID（回傳供呼叫端確認） |
| message | string | 錯誤訊息 |

---

## 處理流程

```
1. 驗證 Bearer Token → 401
2. 驗證 printer_id 存在於 LB_PRINTER → 404 / LB_PRINTER_005
   （含 PRINTER_DRIVER='USB' 的本機 USB 直連印表機）
3. 驗證 bar_type 為 LB_TYPE 啟用代碼之一 → 422 / LB_PRINT_LOG_003
4. 驗證 uuid 不重複（SELECT WHERE UUID = :uuid）→ 409 / LB_PRINT_LOG_002
5. INSERT INTO LB_PRINT_LOG（UUID、BAR_TYPE、PRINTER_ID、SITE_ID、Data1~19、
   STATUS、RES_ID=ref_log_uuid、CREATED_USER/DATE/SITE 標準欄位）
   ※ CREATED_USER / CREATED_SITE 來源見下方
6. 回傳 success + 該筆 UUID
```

### 稽核欄位來源

| 呼叫端 | CREATED_USER | CREATED_SITE |
|--------|--------------|--------------|
| 中央 SRVLB001 內部呼叫（從 Client 列印請求觸發）| 觸發 Client 之 JWT payload 的 `user_id` | JWT payload 的 `site_id` |
| LBSB01 → 本 API（測試頁 / 離線列印）| 固定 `'LBSB01'` | Bearer Token payload 中 `site_id` |

---

## 錯誤情境

| error_code | HTTP | 情境 | error_message |
|------------|------|------|--------------|
| DP_AUTH_003 | 401 | Token 無效 | Token 無效或已過期 |
| LB_PRINT_LOG_002 | 409 | UUID 重複 | 列印記錄 UUID 已存在（冪等處理：回原 UUID 或 ignore 再寫） |
| LB_PRINT_LOG_003 | 422 | `bar_type` 不支援 | 標籤類別代碼不支援 |
| LB_PRINTER_005 | 404 | `printer_id` 不存在於 `LB_PRINTER` | 印表機不存在 |
| COMMON_422 | 422 | 必填欄位缺漏或型態錯誤 | 請求格式驗證失敗 |

> error_code 規範參見 [`.claude/rules/sti-error-codes.md`](../../../../.claude/rules/sti-error-codes.md) 與 [`docs/ref/error-codes.md`](../../../ref/error-codes.md) §LB_PRINT_LOG / §LB_PRINTER。

---

## 與 APILB006 的差異

| 項目 | APILB007（本服務） | APILB006 |
|------|--------------------|---------|
| 動作 | `INSERT` 新 LOG | `UPDATE` 既有 LOG |
| 時機 | 列印進件首次寫入 | 狀態變更（完成 / 移動 / 刪除） |
| 關鍵欄位 | UUID + 業務欄位 + `Data_*` | UUID（定位）+ STATUS + RESULT |
| 資料模型語意 | 事件起點 | append-only 事件流 |
