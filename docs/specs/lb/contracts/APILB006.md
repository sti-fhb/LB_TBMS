# API 契約：回報列印事件

**編碼**: APILB006（原 SRVLB011）
**日期**: 2026-04-29（review 修訂）
**對應 FR**: FR-013（狀態變更事件 append-only 回寫）、FR-024（LB_PRINT_LOG append-only）
**對應 UseCase**: UCLB001（列印完成 / 移動 / 刪除）、UCLB101（LBSB01 內部狀態更新）
**介接方向**: LBSB01 → 中央 DP Server
**類型**: 外部 API — Bearer Token 認證
**提供方**: 中央 DP Server
**呼叫方**:
- LBSB01 列印完成後（事件：PRINTED，Status → 1，RESULT 寫入列印參數）
- 使用者於 Online / Offline Queue 上操作（事件：MOVED_OFFLINE / MODIFIED / DELETED）
- 其他需記錄列印事件的流程

---

## 概述

> **2026-04-21 重新命名**：原 `SRVLB011-標籤列印LOG更新` → `APILB006-回報列印事件`（對外 API）。語意從「更新 LOG」調整為「append-only 事件流」：LBSB01 對此資料**只寫、不讀、不改舊紀錄**，以單一 endpoint 配合 action 欄位分流各類事件。

**存取 Table**: `LB_PRINT_LOG`（依 UUID 更新 STATUS + RESULT；語意為 append-only 事件流）
**HTTP 路由**: `POST /api/lb/print-events`（由 LBSB01 `central_api.replay_op` replay 進來）

---

## Request

| 參數 | 型態 | 必填 | 說明 |
|------|------|------|------|
| uuid | string(36) | Y | `LB_PRINT_LOG` 的 UUID（主鍵） |
| status | int | N | 新狀態（`0`=Online 待列印、`1`=終態、`2`=離線區；空=不更新） |
| result_memo | string(200) | N | RESULT 備註段（見下方 RESULT 格式；空=保持原 RESULT） |

**Header**: `Authorization: Bearer <token>`

---

## Response

| 欄位 | 型態 | 說明 |
|------|------|------|
| success | boolean | 是否成功 |
| affected_rows | int | 更新筆數（預期為 1） |
| message | string | 訊息（失敗時為錯誤說明） |

---

## Status 狀態機

| Status | 語意 |
|--------|------|
| `0` | 待列印（Online Queue 中） |
| `1` | 終態（印出成功 or 人工刪除） |
| `2` | 離線區（Offline Queue） |

---

## RESULT 寫入格式

`LB_PRINT_LOG.RESULT` 欄位格式：

```
[程式版本號]+'-'+[如果勾固定參數本欄為'F']+'W'+[寬]+'H'+[長]+'L'+[左位移]+'T'+[上位移]+'D'+[明暗值]+[備註]
```

程式版本號取自 LBSB01 `version.py` 的 `VERSION` 常數。組 RESULT 一律透過 LBSB01 端 `local_db.build_result()` 函式，中央 APILB006 直接寫入前端組好的字串。

| 備註代碼 | 意義 | Status 變更 |
|---------|------|-----------|
| `OnLine` | 工作被移至 Online 區 | 保持 |
| `OffLine` | 工作被移至離線區 | → `2` |
| `Delete` | 工作被人工刪除（Online 區） | → `1` |
| `Off_DEL` | 工作在 Offline 區被刪除 | → `1` |

**範例**：
- 已印出（Status→1）：`v1.1r1-W80H35L40T0D8`
- 勾選固定參數：`v1.1r1-FW80H35L40T0D8`（`F` 僅於勾選「固定參數」時加入）
- 移至離線（Status→2）：`v1.1r1-OffLine`

---

## 處理流程

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
     ※ 稽核欄位來源見下方
  4. 回傳 success + affected_rows
```

### 稽核欄位來源

| 呼叫端 | UPDATED_USER | UPDATED_SITE |
|--------|--------------|--------------|
| LBSB01 → 本 API（Bearer Token 為服務 Token）| 固定 `'LBSB01'` | Bearer Token payload 中 `site_id`（即 LBSB01 部署站點） |

> APILB006 主要呼叫方為 LBSB01（無使用者 session），稽核欄位以服務識別字 `'LBSB01'` 記錄。

---

## 錯誤情境

| error_code | HTTP | 情境 | error_message |
|------------|------|------|--------------|
| DP_AUTH_003 | 401 | Token 無效 | Token 無效或已過期 |
| LB_PRINT_LOG_001 | 404 | UUID 查無 | 列印記錄不存在（可能發生於測試環境或資料不一致） |
| COMMON_422 | 422 | status 值不在 `{0,1,2}` 等型態錯誤 | 請求格式驗證失敗 |
| COMMON_500 | 500 | 寫入失敗（DB 錯） | Internal Server Error（呼叫端依 LBSB01 離線原則重試） |

> error_code 規範參見 [`.claude/rules/sti-error-codes.md`](../../../../.claude/rules/sti-error-codes.md) 與 [`docs/ref/error-codes.md`](../../../ref/error-codes.md) §LB_PRINT_LOG。

---

## 冪等性

LBSB01 重送相同 `(uuid, status, result_memo)` 不會造成副作用（同值 UPDATE）。LBSB01 端以 `PENDING_OPS` 的 SEQ 順序 replay，中央寫入成功後 LBSB01 移除該筆 PENDING_OPS。
