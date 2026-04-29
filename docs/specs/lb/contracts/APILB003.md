# API 契約：新增印表機

**編碼**: APILB003（原 SRVLB091 的 POST 部分）
**日期**: 2026-04-29（review 修訂）
**對應 FR**: FR-019（中央 UI 支援 LB_PRINTER 全域主檔 CRUD）
**對應 UseCase**: US4（LBSB01 端新增印表機）、US6（中央管理員新增）
**介接方向**: LBSB01 / 中央 Admin UI → 中央 DP Server
**類型**: 外部 API — Bearer Token 認證
**提供方**: 中央 DP Server
**呼叫方**:
- LBSB01 印表機設定頁「新增」（上線時同步；離線時排 `PENDING_OPS` 稍後 replay）
- 中央管理員 UI「新增印表機」

---

## 概述

新增一筆 `LB_PRINTER`。USB 印表機亦為一般主檔記錄（透過 `printer_driver="USB"` 欄位識別），不在 `printer_id` 維度設保留字。

**存取 Table**: `LB_PRINTER`（INSERT）
**HTTP 路由**: `POST /api/lb/printers`

---

## Request（Body，JSON）

> 欄位長度與型別以 [`docs/specs/lb/data-model.md`](../data-model.md) §LB_PRINTER 為權威。

| 欄位 | 型態 | 必填 | 說明 |
|------|------|------|------|
| printer_id | string(20) | Y | 主鍵；建議「站點碼-流水號」格式（如 `S01-PRN-020`），便於跨站點識別 |
| printer_name | string(256) | Y | 印表機名稱 |
| site_id | string(9) | Y | 所屬站點（FK→`DP_SITE`） |
| server_ip | string(20) | **條件必填** | LBSB01 主機 IP；當 `printer_driver != 'USB'` 時必填（網路印表機需經 LBSB01 中介派送） |
| printer_ip | string(20) | N | 印表機固定 IP；**有填則列印時優先採用**，Port 固定 `9100` |
| printer_driver | string(20) | N | `USB` / `#OS 印表機名`（`printer_ip` 空時必填其一）；**`"USB"` 表示該印表機透過本機 USB 直連，列印時走 USB Port 而非網路** |
| shift_left | int | N | 左位移（預設 `0`） |
| shift_top | int | N | 上位移（預設 `0`） |
| paper_width | int | N | 固定裝紙寬度（點數）；通常空白由 `LB_TYPE.WIDTH` 自動帶入，僅特殊客製紙張才填 |
| fix_paper_h | int | N | 固定裝紙長度（點數）；通常空白由 `LB_TYPE.LENGTH` 自動帶入 |
| darkness | int | N | 明暗（預設 `12`） |
| print_speed | int | N | 列印速度（GoDEX 1–6，預設 `2`） |
| model_no | string(10) | N | 印表機型號代碼（如 `EZ120`、`RT700i`，參考用） |
| is_active | int | Y | `1`=啟用（預設）、`0`=停用 |
| note | string(200) | N | 備註說明 |

**Header**: `Authorization: Bearer <token>`

> **欄位來源備註**：
> - `printer_name`、`site_id`、`server_ip`、`printer_ip`、`printer_driver` 等長度依 LB_PRINTER DDL（VARCHAR 各欄位長度）。
> - `paper_width` / `fix_paper_h` / `print_speed` 為硬體層公差參數，多數情境由 `LB_TYPE` 代碼表帶入，僅在客製紙張或印表機老化補償時手動覆寫。
> - `model_no` 為原 data-model `MODEL_NO` 欄位（API 層採 snake_case 對齊 JSON 慣例）。

---

## Response

| 欄位 | 型態 | 說明 |
|------|------|------|
| success | boolean | 是否成功 |
| printer_id | string | 寫入的 PRINTER_ID（冪等確認） |
| message | string | 失敗訊息（成功時可為空） |

---

## 處理流程

```
1. 驗證 Bearer Token → 401
2. 驗證 printer_id 不可重複（SELECT WHERE PRINTER_ID = :printer_id）→ 409 / LB_PRINTER_001
3. 驗證 site_id 存在於 DP_SITE → 422 / LB_PRINTER_002
4. 驗證 printer_ip 或 printer_driver 至少其一有值 → 422 / LB_PRINTER_003
5. 驗證 printer_driver != 'USB' 時 server_ip 必填 → 422 / LB_PRINTER_004
6. INSERT INTO LB_PRINTER (..., CREATED_USER, CREATED_DATE, CREATED_SITE)
   ※ CREATED_USER / CREATED_SITE 來源見下方「稽核欄位來源」
7. 回傳 success + printer_id
```

