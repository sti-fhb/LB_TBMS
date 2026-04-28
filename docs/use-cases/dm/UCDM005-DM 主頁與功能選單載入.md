# UCDM005-DM 主頁與功能選單載入

使用者完成 [UCDM004 DM 登入](UCDM004-DM%20登入.md) 後進入 DM 主頁；DM 後端**依 SS 回傳之可用功能清單**渲染主頁功能選單。

- **主要參與者**：使用者
- **對應功能選項**：DM04-主頁
- **前置條件**：已通過 UCDM004 DM 登入，瀏覽器 session 持有 SS 角色、可用功能清單、Bearer Token
- **後置條件**：使用者於主頁可見並可點選有授權的功能；無授權項目以 disable 樣式或不顯示

## 對應 RQ

| 來源 | 條目 | 對應方式 |
|------|------|---------|
| RQSS011 | SS 管理者可設定角色↔功能對應表（哪些角色可使用哪些功能）| 沿用 SS 端對應，DM 端僅消費登入時取得之 functions |
| RQSS013 | 系統需提供登入認證 API，輸出 Token + 角色 + 可用功能清單 | DM 於登入時一次取得 functions，主頁依此渲染 |
| RQSS009 | 一個使用者可指派多個角色 | functions 為角色聯集（SS 計算後回傳） |

> 註：本 UC 為實作 SS 端 RBAC 結果於 DM 主頁的具體流程；DM 自身不維護角色↔功能對應表。

## 正常流程

1. UCDM004 登入完成後重導 DM 主頁
2. **DM 後端讀取 session 中的 functions（由 SS 於登入時計算並回傳）**

   - 任一 SS 角色視為一般使用者；DM 各功能（DM01 / DM02 / DM05）是否可用，由 SS 端「角色↔功能對應」決定
   - SOP_REVIEWER 是 UCDM006 內的**硬卡點**（核准 / 退件動作層級檢查），**不影響功能選單顯示**

   > 角色簡化（2026-04-27 / 2026-04-28 更新）：原 SOP_AUTHOR / SOP_READER 名稱廢除；只剩 SOP_REVIEWER 與「一般使用者」二分。SS 角色於 SS 模組獨立管理。

3. **DM 主頁顯示功能選單**（依 functions 結果 Enable / Disable）：
   - 在 functions 中：可點選
   - 不在 functions 中：disable 樣式（灰階）或不顯示
4. **使用者選功能** → 觸發對應 UC：
   - DM01 → [UCDM001-文件管理與版本管控](UCDM001-文件管理與版本管控.md)
   - DM02 → [UCDM002-線上文件查閱](UCDM002-線上文件查閱.md) / [UCDM003-SOP 文件查閱](UCDM003-SOP文件查閱.md)
   - DM05 → [UCDM006-文件審查作業流程](UCDM006-文件審查作業流程.md)
   - 其他未來功能類推

## 替代流程

- **2a**. functions 為空（角色尚無任何功能對應）→ 主頁顯示「您目前無可用功能，請洽資訊人員」
- **2b**. session 過期或 Token 失效（APISS002 回 401）→ 重導登入頁（觸發 UCDM004 重新登入）

## 設計要點

- 權限粒度到「**功能選單**」層級
- 角色 → 功能對應由 **SS 模組**（UCSS004）維護，DM 端只消費登入時 SS 回傳之 functions
- 主頁不快取角色與 functions；每次登入重新取（避免 SS 端角色 / 對應變動後 DM 仍用舊資料）
- DM 端 functions cache 僅限本次 session 內使用，登出或 Token 失效即釋放

## 流程圖

![](UCDM005-DM%20主頁與功能選單載入.png)
