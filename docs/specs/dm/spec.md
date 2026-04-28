# Feature Specification: 文件管理模組（Document Management）

**Created**: 2026-04-28（重構，對齊 BC / TL 拆法 — spec.md 薄殼 + spec_usX.md 各 US 細節）
**Status**: Draft
**Input**: 依據 requirements/RQDM.md + DM-模組建構概念.md 產出 DM 模組功能規格

---

## 模組概觀

文件管理模組（DM）為 TSBMS 周邊文件服務，**獨立部署**、**獨立 DB**、與主系統相同技術棧（FastAPI + React），**透過 SS 模組做使用者認證**（與主系統 DP 帳密完全切開），**透過 DP APIDP003 做啟動期系統參數查詢**。

### 核心定位

- **平台**：自建 FastAPI + React，PostgreSQL，獨立服務
- **管理範圍（三類文件）**：操作手冊 / SOP / 訓練教材（限文件型 PDF / PPT / 圖文）
- **不管理**：影片型教材（仍由 ET 模組自管，保留 RQET004 強制觀看追蹤）、表單（業務模組各自處理）
- **使用者群**：一般軍人（透過 SS 認證；與主系統 DP 帳密完全切開）
- **歷史**：原為獨立模組 → 2026-03-25 併入 ET → 2026-04-24 因 Moodle Wiki/Book/Database activity 無法滿足「版本歷程 + 多階簽核 + 狀態機」三項硬性需求，重新獨立為 DM 模組 → 2026-04-28 認證改走 SS

### 操作角色

| 角色 | 職責範圍 |
|------|----------|
| 一般使用者（任一 SS 角色 + DM 對應功能權限） | 上傳文件、建立審查單、加入文件明細、送審、讀取 |
| 審查者（SOP_REVIEWER） | 對審查單作核准 / 退件（**唯一硬卡點角色**，不影響功能選單顯示）|
| 系統自動 | 版本歷程維護、原子搬移、通知發送、稽核軌跡記錄 |
| SS 模組 | 提供登入認證（APISS001）與 Token 驗證（APISS002）|
| DP 模組 | 提供系統參數查詢（APIDP003，DM 內建靜態 Token）與共用稽核（SRVDP003）|
| ET 模組 | 課程章節以連結引用 DM 文件型教材固定 URL |

> 角色簡化（2026-04-27 / 2026-04-28 更新）：只硬卡 `SOP_REVIEWER`，其餘任一 SS 角色視為一般使用者；原 SOP_AUTHOR / SOP_READER 名稱廢除。SS 角色於 SS 模組獨立管理（規格位於主專案 `TBMS/docs/specs/ss/spec.md`）。

---

## Clarifications

### Session 2026-04-28（DM 重構：對齊 BC / TL 拆法）

- Q: spec.md 為何瘦身、移除 FR-XXX 條列？ → A: 對齊 SA 工作區 BC / TL 慣例 — 主規格薄殼，US 細節（含 Acceptance Scenarios，等同各 FR 行為）拆到各 spec_usX.md。FR-XXX 與 Acceptance Scenarios 大量重疊，BC / TL 模式以 Acceptance Scenarios 為唯一正式行為要求，避免雙軌。
- Q: Key Entities / Cross-Module / Config Params 為何仍留在 spec.md？ → A: DM 目前無 data-model.md / plan.md，這些跨切面資訊集中在 spec.md 較利檢索；待 speckit 產出時再分流到對應檔。

### Session 2026-04-28（認證改走 SS）

- Q: 使用者認證為何不再走 DP？ → A: SS 使用者為一般軍人，與主系統 DP 內部人員（護理師、檢驗師、庫存管理員）完全分流。SS 為獨立認證系統，與 DP **完全切開**（獨立 DB、不同步、不共用使用者 ID 命名空間）。
- Q: DM 仍與 DP 介接哪些 API？ → A: 僅保留 **APIDP003 系統參數查詢**（DM 內建靜態 Token）與 **SRVDP003 共用稽核**；不做任何使用者身分相關介接。

### Session 2026-04-27（簽核流程審查單批次模式）

