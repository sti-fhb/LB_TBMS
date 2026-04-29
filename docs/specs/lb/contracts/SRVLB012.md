# API 契約：標籤列印紀錄查詢

**編碼**: SRVLB012
**日期**: 2026-04-23
**對應 FR**: UCLB002（歷史查詢與補印標籤）
**介接方向**: 中央 UI（LBSR01-歷史標籤查詢及補印作業）→ 中央 DP Server
**類型**: 內部服務（SRV）— 模組間溝通
**提供方**: 中央 DP Server
**呼叫方**: 「LBSR01-歷史標籤查詢及補印作業」畫面（UCLB002）

---

## 概述

查詢 `LB_PRINT_LOG` 歷史紀錄，供操作者找回過去列印資料、檢視列印狀態、或選取目標紀錄補印（補印由 [SRVLB001](./SRVLB001.md) 格式二完成）。

**存取 Table**:
- `LB_PRINT_LOG`（讀取）
- `LB_PRINTER`（JOIN 取得印表機名稱）
- `DP_SITE`（JOIN 取得站點名稱）

**HTTP 路由**（若對外）: 透過中央 UI 內部呼叫；無對外 HTTP endpoint（純中央 SRV）

---

## Request（至少一項查詢條件）

| 參數 | 型態 | 必填 | 說明 |
|------|------|------|------|
| date_from | date | N | 列印時間起（`CREATED_DATE >= date_from`） |
| date_to | date | N | 列印時間迄（`CREATED_DATE <= date_to`） |
| site_id | string | N | 資料站點 |
| printer_id | string | N | 印表機編號 |
| bar_type | string | N | 標籤類別（CP01 / CP11 / TL01 …） |
| status | int | N | `0`=待列印 / `1`=終態 / `2`=離線區（空=全部） |
| specimen_no | string | N | 檢體號碼 |
| page | int | N | 分頁頁碼（預設 1） |
| limit | int | N | 每頁筆數（預設 20，最大 100） |

> 至少須傳一項查詢條件，全部空白時回 400「至少一項查詢條件」。

---

## Response

| 欄位 | 型態 | 說明 |
|------|------|------|
| data | object[] | 紀錄清單 |
| meta | object | `{ total, page, limit, total_pages }` |

`data[]` 欄位：
`uuid`、`bar_type`、`site_id`、`site_name`、`printer_id`、`printer_name`、`specimen_no`、`data_1`~`data_19`、`status`、`result`、`created_date`、`created_user`

---

## 處理流程

```
1. 驗證至少一項查詢條件（否則 400）
2. 組 SELECT，JOIN LB_PRINTER (PRINTER_NAME)、JOIN DP_SITE (SITE_NAME)
3. 依 CREATED_DATE DESC 排序
4. 分頁回傳
```

```sql
-- 概念性 SQL（實際依 ORM 組）
SELECT
  l.UUID, l.BAR_TYPE, l.SITE_ID, s.SITE_NAME,
  l.PRINTER_ID, p.PRINTER_NAME,
  l.SPECIMEN_NO, l.DATA_1, ..., l.DATA_19,
  l.STATUS, l.RESULT,
  l.CREATED_DATE, l.CREATED_USER
FROM LB_PRINT_LOG l
LEFT JOIN LB_PRINTER p ON l.PRINTER_ID = p.PRINTER_ID
LEFT JOIN DP_SITE    s ON l.SITE_ID    = s.SITE_ID
WHERE (:date_from IS NULL OR l.CREATED_DATE >= :date_from)
  AND (:date_to   IS NULL OR l.CREATED_DATE <= :date_to)
  AND (:site_id   IS NULL OR l.SITE_ID     = :site_id)
  AND (:printer_id IS NULL OR l.PRINTER_ID = :printer_id)
  AND (:bar_type  IS NULL OR l.BAR_TYPE    = :bar_type)
  AND (:status    IS NULL OR l.STATUS      = :status)
  AND (:specimen_no IS NULL OR l.SPECIMEN_NO = :specimen_no)
  AND l.DELETED = 0  -- 排除軟刪除（若有）
ORDER BY l.CREATED_DATE DESC
LIMIT :limit OFFSET (:page - 1) * :limit;
```

---

## 補印連動

使用者在結果清單選取要補印的紀錄，前端以該筆的 `printer_id` + `log_uuid`（即該筆 LB_PRINT_LOG 的 UUID）**以格式二呼叫 [SRVLB001](./SRVLB001.md)**。中央依 `log_uuid` 讀 `LB_PRINT_LOG` 取回原 `bar_type` + `data_*`（不重傳），跳過 SRVDP010 解析，直接派送 Task 至指定印表機。補印時可指定不同於原紀錄的印表機。

流程：
```
UI「歷史查詢」→ 呼叫 SRVLB012 → 顯示清單
操作者選取某筆 + 選新印表機 → 呼叫 SRVLB001 格式二
  │
  └─→ 中央新增一筆 LB_PRINT_LOG（新 UUID, RES_ID=原UUID）→ POST Task 至新印表機
```

---

## 錯誤情境

| 情境 | HTTP | 說明 |
|------|------|------|
| 全部查詢條件為空 | 400 | 「至少一項查詢條件」 |
| `limit > 100` | 400 | 超過最大分頁筆數 |
| `status` 值不在 `{0,1,2}` | 400 | 狀態碼錯誤 |
| 查詢條件合法但無結果 | 200 + `data: []` | 非錯誤，純無資料 |

---

## 分頁與效能

- 預設 `limit=20`（UI 預設）
- 最大 `limit=100`（避免 payload 過大）
- `total_pages = ceil(total / limit)`
- 建議 `LB_PRINT_LOG` 於 `CREATED_DATE` + `SITE_ID` + `PRINTER_ID` 建索引以支援常見查詢組合
