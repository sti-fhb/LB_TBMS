# Feature Specification: 教育訓練模組（Education & Training）

**Created**: 2026-04-28（重構，對齊 BC / TL 拆法 — spec.md 薄殼 + spec_usX.md 各 US 細節）
**Status**: Draft
**Input**: 依據 requirements/RQET.md 產出教育訓練模組功能規格

---

## 模組概觀

教育訓練模組（ET）為 TSBMS 的**周邊支援系統**，提供血液中心內部人員與一般軍人之**線上學習平台**。本案以 **Moodle 4.x LTS** 為核心，搭配獨立 **SS 模組**做身分認證、**DM 模組**做文件型教材版本管控。

### 核心定位

- **平台**：Moodle LMS（開源、4.x LTS）
- **使用者群**：一般軍人（透過 SS 認證；與主系統 DP 帳密**完全切開**）
- **教材分流（2026-04-27）**：影片型教材由 ET 自管（保留強制觀看追蹤）；文件型教材（PDF / PPT / 圖文）改放 DM 享版本管控
- **不做**：不在 ET 重建學習功能、不客製 Moodle 核心、不把 Moodle 資料同步回 TSBMS DB、不用捐血者資料做學員基礎

### 操作角色

| 角色 | 職責範圍 |
|------|----------|
| 管理者（講師） | 建立課程、上傳教材、編排章節、建立測驗、邀請學員、檢視學習報表 |
| 學員 | 加入課程、學習教材內容、進行線上測驗、查看個人學習進度 |
| eMail Server | 外部郵件系統，負責寄發課程邀請碼通知信 |
| SS 模組 | 提供登入認證（APISS001）與 Token 驗證（APISS002）|
| DM 模組 | 提供文件型教材之版本管控與固定 URL，ET 課程章節以連結引用 |

### RQ → UC 對應總覽

![RQET ⇄ UCET 對應](RQET-UCET-對應.png)

> 圖示為 RQET001~008 條目與 UCET001~010 / UCET013 之 Realisation 對應；文件型教材（RQET010）併入 UCET002 文件型分支處理。

---

## Clarifications

### Session 2026-04-28（ET 重構：對齊 BC / TL 拆法）

- Q: spec.md 為何瘦身、移除 FR-XXX 條列？ → A: 對齊 SA 工作區 BC / TL 慣例 — 主規格薄殼，US 細節（含 Acceptance Scenarios，等同各 FR 行為）拆到各 spec_usX.md。FR-XXX 與 Acceptance Scenarios 大量重疊，BC / TL 模式以 Acceptance Scenarios 為唯一正式行為要求，避免雙軌。

### Session 2026-04-28（認證改走 SS）

- Q: ET 認證為何不再走 DP？ → A: SS 使用者為一般軍人，與主系統 DP 內部人員完全分流。SS 為獨立認證系統，與 DP **完全切開**（獨立 DB、不同步、不共用使用者 ID 命名空間）。Moodle 透過 `auth/tsbms/` custom plugin 呼叫 SS 之 APISS001 / APISS002。
- Q: Moodle 系統角色（Manager / Teacher / Student）對應 SS 哪些角色？ → A: 由 plugin 設定中維護對應規則；SS 端 roles 由 SS 管理者於後台設定。

### Session 2026-04-27（教材分流）

- Q: 影片 vs 文件型教材如何分工？ → A: 影片型教材直接由 ET 自管（保留 RQET004「強制觀看完影片才能進下一章節」的進度追蹤能力）；文件型教材（PDF / PPT / 圖文）改放 DM 享版本管控，ET 課程章節以連結引用 DM 固定 URL（`https://dm.tbms.internal/doc/{DOC_ID}`）。
- Q: DM 教材撤回後 ET 引用連結怎麼辦？ → A: DM 端 STATUS=WITHDRAWN 時 URL 回 410 Gone；Phase 2 補 webhook 通知 ET 課程編輯者死鏈。

### Session 2026-04-24（DM 拆出獨立）

- Q: SOP / 文件管理為何拆出 ET？ → A: Moodle 原生 Wiki / Book / Database activity 無法滿足「版本歷程 + 多階簽核 + 狀態機」三項硬性需求，改為獨立 DM 模組，採主系統技術棧（FastAPI + React）自建。

---

## User Stories

