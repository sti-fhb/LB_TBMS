# Moodle 認證整合方案比較

**文件狀態**：**草稿（待 SD 討論）**
**討論目的**：與 SD 決定 Moodle 與 DP 模組的認證整合方案（A / B 擇一）

---

## 背景與需求

- 使用者在 TSBMS 登入後需進入 Moodle 查閱 SOP 文件、操作手冊、上課
- 使用者帳密統一由 **DP 模組**管理，Moodle 不另維護帳號
- Moodle 簽核角色（SOP_REVIEWER / SOP_AUTHOR / SOP_READER）由 DP 發放，透過登入流程帶入
- **Moodle 不要求 MFA**（MFA 在 TSBMS 主站登入時已處理一次，Moodle 本身視為延伸信任）
- 不做多層審核（見「電子簽核」設計，狀態機只有草稿 → 已核准）

---

## 方案 A：OIDC（OpenID Connect，SSO）

### 架構流程

```
1. User 開 Moodle URL
2. Moodle 偵測未登入 → redirect 到 DP /oidc/authorize
3. 若 User 已登過 TSBMS（DP session 存在）→ silent login（不顯示頁面）
   否則 DP 顯示登入頁 → User 輸入 TSBMS 帳密（免 MFA）
4. DP 驗證通過 → 回 authorization code → redirect 回 Moodle
5. Moodle 以 code 向 DP /oidc/token 換取 id_token + access_token
6. Moodle 解析 id_token 取得 username、sopRole 等 claims
7. Moodle 建 session，upsert 本地 user + 指派對應 Moodle role
8. User 進入 Moodle 首頁
```

### DP 要做

| 項目 | 說明 |
|------|------|
| 架 OIDC Provider | 實作三個 endpoint：`/oidc/authorize`、`/oidc/token`、`/oidc/userinfo` |
| 註冊 Moodle Client | 管理介面新增 OIDC Client：`client_id=moodle`、`client_secret`、`redirect_uri`、`require_mfa=false` |
| id_token Claims | `sub`（username）、`email`、`name`、`sopRole`、`site` 等 |
| Session 整合 | 若 User 已有 TSBMS session → silent 回應；否則顯示 DP 登入頁 |

### Moodle 要做（一次性設定，不寫 code）

| 項目 | 值 |
|------|----|
| 裝 Plugin | 官方 `auth_oidc`（Moodle Plugin Directory 可下載） |
| Site admin → Plugins → Authentication → OIDC | 填入 Client ID / Secret / Authorize / Token / UserInfo URL |
| Attribute mapping | `sub`→username、`email`→email、`sopRole`→`profile_field_sopRole` |
| 停用其他認證方式 | 除 admin 緊急登入外一律走 OIDC |

### 免 MFA 的實作方式

MFA 決定權在 **DP（IdP）端**，不在 Moodle：

```
DP 登入邏輯：
  if (client_id == 'moodle' && require_mfa == false) {
      驗帳密通過即發 token，不走 MFA 層
  } else {
      正常流程：帳密 → MFA → 發 token
  }
```

TSBMS 其他敏感操作（如捐血者資料）仍走 MFA，Moodle 單獨免 MFA。

---

## 方案 B：Custom API（DP 提供 REST API，Moodle 寫 Plugin 接）

### 架構流程

```
1. User 開 Moodle URL
2. Moodle 顯示 Moodle 登入頁
3. User 輸入 TSBMS 帳密 submit
4. Moodle custom auth plugin 攔截 → POST APIDP001
5. DP 驗證（免 MFA）→ 回 token + user info
6. Plugin 本地 upsert user 記錄、存 token 到 Moodle session
7. User 進入 Moodle 首頁
8. 使用期間：Moodle 定期呼叫 APIDP0XX 驗 token 仍有效；401 時強制 logout
```

### DP 要做

**APIDP001 — 登入驗證**
```http
POST /api/dp/auth/login
Body:
  { "username": "alvin", "password": "xxx" }
Response 200:
  {
    "token": "eyJhbGc...",          # Bearer token
    "expires_in": 3600,
    "user": {
      "username": "alvin",
      "email": "alvin@sti.com.tw",
      "name": "謝明均",
      "sopRole": "SOP_AUTHOR",      # SOP_REVIEWER / SOP_AUTHOR / SOP_READER
      "site": "TSGH"
    }
  }
Response 401:
  { "error": "invalid_credentials" }
```

**APIDP0XX — 驗證 Token 仍有效**
```http
POST /api/dp/auth/verify
Header: Authorization: Bearer {token}
Response 200: { "user": { ... }, "expires_in": 2800 }
Response 401: { "error": "token_invalid_or_expired" }
```

### Moodle 要做

- 寫 custom auth plugin（約 200 行 PHP），放 `auth/tsbms/`
- Plugin 攔截登入 submit → 呼叫 APIDP001
- Session 存 token，後續 request hook 呼叫 APIDP0XX 驗證
- Token 過期時強制 logout

