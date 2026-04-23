# 使用契約：APILB007 — 新增列印事件（Client 視角）

**呼叫方**: 中央 SRVLB001（主要）/ LBSB01 標籤測試頁（少數情境）
**方向**: 中央內部 + LBSB01 → 中央
**HTTP**: `POST /api/lb/print-logs`
**完整 Server-side 契約**: 主專案 TBMS `docs/specs/lb/contracts/APILB007.md`

---

## LBSB01 是否呼叫

**多數情境不需要**。APILB007 主要由**中央 SRVLB001** 於 [Step 3] 進件寫 Log 時呼叫。LBSB01 端 Listener `:9200/api/lb/task` 收到的 Task 已由中央寫好 LOG（有 `uuid`）；LBSB01 只存本地 Cache、消化列印、事後用 [APILB006](./APILB006.md) 回報狀態。

**例外 — LBSB01 直接呼叫 APILB007 的情境**：
- **標籤測試頁** 從本機走 `localhost:9200` 走 Listener → **不經**中央 SRVLB001 → 需自行呼叫 APILB007 進件寫 LOG
- 離線補寫（若有）：離線中發生的本機列印，上線後補 POST

## 關鍵欄位（LBSB01 端）

| 欄位 | 由誰產生 |
|------|---------|
| `uuid` | LBSB01 端以 `uuid.uuid4()` 或類似產生，須唯一 |
| `bar_type` | 測試頁選擇的 LB_TYPE |
| `printer_id` | 當前指定印表機；保留字 `"USB"` 合法（跳過主檔驗證） |
| `site_id` | 本機 SITE_ID（從 `config.ini` 取） |
| `data_1 ~ data_19` | 測試標籤資料 |
| `status` | `0`=Online Queue（預設）、`2`=Offline Queue（測試用） |
| `ref_log_uuid` | 若為格式二補印，帶原 LOG UUID |

## Local-first 流程

```
LBSB01 測試頁 / 離線補寫
  │
  ├─ local_db.insert_print_log(data)  ← 本地 Cache 即時反映
  ├─ 排 PENDING_OPS(op=INSERT, target=LB_PRINT_LOG, payload=整筆)
  │
  ▼ 上線
  │   central_api.replay_op → POST /api/lb/print-logs（APILB007）
  │
  ▼ 離線
  │   保留 PENDING_OPS，Timer / [更新] 觸發後 replay
```

## 冪等性

LBSB01 產生的 UUID 應唯一。若 UUID 重複（409）代表前一次呼叫可能已成功但回應遺失，直接清 `PENDING_OPS` 該筆（視為成功）。

## 實作位置

`central_api.py` → `create_print_log(data)`
`local_db.py` → `insert_print_log(data, online=True)`
