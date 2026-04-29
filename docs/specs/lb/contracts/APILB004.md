# API 契約：修改印表機

**編碼**: APILB004（原 SRVLB091 的 PATCH 部分）
**日期**: 2026-04-29（review 修訂）
**對應 FR**: FR-019（中央 UI 支援 LB_PRINTER 全域主檔 CRUD）
**對應 UseCase**: US4（LBSB01 端修改，含公差校正）、US6（中央管理員修改）
**介接方向**: LBSB01 / 中央 Admin UI → 中央 DP Server
**類型**: 外部 API — Bearer Token 認證
**提供方**: 中央 DP Server
**呼叫方**:
- LBSB01 設定頁「儲存變更」（上線時同步；離線時排 `PENDING_OPS`）
- 中央管理員 UI「編輯印表機」

---

## 概述

**部分更新**（PATCH 語意）`LB_PRINTER` 單筆記錄，只傳有變的欄位。`PRINTER_ID` 不可改（PK）；其他欄位皆可更新。

**存取 Table**: `LB_PRINTER`（UPDATE）
**HTTP 路由**: `PATCH /api/lb/printers/{printer_id}`

---

## Request

> 欄位長度與型別以 [`docs/specs/lb/data-model.md`](../data-model.md) §LB_PRINTER 為權威。

| 參數 | 型態 | 必填 | 位置 | 說明 |
|------|------|------|------|------|
| printer_id | string(20) | Y | Path | 目標印表機 PRINTER_ID（LB_PRINTER 主鍵）|

Body（JSON，欄位皆選填，只傳要改的）：

| 欄位 | 型態 | 說明 |
|------|------|------|
| printer_name | string(256) | 印表機名稱 |
| site_id | string(9) | 換站點時需有權限 |
| server_ip | string(20) | LBSB01 主機 IP；當印表機由 USB 改為網路類型時必填 |
| printer_ip | string(20) \| `null` | 傳 `null` 清空；清空後必須有 `printer_driver` |
| printer_driver | string(20) \| `null` | 同上 |
| shift_left | int | 左位移 [-200, 200] |
| shift_top | int | 上位移 [-200, 200] |
| paper_width | int | 固定裝紙寬度（點數）|
| fix_paper_h | int | 固定裝紙長度（點數）|
| darkness | int | 明暗 [1, 19] |
| print_speed | int | 列印速度 [1, 6] |
| model_no | string(10) | 印表機型號代碼 |
| is_active | int | `1` / `0` |
| note | string(200) | 備註說明 |

**Header**: `Authorization: Bearer <token>`

---

## Response

| 欄位 | 型態 | 說明 |
|------|------|------|
| success | boolean | |
| affected_rows | int | 預期為 `1` |
| message | string | 失敗訊息（成功時可為空）|

---

## 處理流程

```
1. 驗證 Bearer Token → 401
2. SELECT FROM LB_PRINTER WHERE PRINTER_ID = :printer_id
   → 若查無 → 404 / LB_PRINTER_005
3. 驗證 Request Body：
   - 若 printer_ip 和 printer_driver 都傳空 → 422 / LB_PRINTER_003
   - 若印表機從 USB 改為網路類型（傳新 server_ip 但未提供）→ 422 / LB_PRINTER_004
   - 型態 / 範圍驗證（同 APILB003）→ COMMON_422
4. UPDATE LB_PRINTER SET <變更欄位>,
          UPDATED_USER, UPDATED_DATE, UPDATED_SITE
   WHERE PRINTER_ID = :printer_id
   ※ UPDATED_USER / UPDATED_SITE 來源見下方「稽核欄位來源」
5. 回傳 success + affected_rows
```

### 稽核欄位來源

| 呼叫端 | UPDATED_USER | UPDATED_SITE |
|--------|--------------|--------------|
| 中央管理員 UI（JWT 認證走主系統登入） | JWT payload 的 `user_id` | JWT payload 的 `site_id`（Session 站點） |
| LBSB01 → 本 API（Bearer Token 為服務 Token）| 固定 `'LBSB01'` | Bearer Token payload 中 `site_id`（即 LBSB01 部署站點） |

> LBSB01 為服務型呼叫方（無使用者 session），稽核欄位以服務識別字 `'LBSB01'` 記錄；實際操作者於 LBSB01 端的 GUI session 中辨識，但跨系統稽核以 LBSB01 為單位。

---

## 冪等性

相同 Request 重複呼叫 → 結果一致（相同欄位值 UPDATE）。`UPDATED_DATE` 會每次刷新，屬於稽核記錄，不影響業務。

---

## 錯誤情境

| error_code | HTTP | 情境 | error_message |
|------------|------|------|--------------|
| DP_AUTH_003 | 401 | Token 無效 | Token 無效或已過期 |
| LB_PRINTER_005 | 404 | printer_id 查無 | 印表機不存在（LB_PRINTER 為硬刪除例外表，不存在即真的不存在）|
| LB_PRINTER_003 | 422 | 清空 printer_ip / printer_driver 雙方 | 必須提供印表機固定 IP 或印表機驅動之一 |
| LB_PRINTER_004 | 422 | 從 USB 改為網路印表機未填 server_ip | 網路印表機必須提供 LBSB01 主機 IP |
| COMMON_422 | 422 | 欄位型態錯誤 | 請求格式驗證失敗 |

> error_code 規範參見 [`.claude/rules/sti-error-codes.md`](../../../../.claude/rules/sti-error-codes.md) 與 [`docs/ref/error-codes.md`](../../../ref/error-codes.md) §LB_PRINTER。

---

## LBSB01 側行為（離線處理）

離線時的修改：
1. 寫本地 `LB_PRINTER_CACHE`（標記「待同步」）
2. 排 `PENDING_OPS(op_type=UPDATE, target=LB_PRINTER, printer_id, payload)`
3. 上線後依 SEQ replay：Call APILB004

### 衝突處理（一律以 Local 蓋中央）

上線 replay 時若中央也有異動，依離線原則 R03 第 3 條 — **一律以 Local 蓋中央**：直接送 PATCH 覆蓋中央值，不做合併或衝突偵測。

詳見 [spec_us3.md](../spec_us3.md) §離線同步 + [spec.md](../spec.md) §離線原則 R03。

---

## 常用修改情境（LBSB01 端）

| 情境 | 欄位 |
|------|------|
| 印表機位置偏移校正 | `shift_left`、`shift_top` |
| 感熱元件老化補償 | `darkness` |
| 啟停印表機 | `is_active`（`0`=停用、`1`=啟用） |
| 換網段 | `server_ip`、`printer_ip` |
| 更新備註 | `note` |
| 客製紙張規格 | `paper_width`、`fix_paper_h` |
| 列印速度調整 | `print_speed` |
