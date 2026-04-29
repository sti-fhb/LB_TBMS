# API 契約：查詢單筆印表機

**編碼**: APILB002
**日期**: 2026-04-29（review 修訂）
**對應 FR**: FR-019（中央 UI 支援 LB_PRINTER 全域主檔 CRUD）
**對應 UseCase**: US4（印表機設定作業 — 編輯頁載入）、US6（中央管理員檢視）
**介接方向**: LBSB01 / 中央 Admin UI → 中央 DP Server
**類型**: 外部 API — Bearer Token 認證
**提供方**: 中央 DP Server
**呼叫方**:
- LBSB01 設定頁編輯某印表機時載入完整欄位
- 中央管理員 UI「查看詳細」

---

## 概述

依 `PRINTER_ID` 取得單筆 `LB_PRINTER` 完整欄位。與 [APILB001](./APILB001.md) 差異：本 API 用於單筆詳細頁、查詢條件明確；APILB001 用於清單與篩選。

**存取 Table**: `LB_PRINTER`（讀取，JOIN `DP_SITE`）
**HTTP 路由**: `GET /api/lb/printers/{printer_id}`

---

## Request

| 參數 | 型態 | 必填 | 位置 | 說明 |
|------|------|------|------|------|
| printer_id | string(20) | Y | Path | 印表機編號（`LB_PRINTER.PRINTER_ID`，所有印表機—含 USB 連接者—皆為主檔內真實記錄）|

**Header**: `Authorization: Bearer <token>`

---

## Response

> 欄位長度與型別以 [`docs/specs/lb/data-model.md`](../data-model.md) §LB_PRINTER 為權威。

| 欄位 | 型態 | 說明 |
|------|------|------|
| printer_id | string(20) | 印表機編號 |
| printer_name | string(256) | 印表機名稱 |
| site_id | string(9) | 所屬站點 |
| site_name | string | 站點名稱（JOIN DP_SITE） |
| server_ip | string(20) | LBSB01 主機 IP |
| printer_ip | string(20) \| null | 印表機固定 IP（有填則優先採用） |
| printer_driver | string(20) \| null | `USB` / `#OS 印表機名` |
| shift_left | int | 左位移 |
| shift_top | int | 上位移 |
| paper_width | int \| null | 固定裝紙寬度（點數）|
| fix_paper_h | int \| null | 固定裝紙長度（點數）|
| darkness | int | 明暗 |
| print_speed | int \| null | 列印速度（GoDEX 1–6）|
| model_no | string(10) \| null | 印表機型號代碼 |
| is_active | int | `1`=啟用、`0`=停用 |
| note | string(200) \| null | 備註說明 |
| created_user / created_date / created_site | — | 建立資訊（稽核用） |
| updated_user / updated_date / updated_site | — | 最後異動資訊 |

---

## 處理流程

```
1. 驗證 Bearer Token → 401 若無效
2. SELECT FROM LB_PRINTER WHERE PRINTER_ID = :printer_id
3. LEFT JOIN DP_SITE 取 SITE_NAME
4. 無資料 → 404；有資料 → 回完整欄位（含 PRINTER_DRIVER，呼叫端據此決定列印路徑）
```

---

## 錯誤情境

| error_code | HTTP | 情境 | error_message |
|------------|------|------|--------------|
| DP_AUTH_003 | 401 | Token 無效 | Token 無效或已過期 |
| LB_PRINTER_005 | 404 | `printer_id` 查無 | 印表機不存在（LB_PRINTER 為硬刪除例外表，不存在即真的不存在）|

> error_code 規範參見 [`.claude/rules/sti-error-codes.md`](../../../../.claude/rules/sti-error-codes.md) 與 [`docs/ref/error-codes.md`](../../../ref/error-codes.md) §LB_PRINTER。

---

## LBSB01 側行為

LBSB01 通常不需要呼叫本 API——印表機清單透過 [APILB001](./APILB001.md) 整批取得後存本地 Cache，編輯時從 Cache 讀。只在本地 Cache 缺該筆時才透過本 API 補抓（例：管理員剛新增的印表機未在上次同步時出現）。