| Story | UC 編號 | 名稱 | 優先級 | 子檔 |
|-------|---------|------|--------|------|
| 1 | UCET013 | 登入線上學習平台（SS） | P1 | [spec_us1.md](spec_us1.md) |
| 2 | UCET001 | 建立與編輯課程 | P1 | [spec_us2.md](spec_us2.md) |
| 3 | UCET002 | 上傳教材（影片 / 引用 DM 文件） | P1 | [spec_us3.md](spec_us3.md) |
| 4 | UCET003 | 編排課程章節與進度條件 | P1 | [spec_us4.md](spec_us4.md) |
| 5 | UCET004 | 建立線上測驗 | P2 | [spec_us5.md](spec_us5.md) |
| 6 | UCET005 | 邀請學員加入課程 | P2 | [spec_us6.md](spec_us6.md) |
| 7 | UCET006 | 檢視學習報表與完課率 | P2 | [spec_us7.md](spec_us7.md) |
| 8 | UCET007 | 加入課程（學員） | P1 | [spec_us8.md](spec_us8.md) |
| 9 | UCET008 | 學習課程內容 | P1 | [spec_us9.md](spec_us9.md) |
| 10 | UCET009 | 進行線上測驗（學員） | P2 | [spec_us10.md](spec_us10.md) |
| 11 | UCET010 | 查看個人學習進度 | P3 | [spec_us11.md](spec_us11.md) |

