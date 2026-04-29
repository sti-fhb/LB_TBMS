# API 契約：刪除印表機

**編碼**: APILB005（原 SRVLB092）
**日期**: 2026-04-29（review 修訂）
**對應 FR**: FR-019（中央 UI 支援 LB_PRINTER 全域主檔 CRUD）、FR-021（刪除印表機 cascade 清 DP_COMPDEVICE_LABEL）、FR-016（LBSB01 PENDING_OPS replay）
**對應 UseCase**: US4（LBSB01 端刪除）、US6（中央管理員刪除）
**介接方向**: LBSB01 / 中央 Admin UI → 中央 DP Server
**類型**: 外部 API — Bearer Token 認證
**提供方**: 中央 DP Server
**呼叫方**:
- LBSB01 設定頁「刪除印表機」（上線時同步；離線時排 `PENDING_OPS`）
- 中央管理員 UI「刪除印表機」

---

## 概述

刪除 `LB_PRINTER` 單筆記錄。**硬刪**（HARD DELETE）；後端在 Transaction 內 **cascade 清** `DP_COMPDEVICE_LABEL` 子表中引用該 `PRINTER_ID` 的對應。

> **2026-04-22 簡化**：原「LBSB01 → SRVDP020 → SRVLB092」兩段式流程已廢除。SRVDP020 已停用；由本 APILB005 單一端點在 Transaction 內完成 cascade + 硬刪。

**存取 Table**:
- `DP_COMPDEVICE_LABEL`（DELETE — cascade）
- `LB_PRINTER`（DELETE — 硬刪）

**HTTP 路由**: `DELETE /api/lb/printers/{printer_id}`

---

## Request

| 參數 | 型態 | 必填 | 位置 | 說明 |
|------|------|------|------|------|
| printer_id | string(20) | Y | Path | 目標印表機 PRINTER_ID（LB_PRINTER 主鍵）|

**Header**: `Authorization: Bearer <token>`

---

## Response

| 欄位 | 型態 | 說明 |
|------|------|------|
| success | boolean | |
| printer_id | string | 刪除的 PRINTER_ID |
| cascade_cleared | int | 同時從 `DP_COMPDEVICE_LABEL` 清除的對應筆數 |
| message | string | |

---

## 處理流程

```
1. 驗證 Bearer Token → 401
2. SELECT FROM LB_PRINTER WHERE PRINTER_ID = :printer_id
   → 若查無 → 404
3. BEGIN TRANSACTION
   ├─ 3a. DELETE FROM DP_COMPDEVICE_LABEL WHERE PRINTER_ID = :printer_id
   │      → 記錄刪除筆數（cascade_cleared）
   ├─ 3b. DELETE FROM LB_PRINTER WHERE PRINTER_ID = :printer_id
   │      → 硬刪
   └─ COMMIT
4. 回傳 success + printer_id + cascade_cleared
```

**為什麼硬刪而非軟刪？**
- `LB_PRINTER` 屬裝置主檔，刪除代表實體設備已下線/移除，不需保留歷史記錄供業務追溯
- 列印歷史紀錄（`LB_PRINT_LOG`）仍保留 `PRINTER_ID` 文字值，可作稽核（但 JOIN 後 `printer_name` 會是空）
- 避免軟刪造成 UNIQUE 限制衝突（新建同代碼印表機時需繞開軟刪記錄）
- **schema 不含 `DELETED` 欄位**，與 `DP_SCHEDULE` / `DP_COMPDEVICE` 同列硬刪除例外表（見 `.claude/rules/sti-backend-modules.md`）

---

## 錯誤情境

| error_code | HTTP | 情境 | error_message |
|------------|------|------|--------------|
| DP_AUTH_003 | 401 | Token 無效 | Token 無效或已過期 |
| LB_PRINTER_005 | 404 | printer_id 查無 | 印表機不存在（冪等：第二次刪除同 ID 時回此） |
| COMMON_500 | 500 | DB 失敗（Transaction rollback） | Internal Server Error（呼叫端視為暫時失敗，依離線原則重試） |

> error_code 規範參見 [`.claude/rules/sti-error-codes.md`](../../../../.claude/rules/sti-error-codes.md) 與 [`docs/ref/error-codes.md`](../../../ref/error-codes.md) §LB_PRINTER。

---

## LBSB01 側行為（離線處理）

離線時的刪除：
1. 即時從本地 `LB_PRINTER_CACHE` 移除該筆
2. 排一筆 `PENDING_OPS(op_type=DELETE, target=LB_PRINTER, printer_id)`
3. 上線後依 SEQ replay：Call APILB005

**無跨模組副作用的本地處理**：LBSB01 只需排一筆 DELETE LB_PRINTER（對應 APILB005），**不再**有跨模組 CALL_SRV 操作（因 SRVDP020 已廢除，cascade 由中央在 Transaction 內處理）。

---

## 廢除歷史

> - 原 `SRVLB092-印表機刪除` 於 2026-04-21 改名為 **APILB005**
> - 原 `SRVDP020-刪除元件設備標籤對應` 於 2026-04-22 廢除，功能併入本 APILB005 的 Transaction 內 cascade
