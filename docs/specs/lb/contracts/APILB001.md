# API 契約：查詢印表機清單

**編碼**: APILB001（原 SRVLB093）
**日期**: 2026-04-29（review 修訂）
**對應 FR**: FR-019（中央 UI 支援 LB_PRINTER 全域主檔 CRUD）
**對應 UseCase**: US4（印表機設定作業，LBSB01 端啟動/同步）、US6（中央印表機管理，管理員查詢）
**介接方向**: LBSB01 / 中央 Admin UI → 中央 DP Server
**類型**: 外部 API — Bearer Token 認證
**提供方**: 中央 DP Server
**呼叫方**:
- LBSB01 啟動、定時同步、設定頁開啟（用以覆蓋本地 Cache）
- 中央管理員 UI 查詢全域印表機清單

---

## 概述

回傳 `LB_PRINTER` 清單，可依 `SITE_ID` / `IS_ACTIVE` / 關鍵字篩選。`LB_PRINTER` 為硬刪除例外表（無 `DELETED` 欄位），刪除即從 DB 移除。

**存取 Table**: `LB_PRINTER`（讀取，可 JOIN `DP_SITE` 取站點名稱）
**HTTP 路由**: `GET /api/lb/printers`

---

## Request（Query String）

| 參數 | 型態 | 必填 | 說明 |
|------|------|------|------|
| site_id | string | N | 限定站點；空=全部站點 |
| is_active | int | N | `1`=僅啟用、`0`=僅停用、空=全部 |
| keyword | string | N | 關鍵字（比對 `PRINTER_ID` / `PRINTER_NAME` / `NOTE`） |
| page | int | N | 分頁頁碼（預設 1） |
| limit | int | N | 每頁筆數（預設 50，最大 200） |

> **UX 約束（依 lb/spec.md FR-020）**：「印表機下拉」場景（DP01 設備標籤對照、列印作業選印表機等）UI 端 **MUST 預設帶 Session 登入站點**，避免跨站點誤對照；僅 DP01 / DP06 高權限資訊人員可顯式清空 `site_id` 查全部。

**Header**: `Authorization: Bearer <token>`

---

## Response

| 欄位 | 型態 | 說明 |
|------|------|------|
| data | object[] | 印表機清單（依 `PRINTER_ID` 升序） |
| meta | object | `{ total, page, limit, total_pages }` |

`data[]` 欄位（型別與長度以 [`docs/specs/lb/data-model.md`](../data-model.md) §LB_PRINTER 為權威）：
`printer_id`、`printer_name`、`site_id`、`site_name`（JOIN DP_SITE）、`server_ip`、`printer_ip`、`printer_driver`、`shift_left`、`shift_top`、`paper_width`、`fix_paper_h`、`darkness`、`print_speed`、`model_no`、`is_active`、`note`、`updated_date`

---

## 處理流程

```
1. 驗證 Bearer Token → 401 若無效
2. 組 SELECT FROM LB_PRINTER（無 DELETED 欄位，所有記錄皆為現存印表機）
   依參數動態加 WHERE（site_id / is_active / keyword）
3. LEFT JOIN DP_SITE 取 SITE_NAME
4. 依 PRINTER_ID 升序排序
5. 分頁回傳
```

---

## 錯誤情境

| error_code | HTTP | 情境 | error_message |
|------------|------|------|--------------|
| DP_AUTH_003 | 401 | Token 無效 / 過期 | Token 無效或已過期（請檢查 `login.py` 的 `TOKEN` 常數） |
| COMMON_004 | 422 | `limit > 200` | limit 不得超過 200（本端點上限，與全域 100 不同） |
| COMMON_500 | 500 | DB 失敗 | Internal Server Error（呼叫端 LBSB01 視為離線，改讀本地 Cache） |

> error_code 規範參見 [`.claude/rules/sti-error-codes.md`](../../../../.claude/rules/sti-error-codes.md) 與 [`docs/ref/error-codes.md`](../../../ref/error-codes.md)。
>
> **注意**：`COMMON_004` 預設 message「limit 不得超過 100」，但本 API 因清單同步需求放寬至 200；後端 message 以本 API 的實際上限為準（建議實作層改用更明確的訊息或新增 LB_PRINTER 專屬錯誤碼）。

---

## LBSB01 側行為

- **啟動時**：呼叫本 API 取清單覆蓋本地 `LB_PRINTER_CACHE`；失敗則延用既有 Cache、啟動 Retry Timer（離線原則）
- **定時同步**：背景 Thread 呼叫，失敗不覆蓋本地
- **設定頁開啟**：嘗試同步 + 顯示本地 Cache（API 不通時仍可開啟）

離線中本地新增/修改/刪除的印表機，上線後依 `PENDING_OPS` 經 [APILB003](./APILB003.md) / [APILB004](./APILB004.md) / [APILB005](./APILB005.md) replay；replay 完成後再 Call APILB001 同步清單。

---

## 廢除歷史

> 原 `SRVLB093-印表機清單查詢` 於 2026-04-21 改名為 **APILB001**（對齊「對外 API 以 API 前綴」的命名規則）。