> 所有 Story 共用 [§操作角色](#操作角色) / [§Cross-Module Dependencies](#cross-module-dependencies) / [§Configurable Parameters](#configurable-parameters) / [§Edge Cases](#edge-cases) / [§Assumptions](#assumptions) / [§邊界](#與其他模組之邊界) / [§Key Entities](#key-entities)。

---

## Edge Cases

- 同時多裝置登入時 Moodle session 是否互踢、SS Token 是否共用
- 學員觀看影片中途網路中斷，已觀看時長之記錄是否完整
- 課程教材引用 DM 文件後，DM 文件被撤回（STATUS=WITHDRAWN）期間學員點連結之回應（Phase 1 由 410 Gone 通知）
- 測驗作答途中關閉瀏覽器，是否視為已提交或可恢復
- 管理者刪除課程時，已加入學員之既有進度與成績如何處置
- SS 端帳號停用 / 角色變更後，Moodle 端 session 何時實際失效（依 APISS002 驗證週期）
- 大量學員同時於指定時點開課（如全營必修）對 Moodle 與 SS 之負載

---

## Key Entities

- **課程（Course）**: 名稱、描述、分類、封面圖、開課日期、狀態 — 由 Moodle 原生資料模型管理
- **章節（Section / Activity）**: 順序、強制完成條件、所屬課程 — 由 Moodle 原生資料模型管理
- **影片教材（Video Resource）**: 檔案、播放進度 — 由 Moodle 自管
- **文件型教材引用（External Link）**: DM URL、所屬章節 — 引用 DM 之 DOC_ID
- **測驗（Quiz）**: 名稱、及格分數、作答時間、重考次數、所屬章節 — 由 Moodle 原生資料模型管理
- **學習進度（Learning Progress）**: 學員、章節、完成度、影片播放時長、測驗成績 — 由 Moodle 自管
- **邀請（Enrolment）**: 課程、學員、邀請碼、有效期、狀態 — 由 Moodle Plugin 擴充

> **不擁有的資料**：使用者帳號（屬 SS 模組）、文件型教材本體（屬 DM 模組）。

---

## Success Criteria

- **SC-001**: 一般使用者於 Moodle 登入頁輸入 SS 帳密至進入首頁完成（含 APISS001 呼叫）回應時間不超過 2 秒
- **SC-002**: 管理者於 1 分鐘內可完成單一課程之基本資料建立 + 上傳一段影片教材
- **SC-003**: 學員觀看影片進度記錄精確到秒，強制完成判斷誤差不超過 1 秒
- **SC-004**: 線上測驗自動閱卷時間不超過 3 秒（每題 100 題以下）
- **SC-005**: DM 文件型教材更版後，ET 課程章節之引用連結於下一次學員點選即指向最新版（無需 ET 介入）
- **SC-006**: 完課率報表計算回應時間不超過 5 秒（單一課程 1000 學員以下）
- **SC-007**: SS 端角色 / 功能對應異動後，Moodle 使用者下一次登入即生效

---

## Assumptions

- ET 平台採 Moodle 4.x LTS，部署採 Docker Compose（開發）/ Kubernetes（生產），DB 採 PostgreSQL
- Moodle 與 TSBMS 主系統同網段或經 service mesh 直連，與 SS 模組以 RESTful API 整合
- `auth/tsbms/` custom plugin 為本案客製產出，安裝於 Moodle `/local/auth/tsbms/`，由開發團隊維護
- 學員為一般軍人，於 SS 模組由業務單位手動建立帳號 / 指派角色，不從捐血者資料 / TSBMS DP 自動建立
- 影片型教材檔案儲存於 Moodle 預設磁碟區（起步），擴充時評估 S3 相容儲存
- 文件型教材一律走 DM 引用，ET 端不保存 PDF / PPT / 圖文之實體檔案
- 邀請信寄發採用 Moodle 原生 SMTP 整合，與 TSBMS 通知中心無關
- 課程教材中引用之 DM URL 採固定格式 `https://dm.tbms.internal/doc/{DOC_ID}`，DM 端保證最新版指向穩定

---

## Cross-Module Dependencies

| Direction | Module | 編碼 | Purpose |
|-----------|--------|------|---------|
| ET → SS | 單一登入模組（SS） | APISS001 | Moodle 登入時透過 auth/tsbms plugin 取 Token + 角色 + 可用功能 |
| ET → SS | 單一登入模組（SS） | APISS002 | Moodle 後續每次請求驗證 Token |
| ET → DM | 文件管理模組（DM） | URL 引用 | 課程章節引用 DM 文件型教材固定 URL，享 DM 版本管控 |
| ET → 外部 | eMail Server（SMTP） | — | 課程邀請信寄發 |
| SS ← ET | 單一登入模組（SS） | — | ET 提供功能清單給 SS 管理者於後台維護（手動，無 API）|

> **不涉入**：ET 與主系統 DP 之間**不**做身分認證整合（2026-04-28 起改走 SS，不再走 DP）。

---

## Configurable Parameters

| 參數 | 說明 | 預設值 |
|------|------|--------|
| Moodle 上傳檔案大小限制 | 影片教材上傳最大容量 | 依 Moodle 站台設定 |
| 課程測驗重考次數 | 未及格時允許重考次數 | 依課程設定 |
| 邀請碼有效期 | 課程邀請碼的有效天數 | 依課程設定 |
| SS 端點與認證金鑰 | APISS001 / APISS002 endpoint + API Key 或 mTLS 憑證 | 部署時設定 |
| DM 教材 URL 前綴 | DM 文件固定 URL 前綴（如 `https://dm.tbms.internal/doc/`） | 部署時設定 |

---

## 與其他模組之邊界

### ET 不做的事

- ❌ 不在 Moodle 維護 SS 帳密 / 角色（屬 SS 模組）
- ❌ 不從 TSBMS DP 同步使用者資料
- ❌ 不保存文件型教材本體（PDF / PPT / 圖文，屬 DM 模組）
- ❌ 不客製 Moodle 核心，僅透過 plugin 擴充
- ❌ 不把 Moodle 學習資料同步回 TSBMS DB
- ❌ 不用捐血者資料做 Moodle 學員基礎

### 與 DM 之分工

| 教材類型 | 載體 | 理由 |
|---------|------|------|
| 影片 | ET 自管（Moodle 原生）| 保留 RQET004「強制觀看完影片才能進下一章節」的進度追蹤能力 |
| 文件型（PDF / PPT / 圖文）| ET 課程章節以連結引用 DM 教材固定 URL | 享 DM 版本管控；URL 永遠指最新發布版 |

詳見 [UCET002-上傳教材.md](../../use-cases/et/UCET002-上傳教材.md)。

### 與 SS 之分工

| 工作 | 由誰負責 |
|------|---------|
| 帳密儲存 | SS 模組 |
| 角色定義 | SS 模組 |
| 角色↔功能對應 | SS 模組（管理者於 SS 後台維護）|
| 登入認證、Token 簽發 / 驗證 | SS 模組（APISS001 / APISS002）|
| 功能清單來源 | ET 模組（提供清單給 SS 管理者於後台維護）|
| Moodle 系統角色（Manager / Teacher / Student）對應 | ET 端 `auth/tsbms` plugin 依 SS 回傳之 roles 自動指派 |

詳見 SS 模組規格（主專案 `TBMS/docs/specs/ss/spec.md`）。

---

## 後續產出（speckit）

| 文件 | 狀態 |
|------|------|
| spec_us1.md（UCET013 登入） | ✅ 已建 |
| spec_us2.md（UCET001 建課） | ✅ 已建 |
| spec_us3.md（UCET002 上傳教材） | ✅ 已建 |
| spec_us4.md（UCET003 編排章節） | ✅ 已建 |
| spec_us5.md（UCET004 建測驗） | ✅ 已建 |
| spec_us6.md（UCET005 邀請學員） | ✅ 已建 |
| spec_us7.md（UCET006 學習報表） | ✅ 已建 |
| spec_us8.md（UCET007 加入課程） | ✅ 已建 |
| spec_us9.md（UCET008 學習內容） | ✅ 已建 |
| spec_us10.md（UCET009 線上測驗） | ✅ 已建 |
| spec_us11.md（UCET010 個人進度） | ✅ 已建 |
| data-model.md | ⏳ 待建（多數實體由 Moodle 原生管理；學員 / 邀請對應表可獨立 DDL）|
| contracts/ | ⏳ 待建（auth/tsbms plugin 與 SS 之介接細節）|
| plan.md | ⏳ 待建 |
| research.md | ⏳ 待建 |
| tasks.md | ⏳ 待建 |
