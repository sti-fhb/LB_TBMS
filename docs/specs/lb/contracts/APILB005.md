# 使用契約：APILB005 — 刪除印表機（Client 視角）

**呼叫方**: LBSB01（印表機設定頁「刪除」）
**方向**: LBSB01 → 中央 DP Server
**HTTP**: `DELETE /api/lb/printer/{printer_id}`
**完整 Server-side 契約**: 主專案 TBMS `docs/specs/lb/contracts/APILB005.md`

---

## 何時呼叫

操作者刪除印表機（實體裝置下線 / 退場）。

## Local-first 流程

```
使用者刪除印表機
  │
  ├─ 即時從本地 LB_PRINTER_CACHE 移除該筆
  ├─ 排 PENDING_OPS(op=DELETE, target=LB_PRINTER, printer_id)
  │
  ▼ 上線
  │   Call APILB005 → 成功 → 清 PENDING_OPS
  │   （中央同時 cascade 清 DP_COMPDEVICE_LABEL）
  │
  ▼ 離線
  │   該筆保留 PENDING_OPS，Timer / [更新] 觸發後 replay
```

## 後端 cascade（LBSB01 無需處理）

中央 APILB005 在同一 Transaction 內：
1. DELETE DP_COMPDEVICE_LABEL WHERE PRINTER_ID = 目標
2. DELETE LB_PRINTER WHERE PRINTER_ID = 目標

LBSB01 **不需**另外 Call 其他 API 清 `DP_COMPDEVICE_LABEL`（原 SRVDP020 已廢除，2026-04-22）。

## 實作位置

`central_api.py` → `delete_printer(printer_id)`
`local_db.py` → `remove_printer(site, pid, online)`

## 注意事項

- `printer_id="USB"` 保留字**不可**刪（400；UI 應防呆，不提供刪除按鈕給保留字）
- 刪除是**硬刪**，無法還原；建議 UI 二次確認
- 刪除不影響歷史列印紀錄（`LB_PRINT_LOG.PRINTER_ID` 仍保留文字值供稽核）
