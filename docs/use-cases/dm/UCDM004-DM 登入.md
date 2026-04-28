# UCDM004-DM 登入

使用者於 **DM 系統獨立登入頁**輸入 SS 帳密進行身分驗證；DM 透過 SS API（APISS001）認證後取得 Bearer Token 與使用者資訊（含角色與可用功能清單）。**不啟用 MFA**。

> **2026-04-28 變更**：認證來源由主系統 DP API 改為獨立的 **SS 模組**（APISS001 / APISS002）。SS 使用者為一般軍人，與主系統 DP 帳密**完全切開**。

- **主要參與者**：使用者（任一 SS 角色；DM 角色簡化後只硬卡 SOP_REVIEWER 於 UCDM006 核准 / 退件動作層級）
- **次要參與者**：SS 模組（提供認證 API APISS001 / Token 驗證 API APISS002）
- **對應功能選項**：DM03-登入頁
- **前置條件**：
  - 使用者於 SS 端已有有效帳號（未停用、未鎖定）
  - DM 服務啟動完畢、SS API 可達
- **後置條件**：
  - 使用者已通過身分驗證，瀏覽器持有 DM session 與 SS Token
  - `DM_AUDIT` 寫入登入紀錄；SS 端同步寫入 SS 登入歷程

## 對應 RQ

| 來源 | 條目 | 對應方式 |
|------|------|---------|
| RQSS013 | 系統需提供登入認證 API 供 ET / DM 模組呼叫，輸入帳密、輸出 Token + 角色 + 可用功能清單 | 直接呼叫 APISS001 |
| RQSS014 | 系統需提供 Token 驗證 API 供 ET / DM 模組於每次請求時呼叫 | 直接呼叫 APISS002（後續每次請求）|
| RQSS015 | Token 採用具時效之憑證機制 | 沿用 SS 簽發之 Token |
| RQSS018 | 登入操作歷程記錄 | SS 端寫 SS_LOGIN_LOG，DM 端寫 DM_AUDIT |

> 註：本 UC 為呼叫 SS 認證流程於 DM 端的具體實作，**不啟用 MFA**（DM 主要為文件查閱，敏感度較低）。

## 正常流程

1. 使用者開啟 DM 系統 URL（如 `https://dm.tbms.internal/login`）→ DM 顯示登入頁（**DM03**）
2. 使用者**輸入 SS 帳號 / 密碼**，按「登入」
3. **DM 後端呼叫 SS 認證 API（APISS001）** 帶帳密
4. SS 驗證帳密、查角色與可用功能；驗證成功則回傳 `{ token, expires_in, user: { account, name, roles, functions } }`
5. **DM 寫 session 與稽核軌跡**：Token + user info 寫入瀏覽器 session（HTTP-only cookie 或 SameSite cookie）；同步寫 DM_AUDIT
6. 重導使用者至 DM 主頁 → 觸發 [UCDM005-DM 主頁與功能選單載入](UCDM005-DM%20主頁與功能選單載入.md)

## 替代流程

- **4a**. 帳密錯誤 → SS 回 401（INVALID_CREDENTIAL）→ DM 顯示「帳號或密碼錯誤」（不顯示細節避免帳號列舉）；SS 累計失敗達 `SS_LOCK_THRESHOLD` 自動鎖定
- **4b**. 帳號鎖定 / 停用 → SS 回 403（ACCOUNT_LOCKED / ACCOUNT_DISABLED）→ DM 顯示「帳號暫時無法登入，請洽資訊人員」
- **4c**. 首次登入 / 密碼到期 → SS 回 426（PASSWORD_CHANGE_REQUIRED）→ DM 導向 SS 變更密碼頁（UCSS002）
- **4d**. SS API 無法存取（網路 / 服務異常）→ DM 顯示「認證服務暫時不可用」+ 進入只讀模式（公開分類仍可瀏覽）
- **5a**. Session 逾時或 Token 過期，下一次請求 APISS002 驗證即被拒，自動導回登入頁

## 設計要點

- **不啟用 MFA**：DM 主要為文件查閱，敏感度較低
- 認證走 SS API（APISS001 / APISS002），DM 不維護獨立帳號表，亦不從 DP 同步
- Token 過期後使用者重新登入；DM 不主動 refresh Token
- 登入失敗連續 N 次由 **SS** 觸發鎖定機制（`SS_LOCK_THRESHOLD`，預設 5 次）

## 流程圖

![](UCDM004-DM%20登入.png)
