# 使用契約：SRVLB012 — 標籤列印紀錄查詢（Client 視角）

**呼叫方**: 「LBSR01-歷史標籤查詢及補印作業」畫面（UI，非 LBSB01）
**方向**: 中央 UI → 中央 DP Server
**完整 Server-side 契約**: 主專案 TBMS `docs/specs/lb/contracts/SRVLB012.md`

---

## LBSB01 是否呼叫

**否**。SRVLB012 為中央 UI 使用。LBSB01 不直接呼叫。

## 與 LBSB01 的連動

操作者於「LBSR01-歷史查詢」畫面查到紀錄 → 選取補印 → UI 以 **[SRVLB001](./SRVLB001.md) 格式二**（`printer_id + log_uuid`）派送新 Task → 中央讀回原 `bar_type + data_*`（不重傳） → POST 至新印表機對應的 LBSB01（經 :9200）。

LBSB01 端 Listener 收到補印 Task 與一般列印 Task **處理路徑完全一致**（寫 Local Queue → 列印 → 回報 APILB006）。
