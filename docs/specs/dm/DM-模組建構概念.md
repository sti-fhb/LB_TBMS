# DM 模組建構概念

本文件說明**文件管理模組（DM）**的定位、架構、與 TSBMS 主系統及 Moodle 的整合邊界，以及 SD（System Design）階段的進行建議。

---

## 1. 模組定位與目標

### 1.1 模組在系統中的角色

DM（Document Management）模組提供 **SOP 文件、操作手冊、訓練教材、表單**等檔案的**集中版本控管、電子簽核、發布通知**，並對外（主系統、Moodle、郵件）提供穩定的查閱介面。

### 1.2 核心目標

1. **版本可追溯**：每份文件皆有明確版本號、變更摘要、歷程可回溯／還原
2. **受控發布**：文件需通過簽核（單層或會簽）才對一般使用者可見，避免未經審核的文件外流
3. **稽核合規**：所有簽核動作、查閱紀錄均寫入不可竄改的稽核軌跡
4. **整合易用**：主系統各畫面可一鍵開啟對應線上操作手冊；Moodle 教材可超連結至 SOP

### 1.3 為何獨立於主系統

- **業務邊界清楚**：文件管理是非業務流程資料，與血液處理主流程解耦
- **部署彈性**：可獨立升版、獨立擴容，不牽動主系統
- **權責分離**：文件簽核角色（SOP_AUTHOR / SOP_REVIEWER）與業務角色（護理師、技術師）獨立管理
- **技術一致**：採主系統相同技術棧（FastAPI + React），團隊技能重用、維運一致

### 1.4 模組歷史

- **初期**：獨立模組 DM
- **2026-03-25**：併入 ET（認為與 SOP/教材版本管理重疊）
- **2026-04-24**：重新獨立 — 因評估 Moodle 原生（Wiki / Book / Database activity）無法滿足版本+多階簽核+狀態機需求；改採主系統技術棧自建

---

## 2. 需求來源

- RFP §2.8.1 文件管理 → RQDM001
- RFP §1.7 文件管理與教育訓練 → RQDM002 (版本)、RQDM003 (與 ET 整合)、RQDM004 (線上操作手冊)
- 詳細需求：[../../requirements/RQDM.md](../../requirements/RQDM.md)

---

## 3. 技術棧與部署架構

### 3.1 建議技術選型

| 面向 | 建議 | 理由 |
|------|------|------|
| 後端 | FastAPI（Python 3.11+）| 與 TSBMS 主系統一致 |
| 前端 | React + Vite + TypeScript | 與 TSBMS 主系統一致 |
| DB | PostgreSQL 13+ | 與 TSBMS 主系統一致 |
| 檔案儲存 | 本地磁碟起步；擴充時評估 S3 相容儲存 | — |
| 容器化 | Docker / Docker Compose | 維運一致 |
| 認證 | 透過 DP API 換取 Token（無獨立帳號表）| 單一 IdP |

### 3.2 部署拓撲

- **獨立服務**：DM 後端與前端獨立部署（可同 repo 不同 service，或獨立 repo）
- **網路**：與主系統後端同網段（或 service mesh），可直連 DP API
- **對外 URL**：單一入口（如 `https://dm.tbms.internal/`）供 Moodle、主系統、使用者瀏覽器連入

---

## 4. 整合邊界

### 4.1 架構圖