- Q: 簽核以什麼為單位？ → A: **審查單（ticket）**。一張 ticket 可附多份文件（任意分類）；退件僅 ticket 級別整批退；同一文件可同時加入多張 ticket。
- Q: 自審是否禁止？ → A: 不限自審。同一人若兼具 SOP_REVIEWER 角色可核准自己送審的 ticket。
- Q: 角色簡化後只剩哪幾個？ → A: 只硬卡 `SOP_REVIEWER`；其餘任一 SS 角色視為一般使用者（原 SOP_AUTHOR / SOP_READER 名稱廢除）。

### Session 2026-04-27（檔名 + 版本號 + 原子搬移）

- Q: 文件如何識別「同一份」？ → A: `(CATEGORY, BASE_FILENAME)` UNIQUE，同分類同檔名再上傳一律視為新版（不開放「另存為新文件」）。檔名標準化：空格→底線、Unicode NFC、移除前後空白；BASE_FILENAME 大小寫不敏感；副檔名一致才視為同檔。
- Q: 版本號規則？ → A: 預設 `V{MAJOR}.{MINOR}` 或 `V{MAJOR}.{MINOR}R{REVISION}`。第一版 `V1.0`；既有文件再上傳系統建議「最低衝擊」`Vx.yR(z+1)`；唯一性比對對象包含 STATUS=PUBLISHED / WITHDRAWN，不含 REJECTED（退件版本不占用版號）。流水版（rev 1/2/3）由分類層級配置。
- Q: 為何最新版檔名不加版本後綴？ → A: 外部連結（ET 模組課程教材、主系統 [?] 按鈕）需要穩定 URL。最新版固定 `{原目錄}/{BASE_FILENAME}`，URL 永遠指最新；歷史版重命名加版號後綴並移到 `{原目錄}/歷史版本/`。
- Q: 上傳新版時的搬移流程？ → A: **原子搬移 + DB transaction**：(A) 鎖 DOC_ID → (B) 重命名舊最新檔加版號 → (C) 移到 `歷史版本/` → (D) 新檔寫入 `{BASE_FILENAME}` → (E) DB transaction 同步更新 → (F) 釋放鎖、發通知。失敗回滾。詳見 [spec_us3.md](spec_us3.md)。
- Q: 訓練教材怎麼進來？ → A: 文件型訓練教材（PDF / PPT / 圖文）放 DM 享版本管控；ET 模組課程章節以連結引用 DM 固定 URL（`/doc/{DOC_ID}`）。**影片型教材仍由 ET 模組自管**（RQET004 強制觀看追蹤）。
- Q: DM 教材撤回後 ET 模組教材引用連結怎麼辦？ → A: DM 端 STATUS=WITHDRAWN 時 URL 回 410 Gone，搭配「此文件已撤回」頁；Phase 2 補 webhook 通知 ET 模組課程編輯者死鏈，Phase 1 採人工提報。

### Session 2026-04-27（文件儲存空間 + DM Token）

- Q: 文件儲存空間如何規劃？是否要寫死路徑？ → A: 走參數化。由 DP 系統參數 `DP_PARAM_D` 維護，`PARAM_ID='DM_UPLOAD_PATH'`，切三組路徑：`PARAM_KEY='MANUAL'` / `'SOP'` / `'TRAINING'`。
- Q: DM 如何讀到這組參數？ → A: 同 LBSB01 模式 — DM 程式內以**常數**寫入永不過期 Bearer Token（對應 `DP_PARAM_D` `PARAM_ID='DP_EXT_API_KEY'`、`PARAM_KEY='DM'`），啟動時呼叫 **APIDP003** 取 `DM_UPLOAD_PATH` 全部明細，寫進記憶體；後續所有上傳依 CATEGORY 對應路徑落地。**不沿用 APIDP001 動態換 Token**。
- Q: 為何不用 APIDP001 換 Token？ → A: DM 為長駐獨立服務、與主系統內網部署，採內建靜態 Token 簡化啟動依賴；同 LBSB01 已採此模式（`DP_EXT_API_KEY` PARAM_KEY='LB_PRINT'），DM 沿用既有設計慣例。

---

## User Stories

