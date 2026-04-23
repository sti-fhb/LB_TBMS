# 使用契約：APILB004 — 修改印表機（Client 視角）

**呼叫方**: LBSB01（印表機設定頁「儲存變更」）
**方向**: LBSB01 → 中央 DP Server
**HTTP**: `PATCH /api/lb/printer/{printer_id}`
**完整 Server-side 契約**: 主專案 TBMS `docs/specs/lb/contracts/APILB004.md`

---

## 何時呼叫

常見情境：
| 操作 | 欄位 |
|------|------|
| 公差校正（印表機位置偏移） | `shift_left`、`shift_top` |
| 感熱元件老化補償 | `darkness` |
| 啟停印表機 | `is_active` |
| 換網段 | `server_ip`、`printer_ip` |
| 更新備註 | `note` |

## Local-first 流程

```
使用者修改欄位 + 儲存
  │
  ├─ 寫本地 LB_PRINTER_CACHE（即時反映於 UI 與列印解析）
  ├─ 排 PENDING_OPS(op=UPDATE, target=LB_PRINTER, printer_id, payload=變更欄位)
  │
  ▼ 上線
  │   Call APILB004 → 成功 → 清 PENDING_OPS
  │
  ▼ 離線
  │   PENDING_OPS 等 Timer / [更新] 觸發
```

## 衝突策略

離線中本地修改 + 中央也修改同一 `PRINTER_ID` → 上線 replay 時採**「一律以 Local 蓋中央」**（[離線原則](../spec.md#離線原則r03) R03 第 3 條）。直接送 PATCH 覆蓋中央值。

## 實作位置

`central_api.py` → `update_printer(printer_id, data)`
`local_db.py` → `save_printer(data, online)`

## 注意事項

- 只傳有變更的欄位（PATCH 語意）
- `PRINTER_ID` 不可改（PK）；若需改請先刪舊新建
- `printer_ip` / `printer_driver` 不能**同時**清空（至少保留一個定址方式）