```
┌────────────────────────┐   ┌──────────────────────┐
│   TSBMS 主系統          │   │   Moodle LMS          │
│   (BC/CP/TL/BS/MA/LB)  │   │   (課程 / 測驗)        │
│                        │   │                       │
│   DP (帳號 / 角色)     │◄──┤   教材內提及 SOP/手冊 │
└──────────┬─────────────┘   │   → 超連結 DM         │
           │ SSO              └──────────┬───────────┘
           │ (DP API + Token)            │ URL
           ▼                             │
┌─────────────────────────────────────────────────────┐
│                DM 模組（獨立服務）                   │
│                                                     │
│   FastAPI 後端                  React 前端           │
│   ┌──────────────┐             ┌─────────────┐    │
│   │ 文件版本管控  │             │ 文件瀏覽器  │     │
│   │ 簽核流程     │             │ 上傳介面    │     │
│   │ 稽核軌跡     │             │ 簽核頁面    │     │
│   │ 通知發送     │             │ 版本歷程    │     │
│   │ 線上操作手冊 │             └─────────────┘    │
│   └──────────────┘                                 │
│         │                                          │
│         ▼ PostgreSQL                               │
│   ┌──────────────┐                                 │
│   │ DM_DOC       │ DM_DOC_VERSION                  │
│   │ DM_APPROVAL  │ DM_AUDIT                        │
│   │ DM_CATEGORY  │ DM_SUBSCRIPTION                 │
│   └──────────────┘                                 │
│         │                                          │
│         ▼ 檔案儲存                                  │
│   ┌──────────────┐                                 │
│   │ /data/dm/    │ (PDF / Word / 圖檔)             │
│   └──────────────┘                                 │
└─────────────────────────────────────────────────────┘
     ▲                          │
     │ 查 User / 寫 Audit       │ 通知
     │                          ▼
┌──────────┐              ┌──────────┐
│ DP API   │              │ SMTP /   │
│          │              │ 通知中心 │
└──────────┘              └──────────┘
```

### 4.2 整合接點

| # | 接點 | 方向 | 技術 |
|---|------|------|------|
| **1** | DM 認證 | DM → DP | 呼叫 APIDPxxx（方案 B 同構）以 TSBMS 帳密換 Token |
| **2** | User 資料查詢 | DM → DP | 查使用者 sopRole、站點、姓名等 |
| **3** | 稽核 Log | DM → DP | 呼叫 SRVDP003（操作歷程記錄服務）寫入 DP_AUDIT |
| **4** | 主系統 → 線上操作手冊 | 主系統 → DM | 各畫面以 func_name call DM API 開啟手冊 |
| **5** | Moodle → SOP / 手冊 | Moodle → DM | 教材內 HTML 超連結指向 `https://dm.tbms.internal/doc/{DOC_ID}` |
| **6** | 通知發送 | DM → 外部 | SMTP（DM 自有）或主系統通知中心 |

### 4.3 明確不做的事

- ❌ DM 不維護自己的使用者帳號表（完全依賴 DP）
- ❌ DM 不直接讀主系統業務 DB（如捐血人、血品）
- ❌ 主系統不直接讀 DM 的 DB（所有讀取走 DM API）
- ❌ Moodle 不直接讀 DM 的 DB（只透過 URL 超連結 + SSO session）

---

## 5. SD 階段進行建議

### 5.1 建議的進行順序

```
階段 1：DM 最小可用版（MVP）
  ├─ FastAPI 骨架 + React 骨架
  ├─ DB schema（DM_DOC / DM_DOC_VERSION / DM_CATEGORY）
  ├─ DP 認證整合（APIDPxxx）
  ├─ 文件上傳 / 下載 / 版本列表
  └─ 最小文件瀏覽 UI

階段 2：簽核流程
  ├─ DM_APPROVAL 表
  ├─ 狀態機（草稿 → 送審中 → 已核准 / 已退件）
  ├─ 角色權限（AUTHOR / REVIEWER / READER）
  └─ 簽核頁面 UI

階段 3：稽核與通知
  ├─ DM_AUDIT 表 + 寫入 DP 稽核軌跡
  ├─ Email / 主系統通知整合
  └─ DM_SUBSCRIPTION 訂閱機制

階段 4：線上操作手冊
  ├─ APIDM002 (by func_name)
  ├─ 手冊頁面樣板
  └─ 主系統各模組埋入呼叫點

階段 5：Moodle 整合
  ├─ 確認 DM URL 格式穩定（DOC_ID）
  ├─ 協助 Moodle 教材編輯者加超連結
  └─ 跨站 SSO session 驗證

階段 6：測試 / 上線
  ├─ 驗收版本控管、簽核流程、稽核軌跡
  └─ 文件管理人員培訓
```

### 5.2 SD 決策檢核清單

