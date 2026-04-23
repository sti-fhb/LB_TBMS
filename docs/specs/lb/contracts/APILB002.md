# 使用契約：APILB002 — 查詢單筆印表機（Client 視角）

**呼叫方**: LBSB01（罕用）
**方向**: LBSB01 → 中央 DP Server
**HTTP**: `GET /api/lb/printer/{printer_id}`
**完整 Server-side 契約**: 主專案 TBMS `docs/specs/lb/contracts/APILB002.md`

---

## 何時呼叫

**罕用**。LBSB01 通常透過 [APILB001](./APILB001.md) 整批取得清單後存本地 Cache，編輯時從 Cache 讀單筆。

僅在以下情境需補抓單筆：
- 中央管理員新增了印表機，但 LBSB01 本次同步尚未觸發
- 本地 Cache 損毀只剩部分記錄

## 實作位置

`central_api.py` → `fetch_printer_one(printer_id)`

## 注意事項

- `printer_id="USB"` 保留字**不可**用本 API 查詢（400 錯誤）；LBSB01 需在 client code 先判斷
