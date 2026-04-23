# 使用契約：APILB003 — 新增印表機（Client 視角）

**呼叫方**: LBSB01（印表機設定頁「新增」）
**方向**: LBSB01 → 中央 DP Server
**HTTP**: `POST /api/lb/printer`
**完整 Server-side 契約**: 主專案 TBMS `docs/specs/lb/contracts/APILB003.md`

---

## 何時呼叫

操作者於 LBSB01 「標籤印表機設定」子視窗按**新增**並儲存時觸發：
- **線上**：立即 Call APILB003；成功則寫本地 Cache
- **離線**：先寫本地 `LB_PRINTER_CACHE`（標記「待同步」），排一筆 `PENDING_OPS(INSERT, LB_PRINTER)`，上線後 replay

## Local-first 流程

```
使用者儲存新印表機
  │
  ├─ 寫本地 LB_PRINTER_CACHE（即時反映於清單）
  ├─ 排 PENDING_OPS(op=INSERT, target=LB_PRINTER, payload=整筆)
  │
  ▼ 上線狀態下
  │   Call APILB003 → 成功 → 清 PENDING_OPS + 清「待同步」標記
  │   Call APILB003 → 409 (重複) → 改走 APILB004 PATCH 覆蓋（Local 蓋中央）
  │
  ▼ 離線狀態
  │   該筆保留在 PENDING_OPS，Timer / [更新] 觸發後 replay
```

## 實作位置

`central_api.py` → `create_printer(data)`
`local_db.py` → `add_printer(data, online=True)` 決定走即時 Call 或排 PENDING_OPS

## 驗證（客戶端先行）

儲存前在 LBSB01 本地先做：
- `printer_id` 非保留字 `"USB"`（UI 防呆）
- `printer_ip` 和 `printer_driver` 至少一項有值

避免送到中央才被 400 駁回。