| 項目 | 決策點 |
|------|--------|
| DM 與主系統是否同 repo | 同 monorepo 還是獨立 repo？影響 CI/CD 與版控策略 |
| 檔案儲存位置 | 本地 `/data/dm/` 起步，S3 之類何時導入？ |
| 版本號規則 | 語意版本（v1.0 / v2.0）或流水（rev 1 / 2 / 3）？依分類可配置？ |
| 簽核流程彈性 | 固定單層還是可配置多階會簽？ |
| 線上操作手冊觸發 | 主系統各畫面的觸發方式：新頁開啟 / 側邊欄 / 浮動視窗？|
| Moodle 超連結驗證 | 教材維護者如何取得正確 DOC_ID？是否提供「插入 DM 連結」UI 輔助？|

---

## 6. API / SRV 契約建議（MVP 最小接口）

> 以下為下週討論草案，實際編號待正式確認後 rename。

### 6.1 DM → DP（認證／資料／稽核）

| 編號（暫定）| 方向 | 用途 | 備註 |
|---|---|---|---|
| APIDPxxx | DM → DP | 以 TSBMS 帳密換取 Token + user info（含 sopRole）| 同 Moodle 方案 B，建議與 Moodle 共用一支 |
| APIDPyyy | DM → DP | 驗 Token 仍有效 | 同 Moodle 方案 B |
| SRVDP003 | DM → DP | 寫入 Audit Log（既有服務）| 現成 |

### 6.2 主系統 → DM（線上操作手冊 + 文件查詢）

| 編號 | 方向 | HTTP | 用途 |
|------|------|------|------|
| **APIDM001** | 主系統 / Moodle → DM | `GET /api/dm/manual?func_name=XXX` | 依 func_name 取對應線上操作手冊 URL 或 HTML，回 `{ doc_id, url, title, version }`；無對應回 404 |
| **APIDM002** | 主系統 / Moodle → DM | `GET /api/dm/doc/{DOC_ID}` | 依 DOC_ID 取文件 metadata + URL；回 `{ title, version, published_at, url, download_url }` |
| **APIDM003** | 主系統 → DM | `GET /api/dm/docs?category=XXX&q=關鍵字` | 搜尋文件清單（可選）|

### 6.3 DM 內部作業 API（資訊人員用）

| 編號 | 方向 | HTTP | 用途 |
|------|------|------|------|
| APIDM101 | DM 前端 → DM 後端 | `POST /api/dm/docs` | 新增文件 / 上傳版本 |
| APIDM102 | DM 前端 → DM 後端 | `POST /api/dm/docs/{DOC_ID}/submit` | 送審 |
| APIDM103 | DM 前端 → DM 後端 | `POST /api/dm/docs/{DOC_ID}/approve` | 核准 |
| APIDM104 | DM 前端 → DM 後端 | `POST /api/dm/docs/{DOC_ID}/reject` | 退件 |
| APIDM105 | DM 前端 → DM 後端 | `GET /api/dm/docs/{DOC_ID}/versions` | 版本清單 |
| APIDM106 | DM 前端 → DM 後端 | `GET /api/dm/docs/{DOC_ID}/audit` | 稽核軌跡 |

### 6.4 URL 慣例（給 Moodle / 主系統連結用）

| URL | 用途 |
|-----|------|
| `https://dm.tbms.internal/doc/{DOC_ID}` | 文件瀏覽頁（含版本、下載按鈕）|
| `https://dm.tbms.internal/manual?func={func_name}` | 線上操作手冊（主系統呼叫或教材連結）|
| `https://dm.tbms.internal/category/{CAT_ID}` | 分類清單頁 |
| `https://dm.tbms.internal/search?q=XXX` | 搜尋頁 |

### 6.5 MVP 必要接口（最小上線）

- **APIDPxxx** （認證）
- **APIDM001** （線上操作手冊 by func_name）
- **APIDM002** （文件查詢 by DOC_ID）
- **URL: /doc/{DOC_ID}** （Moodle 連結入口）
- **URL: /manual?func={func_name}** （主系統入口）

其他（簽核、稽核 API）可在 Phase 2 再上。

---

## 7. 延伸閱讀

- **需求清單**：[../../requirements/RQDM.md](../../requirements/RQDM.md)
- **UseCase 清單**：[../../use-cases/dm/](../../use-cases/dm/)
- **認證方案**：[../dp/Moodle認證整合-方案比較.md](../dp/Moodle認證整合-方案比較.md)（方案 B 同樣適用 DM）
- **ET 模組（教育訓練）**：[../et/ET-模組建構概念.md](../et/ET-模組建構概念.md)