### 稽核欄位來源

| 呼叫端 | CREATED_USER | CREATED_SITE |
|--------|--------------|--------------|
| 中央管理員 UI（JWT 認證走主系統登入） | JWT payload 的 `user_id` | JWT payload 的 `site_id`（Session 站點） |
| LBSB01 → 本 API（Bearer Token 為服務 Token）| 固定 `'LBSB01'` | Bearer Token payload 中 `site_id`（即 LBSB01 部署站點） |

> LBSB01 為服務型呼叫方（無使用者 session），稽核欄位以服務識別字 `'LBSB01'` 記錄；實際操作者於 LBSB01 端的 GUI session 中辨識，但跨系統稽核以 LBSB01 為單位。

---

## 欄位驗證規則

| 欄位 | 規則 |
|------|------|
| printer_id | 非空、長度 ≤ 20、不可重複 |
| printer_name | 非空、長度 ≤ 256 |
| site_id | 必須存在於 `DP_SITE` |
| server_ip | IPv4 格式（長度 ≤ 20）；`printer_driver != 'USB'` 時必填 |
| printer_ip | 若填，IPv4 格式（長度 ≤ 20） |
| printer_driver | 若填，`USB`（本機 USB 直連）或 `#XXX`（`#` 開頭，OS 印表機名）|
| shift_left / shift_top | 整數，範圍 [-200, 200] |
| paper_width / fix_paper_h | 正整數（GoDEX 點數，1 mm ≈ 8 dots） |
| darkness | 整數，範圍 [1, 19]（GoDEX 建議範圍） |
| print_speed | 整數，範圍 [1, 6]（GoDEX 速度等級） |
| model_no | 長度 ≤ 10（如 `EZ120`） |
| is_active | `0` 或 `1` |

---

## 錯誤情境

| error_code | HTTP | 情境 | error_message |
|------------|------|------|--------------|
| DP_AUTH_003 | 401 | Token 無效 / 過期 | Token 無效或已過期 |
| LB_PRINTER_001 | 409 | printer_id 重複 | 印表機編號已存在 |
| LB_PRINTER_002 | 422 | site_id 不存在 | 所屬站點不存在 |
| LB_PRINTER_003 | 422 | printer_ip 與 printer_driver 都空 | 必須提供印表機固定 IP 或印表機驅動之一 |
| LB_PRINTER_004 | 422 | 非 USB 印表機未填 server_ip | 網路印表機必須提供 LBSB01 主機 IP |
| COMMON_422 | 422 | 欄位型態錯誤 | 請求格式驗證失敗 |

> error_code 編號與規則參見 [`.claude/rules/sti-error-codes.md`](../../../../.claude/rules/sti-error-codes.md) 與 [`docs/ref/error-codes.md`](../../../ref/error-codes.md) §LB_PRINTER。

---

## LBSB01 側行為（離線處理）

離線時的新增：
1. 寫本地 `LB_PRINTER_CACHE`（標記「待同步」）
2. 排一筆 `PENDING_OPS(op_type=INSERT, target=LB_PRINTER, payload=整筆)`
3. 上線後依 SEQ replay：Call APILB003 → 成功移除 `PENDING_OPS` 該筆 + 清「待同步」標記

### 衝突處理（離線 replay 回 409）

中央可能已有同 `PRINTER_ID`（如另一 LBSB01 先建立）；replay 時依下列規則處理：

1. APILB003 回 `LB_PRINTER_001`（409） → LBSB01 視為衝突
2. 依離線原則 R03「一律以 Local 蓋中央」 → LBSB01 **自動**將該筆 `PENDING_OPS` 改為 `op_type=UPDATE` 並改呼叫 [APILB004](./APILB004.md) PATCH
3. APILB004 成功 → 移除 `PENDING_OPS` + 清「待同步」標記
4. APILB004 仍失敗 → 保留 `PENDING_OPS`，下個 Timer 週期 retry，並在 LBSB01 GUI 顯示衝突警示

> 此自動轉換為 LBSB01 端內部處理，**呼叫端（管理員 UI）不需感知**；中央 API 仍嚴格區分 POST / PATCH 語意。詳見 [spec_us3.md](../spec_us3.md) §離線同步 + [spec_us4.md](../spec_us4.md) §離線編輯。

---

## 廢除歷史

> 原 `SRVLB091-印表機 Upsert`（同一端點兼負新增與修改）於 2026-04-21 拆為 **APILB003（POST 新增）** + **APILB004（PATCH 修改）**，對齊 REST 慣例。
