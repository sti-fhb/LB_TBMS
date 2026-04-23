# 使用契約：APILB001 — 查詢印表機清單（Client 視角）

**呼叫方**: LBSB01
**方向**: LBSB01 → 中央 DP Server
**HTTP**: `GET /api/lb/printer`
**完整 Server-side 契約**: 主專案 TBMS `docs/specs/lb/contracts/APILB001.md`

---

## 何時呼叫

| 時機 | 行為 |
|------|------|
| LBSB01 啟動 | 取清單覆蓋本地 `LB_PRINTER_CACHE`；失敗則延用既有 Cache、切換離線 |
| 定時同步（Retry Timer 週期或定期）| 背景 Thread 呼叫；失敗**不**覆蓋本地 |
| 設定頁開啟 | 嘗試同步 + 顯示本地 Cache |
| 上線後 | replay `PENDING_OPS` 完成後重新同步清單 |

## 實作位置

`central_api.py` → `fetch_printers(site_id=None, is_active=1)`

通常只需要 `site_id`（等於本機 SITE_ID）+ `is_active=1` 篩選。

## 離線處理

- API 失敗 → 觸發離線狀態（[離線原則](../spec.md#離線原則r03)）
- 本地 Cache 保留最後一次成功同步的資料，仍可支援列印與設定頁操作

## 注意事項

- 印表機保留字 `"USB"` **不**會出現在 APILB001 回傳清單（USB 不入中央主檔）
- LBSB01 自己須在本地 Cache 加入該保留字作為「USB 虛擬印表機」供選擇