### 免 MFA 的實作方式

API 層級直接定義：APIDP001 這支 API 設計為「免 MFA 驗帳密」路徑，DP 內部判 `client=moodle` 時跳過 MFA。

---

## 比較總表

| 面向 | 方案 A（OIDC） | 方案 B（Custom API） |
|------|---------------|---------------------|
| **協定標準** | 業界標準（RFC 6749 / OpenID Connect Core） | 自訂 REST API |
| **DP 實作成本** | 高：要架完整 OIDC Provider（authorize / token / userinfo + 規範符合） | 中：2 支 REST API，設計自由 |
| **Moodle 實作成本** | 低：裝官方 `auth_oidc` plugin + 設定 | 中：寫 ~200 行 PHP custom plugin |
| **User 體驗** | **Silent SSO** — 登過 TSBMS 後點 Moodle 不需再登入 | **Moodle 重新登入** — 雖然同帳密但要再輸入一次 |
| **登入頁位置** | DP 的統一登入頁 | Moodle 的登入頁 |
| **安全責任** | 協定與 plugin 已處理大部分（token 簽章、nonce、state） | 自己把關（HTTPS、rate limit、brute force、token revoke） |
| **跨模組重用** | 多裝 OIDC client 即可 | 其他模組也能用這兩支 API |
| **審計 / 合規** | 業界標準有利於後續稽核 | 自訂方式需額外說明 |
| **維護性** | 隨 OIDC 規範演進，有 Plugin 社群支援 | 完全由專案團隊維護 |
| **適用情境** | 新建或現代化、有條件架 IdP | 既有 DP token 生態、時程緊、團隊不熟 OIDC |

---

## 建議

**主觀建議：方案 A（OIDC）**，理由：

1. **標準協定利於長期維護** — 後續多系統（主系統、報表、看板、其他 LMS）都可接入同一 IdP
2. **Silent SSO 體驗好** — User 在 TSBMS 登入後瀏覽 Moodle 不再被打斷
3. **安全性由協定保證** — 減少自寫 auth 的風險（token replay、CSRF、nonce 等）
4. **Moodle 端極簡** — 只裝官方 plugin + 填設定，無需自寫 PHP

**採方案 B 的條件**：

- DP 已有成熟的 token/API 生態，其他模組都這樣溝通，想維持一致性
- OIDC Provider 架設工時無法在時程內消化
- Moodle 登入頁重登一次可接受

---

## 待 SD 確認的問題

| # | 問題 | 影響 |
|---|------|------|
| 1 | DP 目前是否已有 OIDC/SAML IdP 基礎建設？ | 若有 → 方案 A 成本大降 |
| 2 | MFA 是否真的可以對 Moodle 完全免除？有無資安／軍方法規限制？ | 若不可免 → 兩方案都需加上 MFA 流程 |
| 3 | 使用者體驗要求：silent SSO 還是可接受 Moodle 登入頁？ | 決定方案 A/B |
| 4 | TSBMS 整體是否規劃統一 token 生態（其他模組之間也 API 相通）？ | 傾向方案 B 則統一整個生態 |
| 5 | 時程：OIDC Provider 架設工時估算 vs Custom API 工時估算 | 決定哪個可行 |
| 6 | Moodle 日後若要接其他內部系統（如看板），是否也要共用同一認證？ | 方案 A 擴充性較佳 |
| 7 | 審計要求：是否有稽核單位要求用業界標準協定？ | 若有 → 方案 A |

---

## 其他備選（僅供比較，本次不討論）

| 方案 | 狀態 |
|------|------|
| SAML 2.0 | 跟 OIDC 同等級，若軍方已有 SAML IdP 可改採，本案 Moodle 也支援（`auth_saml2` plugin） |
| LDAP / AD 直連 | 若 DP 底層是 AD，Moodle 可 `auth_ldap` 直接驗證，但無 silent SSO |

---

## 共同設定（兩方案都需要）

不論走哪一案，Moodle 端以下項目都要做：

- 在 Moodle 建 Course「SOP 文件庫」，Section 分「草稿」「正式公告」
- 三個 Moodle 系統角色對應 DP 的 SOP 角色：
  - `SOP_REVIEWER` → Moodle Manager
  - `SOP_AUTHOR` → Moodle Teacher
  - `SOP_READER` → Moodle Student（或 authenticated user）
- `profile_field_sopRole` 自訂 user profile field 用來存 DP 帶來的角色 code
- Role auto-assignment 設定：依 `profile_field_sopRole` 值自動套 Moodle 系統角色

---

## 相關文件

- [ET-模組建構概念](../et/ET-模組建構概念.md)
- [線上操作手冊整合設計（主專案 DP）](../../../../TBMS/docs/specs/dp/線上操作手冊整合設計.md)
- [RQET.md — RQET009 維護 SOP 文件與版本](../../requirements/RQET.md)