| Story | UC 編號 | 名稱 | 優先級 | 子檔 |
|-------|---------|------|--------|------|
| 1 | UCDM004 | DM 登入（SS） | P1 | [spec_us1.md](spec_us1.md) |
| 2 | UCDM005 | DM 主頁與功能選單載入 | P1 | [spec_us2.md](spec_us2.md) |
| 3 | UCDM001 | 文件管理與版本管控 | P1 | [spec_us3.md](spec_us3.md) |
| 4 | UCDM006 | 文件審查作業流程 | P1 | [spec_us4.md](spec_us4.md) |
| 5 | UCDM002 | 線上文件查閱 | P1 | [spec_us5.md](spec_us5.md) |
| 6 | UCDM003 | SOP 文件查閱 | P2 | [spec_us6.md](spec_us6.md) |

> 所有 Story 共用 [§操作角色](#操作角色) / [§Cross-Module Dependencies](#cross-module-dependencies) / [§Configurable Parameters](#configurable-parameters) / [§Edge Cases](#edge-cases) / [§Assumptions](#assumptions) / [§邊界](#與其他模組之邊界) / [§Key Entities](#key-entities)。

---

## Edge Cases

- 上傳 PDF 檔案大小超過限制（單檔上限由 `DM_MAX_FILE_MB` 控制）→ 系統拒絕並提示
- 同一文件多次送審但前次仍 SUBMITTED：系統應阻止重複送審（同一份 + 同版號），允許「撤回 + 重新送審」
- 簽核者 = 送審者本人：**不限制**（同一人若兼具 SOP_REVIEWER 角色可核准自己送審的 ticket）
- 文件已發布後上傳新版：原版本保留為歷程，新版回到 DRAFT 狀態走完整簽核；舊版本不可被覆蓋
- 已發布文件被撤回：該文件 STATUS=WITHDRAWN，主系統 / Moodle 連結返回 410 Gone（搭配「此文件已撤回」頁）；Phase 2 補 webhook 通知 ET 模組死鏈
- **同名檔案上傳但內容是不同主題的文件**：系統視為新版上傳，要求使用者確認；若使用者意在新文件，須改檔名後再上傳（系統不開放「同檔名 + 不同 DOC_ID」共存）
- **使用者改了版本號但與某舊版重複**：拒絕並提示「版號 Vx.y 已存在於版本 N」；唯一性比對對象包含 STATUS=PUBLISHED / WITHDRAWN，但不含 REJECTED
- **原子搬移失敗（檔案 OS 錯誤）**：完整回滾檔案 + DB transaction + 釋放 DOC_ID 鎖；失敗事件寫 DM_AUDIT 與 DP Audit Log
- **歷史版本目錄被外部 URL 直接存取**：DM 後端 reject 403；歷史版實體檔案僅能透過 DM 介面下載（驗權限後後端轉發）
- **待審查目錄被外部 URL 直接存取**：DM 後端 reject 403；待審查檔案僅在 DM 端供送審 / 審查者預覽，不開放公開連結
- DOC_ID 已被 ET / 主系統引用，但對應 DM 文件被硬刪除：DM 必須**禁止硬刪已被引用的文件**（軟刪 / 撤回為主），以免外部連結 404
- 線上操作手冊查無對應 func_name：回 404 + 「尚無操作手冊」頁面（不阻擋使用者繼續操作主系統）
- SS 服務暫時不可用（DM 啟動或 Token 過期）：DM 顯示「認證服務暫不可用」並進入只讀模式（公開分類仍可瀏覽，禁止任何寫入）
- SS 端使用者角色變動（如取消 SOP_REVIEWER）：DM 不快取 functions，每次登入重新取，下一次登入即生效
- 稽核軌跡（DM_AUDIT）即使文件硬刪除（如允許）也必須保留（append-only，類同 DP_AUDIT_LOG）

---

## Key Entities

- **DM_DOC**: 文件主檔（DOC_ID, TITLE, CATEGORY_ID, BASE_FILENAME, CURRENT_VERSION_ID, STATUS, OWNER_USER_ID, CREATED_AT...）<br>UNIQUE `(CATEGORY_ID, BASE_FILENAME)` — 檔名作為文件邏輯識別
- **DM_DOC_VERSION**: 文件版本（VERSION_ID, DOC_ID, VERSION_NO, FILE_PATH, FILE_NAME_ARCHIVED, IS_CURRENT, HTML_BODY, CHANGE_SUMMARY, AUTHOR_USER_ID, PUBLISHED_AT...）<br>UNIQUE `(DOC_ID, VERSION_NO)`
- **DM_CATEGORY**: 分類主檔（CAT_ID, NAME, PARENT_ID, VERSION_RULE='SEMVER'/'SEQUENTIAL'）
- **DM_APPROVAL_TICKET**: 審查單主檔（TICKET_ID PK, TITLE, SUBMITTER_USER_ID, STATUS, REVIEWER_USER_ID, REJECT_REASON, SUBMITTED_AT, ACTED_AT, DELETED）
- **DM_APPROVAL_TICKET_DOC**: 審查單-文件明細（TICKET_ID + DOC_ID + VERSION_ID 複合 PK）
- **DM_APPROVAL**: 簽核**動作歷程**（APPROVAL_ID, TICKET_ID, USER_ID, ACTION='SUBMIT/APPROVE/REJECT/CLOSE', COMMENT, ACTED_AT；append-only）
- **DM_AUDIT**: 稽核軌跡（AUDIT_ID, DOC_ID, ACTION_TYPE, USER_ID, BEFORE_VALUE, AFTER_VALUE, CREATED_AT）— append-only
- **DM_SUBSCRIPTION**: 訂閱（SUB_ID, USER_ID, DOC_ID 或 CAT_ID, NOTIFY_CHANNEL='EMAIL'/'SYSTEM'）
- **DM_FUNC_MANUAL_MAP**: 主系統 func_name → DOC_ID 對照（FUNC_NAME, DOC_ID, NOTE）

> **不擁有的資料**：使用者帳號（屬 SS 模組）、影片型教材（屬 ET 模組）。完整 DDL 見 [data-model.md](data-model.md)（待建）。

---

## Success Criteria

- **SC-001**: 線上操作手冊查詢（APIDM001）回應時間 90th percentile < 200ms；主系統 [?] 按鈕點擊到顯示手冊 < 1s
- **SC-002**: 全文檢索回應時間 < 1s（10 萬筆文件量級）
- **SC-003**: 資訊人員可在 1 分鐘內完成單份文件上傳（含分類、檔名、版本、變更摘要、送審）
- **SC-004**: 審查單核准後原子搬移完成於 5 秒內（含檔案搬移 + DB transaction）
- **SC-005**: ET 模組教材中之 DM 連結於 DM 端版本切換後，下次點擊即指最新版（無需 ET 介入）
- **SC-006**: 已發布文件版本歷程 100% 可完整回溯
- **SC-007**: 簽核流程符合「不限自審」「退件需原因」「軌跡不可改」三條鐵則

---

## Non-Functional Requirements

- **NFR-001**: 線上操作手冊查詢回應時間應 < 200ms（90th percentile）
- **NFR-002**: 全文檢索回應時間 < 1s（10 萬筆文件量級）
- **NFR-003**: DM 服務可用率 ≥ 99.5%；SS 認證不可用時 DM 進入只讀模式（已發布文件仍可瀏覽）
- **NFR-004**: 介面提供完整中文化（同主系統）
- **NFR-005**: 所有 API MUST Bearer Token 認證；Token 由 SS 簽發
- **NFR-006**: 檔案儲存路徑不可由 URL 直接存取（必須透過 DM 後端轉發，驗證權限後才回應）
- **NFR-007**: 稽核軌跡資料表設定 DB 層級不可 UPDATE / DELETE 約束（trigger 或 view）

---

## Assumptions

- **SS API（APISS001 / APISS002）已就緒並穩定**；DM 與 SS 之間透過 IP 白名單 / mTLS 或 API Key 管控
- **DP API（APIDP003 系統參數查詢、SRVDP003 共用稽核）已就緒**；DP `DP_PARAM_D` 已建立 `PARAM_ID='DM_UPLOAD_PATH'` 三筆（MANUAL / SOP / TRAINING）與 `PARAM_ID='DP_EXT_API_KEY'`、`PARAM_KEY='DM'` 的 DM 內建 Token
- DM 服務啟動環境提供穩定可寫入的儲存路徑（檔案系統 / Object Storage / NAS），管理者依 `DP09-系統參數維護作業` 維護路徑
- 主系統前端共用層 [?] 按鈕已實作（見 TBMS repo `docs/specs/dp/線上操作手冊整合設計.md`）
- ET 模組教材編輯者於 ET 端手動嵌入 DM 連結（Phase 1）；Phase 2 評估提供「插入 DM 連結」UI 輔助
- DM 採 React + FastAPI + PostgreSQL；獨立部署；與主系統同網段或經 service mesh 直連 SS / DP

---

## Cross-Module Dependencies

| Direction | Module | 編碼 | Purpose |
|-----------|--------|------|---------|
| DM → SS | 單一登入模組（SS） | APISS001 | 使用者登入認證，取 Token + 角色 + 可用功能 |
| DM → SS | 單一登入模組（SS） | APISS002 | 每次請求 Token 驗證 |
| DM → DP | 資訊模組（DP） | APIDP003 | 取系統參數（`DM_UPLOAD_PATH` 等，DM 內建靜態 Token）|
| DM → DP | 資訊模組（DP） | SRVDP003 | 跨系統重大事件寫共用 Audit Log（DM 自身審查軌跡寫 DM_AUDIT）|
| 主系統 → DM | 各業務模組 | APIDM001 | 線上操作手冊查閱（by func_name）|
| 主系統 → DM | 各業務模組 | APIDM002 | 文件查詢（by DOC_ID）|
| ET 模組 → DM | 教育訓練模組 | URL Redirect | 教材內 SOP / 手冊超連結（`/doc/{DOC_ID}`）|
| DM → 外部 | 通知中心 / Email | API / SMTP | 文件發布通知 |

> **使用者認證一律走 SS**（與主系統 DP 帳密完全切開）；DM 與 DP 之間僅保留**系統參數查詢**與**共用稽核**兩項 API 介接，**不**做任何使用者身分相關介接。

---

## Configurable Parameters

以下參數透過 DP 模組參數管理維護（DP_PARAM + DP_PARAM_D），DM 啟動時透過 APIDP003 讀取：

| 參數類別代碼 | 參數類別名稱 | 說明 | 預設值摘要 |
|-------------|-------------|------|-----------|
| `DM_UPLOAD_PATH` | DM 文件儲存路徑 | 各分類之根目錄（MANUAL / SOP / TRAINING） | `/data/dm/manual/` / `/data/dm/sop/` / `/data/dm/training/` |
| `DM_MAX_FILE_MB` | 單檔上傳大小上限 | 整數，單位 MB | 50 |
| `DP_EXT_API_KEY` (PARAM_KEY='DM') | DM 內建靜態 Token | 對應 DP 端外部存取 Token | 部署時設定 |

DM 自身亦有少量配置（**不**經 DP 維護）：

| 參數 | 說明 | 預設值 |
|------|------|--------|
| SS 端點 + API Key / mTLS 憑證 | DM 呼叫 APISS001 / APISS002 之連線資訊 | 部署時設定 |
| DP 端點 + 內建靜態 Token | DM 呼叫 APIDP003 / SRVDP003 之連線資訊 | 部署時設定 |
| 通知範本（主旨 / 內文）| 文件發布通知範本 | 資訊人員可配置 |

---

## Scope Boundaries

**In Scope（Phase 1 MVP）**：
- 文件 CRUD + 版本管控（檔名識別、版本號規則、原子搬移）
- 審查單批次簽核（單層）
- 線上操作手冊（by func_name）
- 基本搜尋（by 分類 + 關鍵字）
- 稽核軌跡

**Out of Scope（Phase 2+）**：
- 多階會簽 / 動態簽核流
- 全文檢索（中文斷詞、語意搜尋）
- AI 文件摘要 / 智能標籤
- 文件協同編輯（多人即時編輯）
- 行動端 App
- 跨機構文件交換
- DM → ET 撤回 webhook 通知（Phase 1 採人工提報）

**不在 DM 範圍**（永久排除）：
- **影片型訓練教材**：仍由 ET 模組管理（保留 RQET004 強制觀看追蹤能力）
- **表單**：以業務模組各自需求處理，不集中於 DM
- **使用者帳密 / 角色管理**：由 SS 模組負責；DM 僅消費 SS 認證結果

---

## 與其他模組之邊界

### DM 不做的事

- ❌ 不維護自己的使用者帳號表（完全依賴 SS 模組，與主系統 DP 帳密無關）
- ❌ 不從 TSBMS DP 同步任何使用者資料
- ❌ 不直接讀主系統業務 DB（如捐血人、血品）
- ❌ 主系統不直接讀 DM 的 DB（所有讀取走 DM API）
- ❌ Moodle 不直接讀 DM 的 DB（只透過 URL 超連結 + DM 端 SS session）
- ❌ 不接受影片型檔案上傳（影片走 ET 模組自管）

### 與 ET 之分工

| 教材類型 | 載體 | 理由 |
|---------|------|------|
| 影片 | ET 模組自管（Moodle 原生）| 保留 RQET004「強制觀看完影片才能進下一章節」的進度追蹤能力 |
| 文件型（PDF / PPT / 圖文）| **DM 模組** + ET 課程章節以連結引用 | 享 DM 版本管控；DM URL 永遠指最新發布版 |

### 與 SS 之分工

| 工作 | 由誰負責 |
|------|---------|
| 帳密儲存 | SS 模組 |
| 角色定義 / 角色↔功能對應 | SS 模組（管理者於 SS 後台維護）|
| 登入認證、Token 簽發 / 驗證 | SS 模組（APISS001 / APISS002）|
| DM 功能清單來源 | DM 模組（提供清單給 SS 管理者於後台維護）|
| DM 主頁功能選單渲染 | DM 端依 SS 回傳之 functions 決定 Enable / Disable |
| SOP_REVIEWER 角色卡點 | DM 端於 UCDM006 動作層級檢查（功能選單顯示由 SS 端 RBAC 決定）|

### 與 DP 之分工（限非認證範圍）

| 工作 | 由誰負責 |
|------|---------|
| DM 上傳路徑等系統參數 | DP（`DP_PARAM_D`）；DM 啟動時透過 APIDP003 + 內建靜態 Token 讀取 |
| 跨系統重大事件稽核 | DP（SRVDP003 寫 DP_AUDIT_LOG）；DM 自身審查軌跡寫 DM_AUDIT |
| **使用者認證 / Token** | **不在 DP 範圍**（一律走 SS）|

詳見 [DM-模組建構概念.md](DM-模組建構概念.md)、SS 模組規格（主專案 `TBMS/docs/specs/ss/spec.md`）。

---

## 後續產出（speckit）

| 文件 | 狀態 |
|------|------|
| spec_us1.md（UCDM004 登入） | ✅ 已建 |
| spec_us2.md（UCDM005 主頁） | ✅ 已建 |
| spec_us3.md（UCDM001 文件管理） | ✅ 已建 |
| spec_us4.md（UCDM006 審查） | ✅ 已建 |
| spec_us5.md（UCDM002 線上查閱） | ✅ 已建 |
| spec_us6.md（UCDM003 SOP 查閱） | ✅ 已建 |
| data-model.md | ⏳ 待建（DDL：DM_DOC / DM_DOC_VERSION / DM_CATEGORY / DM_APPROVAL / DM_AUDIT / DM_SUBSCRIPTION / DM_FUNC_MANUAL_MAP）|
| contracts/APIDM001.md | ⏳ 待建（線上操作手冊查詢）|
| contracts/APIDM002.md | ⏳ 待建（文件查詢 by DOC_ID）|
| contracts/APIDM101-106.md | ⏳ 待建（內部作業 API）|
| plan.md | ⏳ 待建（實作計畫）|
| research.md | ⏳ 待建（設計決策紀錄）|
| tasks.md | ⏳ 待建（開發任務清單）|
