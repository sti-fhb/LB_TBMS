# 使用契約：APILB006 — 回報列印事件（Client 視角）

**呼叫方**: LBSB01
**方向**: LBSB01 → 中央 DP Server
**HTTP**: `POST /api/lb/print-events`
**完整 Server-side 契約**: 主專案 TBMS `docs/specs/lb/contracts/APILB006.md`

---

## 何時呼叫

LBSB01 任何改變 `LB_PRINT_LOG` **狀態或結果備註**的動作都透過本 API 回報中央：

| 事件 | status | result_memo |
|------|--------|-------------|
| 列印完成 | `1` | `v1.1r1-W80H35L40T0D8` 等（用 `local_db.build_result()`） |
| 自動移至 Offline（列印失敗） | `2` | `OffLine` |
| 手動移至 Offline | `2` | `OffLine` |
| 從 Offline 移回 Online | `0` | `OnLine` |
| 人工刪除（Online 區） | `1` | `Delete` |
| 人工刪除（Offline 區） | `1` | `Off_DEL` |
| POST 錯誤（由中央 SRVLB001 寫） | `1` | `POST_ERROR:{code}` |

## Local-first 流程

```
事件發生
  │
  ├─ local_db.update_print_log(uuid, status, result)  ← 本地 Cache 即時更新
  ├─ 排 PENDING_OPS(op=UPDATE, target=LB_PRINT_LOG, uuid, status, result_memo)
  │
  ▼ 上線
  │   central_api.replay_op → POST /api/lb/print-events
  │
  ▼ 離線
  │   PENDING_OPS 保留，Timer 3 分鐘 / [更新] 觸發後 replay
```

## RESULT 格式（由 LBSB01 端組）

```
[程式版本號]+'-'+[如果勾固定參數本欄為'F']+'W'+[寬]+'H'+[長]+'L'+[左位移]+'T'+[上位移]+'D'+[明暗值]+[備註]
```

**一律**透過 `local_db.build_result()` 函式組，不在中央組（中央直接寫入前端送來的字串）。程式版本號取自 LBSB01 `version.py` 的 `VERSION` 常數。

## 冪等性

相同 `(uuid, status, result_memo)` 重送 → 同值 UPDATE，無副作用。

## 實作位置

`central_api.py` → `replay_print_event(uuid, status, result_memo)`
`local_db.py` → `update_print_log(uuid, status, result)`、`build_result(params)`

## 與 APILB007 的差異

| 項目 | APILB007 | APILB006（本服務） |
|------|----------|-------------------|
| 動作 | INSERT 新 LOG | UPDATE 既有 LOG |
| 時機 | 進件首次寫入 | 狀態變更（完成/移動/刪除）|
| LBSB01 角色 | 通常由中央 SRVLB001 呼叫（LBSB01 只在測試頁直接呼叫）| LBSB01 主要寫入點 |
