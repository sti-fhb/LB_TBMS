# 使用契約：SRVDP010 — 資訊設備標籤印表機查詢（Client 視角）

**呼叫方**: 中央 SRVLB001 格式一（非 LBSB01 直接呼叫）
**方向**: 中央內部呼叫
**完整 Server-side 契約**: 主專案 TBMS `docs/specs/lb/contracts/SRVDP010.md`

![SRVDP010-標籤印表機查詢服務](./SRVDP010-標籤印表機查詢服務.png)

---

## LBSB01 是否呼叫

**否**。SRVDP010 由中央 SRVLB001 內部呼叫（解析 Client IP + bar_type → 印表機）。LBSB01 端不 Call 此服務。

## 為什麼 LBSB01 PG 需要瞭解

1. **保留字 `PRINTER_ID="USB"`**：DP_COMPDEVICE_LABEL 若設該值，SRVLB001 會略過 LB_PRINTER 查詢；LBSB01 要在本地印表機 Cache 上處理此保留字（不入 Cache、直接走本機 USB 直連路徑）
2. **錯誤「資訊設備需先設定」**：當 Client 發起列印卻未在 `DP_COMPDEVICE_LABEL` 設定對應時，SRVLB001 回此 MSG 且不寫 LB_PRINT_LOG；LBSB01 可能在測試頁遇到此情境（但 LBSB01 本機走 `localhost:9200` 時 `client_ip` 是 loopback，需要中央有對應記錄）

## 相關中央管理作業

`DP_COMPDEVICE_LABEL`（誰 + 哪種標籤 → 哪台印表機）對應表由中央管理員於「資訊設備」功能維護，詳見 [spec_us6.md](../spec_us6.md)。
