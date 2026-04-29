# LB 模組 SRV/API 契約索引（Server 實作視角）

本目錄為**中央實作方**視角的 SRV/API 完整契約——請求、回應、驗證、DB 操作、錯誤碼、Transaction 邊界。
**Client 使用方視角**（LBSB01 何時呼叫、Local-first 策略、retry、錯誤處理）在 LB 專案 `_LB/docs/specs/lb/contracts/`。

---

## 對內 SRV（Client 前端 / 中央 UI → 中央）

| 編碼 | 說明 | 存取 Table | 契約 |
|------|------|-----------|------|
| SRVLB001 | 標籤列印通用 API（兩種輸入模式） | `LB_PRINT_LOG` / `LB_PRINTER` | [SRVLB001.md](./SRVLB001.md) |
| SRVLB012 | 標籤列印紀錄查詢（分頁） | `LB_PRINT_LOG` + `LB_PRINTER` + `DP_SITE` JOIN | [SRVLB012.md](./SRVLB012.md) |
| SRVDP010 | 資訊設備標籤印表機查詢（Client IP + bar_type → 印表機資訊） | `DP_COMPDEVICE_LABEL` + `LB_PRINTER` | [SRVDP010.md](./SRVDP010.md) |

## 對外 API（LBSB01 → 中央，Bearer Token）

| 編碼 | HTTP 路由 | 說明 | 契約 |
|------|----------|------|------|
| APILB001 | GET `/api/lb/printers` | 查詢印表機清單（分頁 + 篩選） | [APILB001.md](./APILB001.md) |
| APILB002 | GET `/api/lb/printers/{id}` | 查詢單筆印表機 | [APILB002.md](./APILB002.md) |
| APILB003 | POST `/api/lb/printers` | 新增印表機 | [APILB003.md](./APILB003.md) |
| APILB004 | PATCH `/api/lb/printers/{id}` | 部分更新印表機 | [APILB004.md](./APILB004.md) |
| APILB005 | DELETE `/api/lb/printers/{id}` | 刪除印表機（硬刪 + cascade `DP_COMPDEVICE_LABEL`） | [APILB005.md](./APILB005.md) |
| APILB006 | POST `/api/lb/print-events` | 回報列印事件（append-only UPDATE）| [APILB006.md](./APILB006.md) |
| APILB007 | POST `/api/lb/print-logs` | 進件寫 LOG（INSERT） | [APILB007.md](./APILB007.md) |

## 命名歷史與近期變更

- **2026-04-21** — SRV/API 命名對齊：
  - 原 `SRVLB093` → `APILB001`
  - 原 `SRVLB091`（upsert）拆為 `APILB003`（POST 新增）+ `APILB004`（PATCH 修改）
  - 原 `SRVLB092` → `APILB005`
  - 原 `SRVLB011-標籤列印LOG更新` → `APILB006-回報列印事件`（append-only 事件流）
- **2026-04-22** — `APILB007` 從 `APILB006` 抽出（INSERT/UPDATE 配對分離）
- **2026-04-22** — `SRVDP020` 廢除，cascade 併入 `APILB005`
- **2026-04-22** — 移除健康檢查端點，離線偵測改由實際 Call APILB 結果判定

## 相關設計文件

- 模組 spec 總檔：[../spec.md](../spec.md)
- 資料模型：[../data-model.md](../data-model.md)
- User Stories：`../spec_us1.md` ~ `../spec_us6.md`
