# LB 模組 SRV/API 契約索引（Client 視角）

本目錄為 **LBSB01 使用方**視角的 SRV/API 說明——描述 LBSB01 何時呼叫、Local-first 策略、retry、錯誤處理。
完整的 **server-side 實作契約**（請求、回應、驗證、DB 操作、錯誤碼）在主專案 TBMS `docs/specs/lb/contracts/`。

> 2026-04-21 調整（SRV/API 命名對齊，對應主專案 #332）：
> - **SRV 對內、API 對外**。Client 前端各模組 → 中央為 SRV；LBSB01 → 中央為 API。
> - 原 `SRVLB093` → `APILB001`；原 `SRVLB091`（upsert）拆 `APILB003`（POST）+ `APILB004`（PATCH）；原 `SRVLB092` → `APILB005`；原 `SRVLB011` → `APILB006`。
> - 2026-04-22：拆出 `APILB007-新增列印事件`（INSERT）與 `APILB006-回報列印事件`（UPDATE）配對；SRVDP020 廢除（cascade 合併進 APILB005）。

---

## 對內 SRV（Client 前端 / 中央 UI 呼叫中央）

| 編碼 | 說明 | LBSB01 是否直接呼叫 | 契約 |
|------|------|---------------------|------|
| SRVLB001 | 標籤列印通用 API（兩種輸入模式） | 僅測試頁（走 `localhost:9200`） | [SRVLB001.md](./SRVLB001.md) |
| SRVLB012 | 標籤列印紀錄查詢 | 否（中央 UI 用） | [SRVLB012.md](./SRVLB012.md) |
| SRVDP010 | 資訊設備標籤印表機查詢 | 否（中央 SRVLB001 內部用）| [SRVDP010.md](./SRVDP010.md) |

## 對外 API（LBSB01 → 中央，Bearer Token）

| 編碼 | HTTP | 說明 | 觸發時機 | 契約 |
|------|------|------|---------|------|
| APILB001 | GET `/api/lb/printer` | 查印表機清單 | 啟動 / 同步 / 設定頁 | [APILB001.md](./APILB001.md) |
| APILB002 | GET `/api/lb/printer/{id}` | 查單筆印表機 | 罕用 | [APILB002.md](./APILB002.md) |
| APILB003 | POST `/api/lb/printer` | 新增印表機 | PENDING_OPS replay | [APILB003.md](./APILB003.md) |
| APILB004 | PATCH `/api/lb/printer/{id}` | 修改印表機 | PENDING_OPS replay | [APILB004.md](./APILB004.md) |
| APILB005 | DELETE `/api/lb/printer/{id}` | 刪除印表機（硬刪 + cascade） | PENDING_OPS replay | [APILB005.md](./APILB005.md) |
| APILB006 | POST `/api/lb/print-events` | 回報列印事件（append-only）| 列印完成 / 移動 / 刪除 | [APILB006.md](./APILB006.md) |
| APILB007 | POST `/api/lb/print-logs` | 進件寫 LOG（INSERT） | 測試頁 / 補寫 | [APILB007.md](./APILB007.md) |

## EA 有 Diagram 的契約

| 契約 | 圖檔 | 類型 |
|------|------|------|
| SRVLB001 | [SRVLB001-標籤列印通用API.png](./SRVLB001-標籤列印通用API.png) | CompositeStructure |
| SRVDP010 | [SRVDP010-標籤印表機查詢服務.png](./SRVDP010-標籤印表機查詢服務.png) | Activity |

## 離線通則

所有 LBSB01 → 中央 API 呼叫都遵守 [§離線原則](../spec.md#離線原則r03)：
1. Call API 失敗 → 切離線 → 啟 Retry Timer（每 3 分鐘）
2. 寫動作（INSERT/UPDATE/DELETE）先寫 Local DB + 排 `PENDING_OPS`
3. 上線後依 SEQ replay；衝突時一律以 Local 蓋中央

詳細離線 Queue / PENDING_OPS 機制見 [spec_us3.md](../spec_us3.md)。
