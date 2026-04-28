# ET 模組 — 交付文件 TODO

記錄 ET 模組**尚未產出**的交付文件 / 教材、以及**待討論的設計議題**。

## 清單

| # | 項目 | 類型 | 狀態 | 預計討論 |
|---|------|------|------|---------|
| 1 | [Moodle 安裝過程手冊](#1-moodle-安裝過程手冊) | 交付文件 + 教育訓練教材 | 待撰寫 | 2026-04-28（下週） |
| 2 | [文件管理方案：Python 檔案管理系統 vs Moodle 原生](#2-文件管理方案python-檔案管理系統-vs-moodle-原生) | 設計議題 | **已決議**（2026-04-24：採主系統技術棧獨立 DM 模組）| — |

---

## 1. Moodle 安裝過程手冊

### 定位

- **雙重角色**：
  - **交付文件**：Moodle LMS 環境建置的正式交付物（供驗收 / 後續維運參考）
  - **教育訓練教材**：資訊人員接手維運、或日後重新部署時的操作依據，本身即是 ET 模組培訓內容之一

### 內容需求

| 章節 | 內容 |
|------|------|
| **1. 軟硬體最小要求** | CPU / RAM / 磁碟容量、OS 版本、PHP / MySQL(Postgres) / Web Server 版本要求，網路埠 |
| **2. 安裝源** | 官方下載位置、版本號、Plugin 下載清單（auth/tsbms、enrol_invitation 等）、中文語系包來源 |
| **3. 安裝步驟** | 逐步操作步驟 — **每一步驟都要有畫面截圖**（含關鍵設定頁、輸入欄位、按鈕位置） |

### 驗收條件

- [ ] 軟硬體規格表完整（CPU、RAM、磁碟、OS、PHP、DB、Web Server 版本）
- [ ] 安裝源可追溯（有明確 URL 與版本號，可於斷網環境預先下載）
- [ ] 每個安裝步驟都有截圖，關鍵設定（DB 連線、管理員帳號、cron、SMTP）不遺漏
- [ ] 附「常見錯誤排除」章節
- [ ] 文件以 PDF 或 Word 產出，可印刷

### 相關設計

- [ET-模組建構概念.md §5.1 階段 1：平台建置](ET-模組建構概念.md#51-建議的進行順序) — 本文件即該階段的交付成果
- [ET-模組建構概念.md §5.3 建議的技術選型](ET-模組建構概念.md#53-建議的技術選型) — 版本 / 部署方式 / DB 的決策基礎
- SS 模組規格（主專案 `TBMS/docs/specs/ss/spec.md`）— 安裝步驟需涵蓋 `auth/tsbms/` plugin（呼叫 APISS001 / APISS002）的部署

---

## 2. 文件管理方案：Python 檔案管理系統 vs Moodle 原生

### 議題

**SOP 文件管理、線上操作手冊、訓練教材**三類檔案：

- **主張**：由新設的 **Python 檔案管理系統** 負責（版本控管、簽核、狀態機、發布），Moodle 只留學習平台功能（課程 / 測驗 / 學員儀表板 / 邀請信）
- **狀態**：**已決議（2026-04-24）** — 採方案 C 變體：以 **TSBMS 主系統技術棧（FastAPI + React）** 自建 **DM 模組**，獨立部署；透過 DP API 認證。
- **成果文件**：[../dm/DM-模組建構概念.md](../dm/DM-模組建構概念.md)、[../../requirements/RQDM.md](../../requirements/RQDM.md)、[../../use-cases/dm/](../../use-cases/dm/)

### 背景（為何浮現）

1. 原設計使用 Moodle Wiki 模組做 SOP 版本控管（[UCET011](../../use-cases/et/UCET011-維護SOP文件與版本.md)、[ET17-Wiki模組.md](functions/ET17-Wiki模組.md)）
2. 評估後發現不合需求：
   - Moodle Wiki = 協作百科編輯，**非受控 SOP 發布**
   - Moodle File resource **無版本歷程**（覆蓋即丟）
   - Moodle Database activity 僅有**單層 approval**，無多階簽核、無版本
   - Moodle 官方自述：「若應用以檔案為核心，應考慮專用的 DMS 類別軟體」
3. RQET009 明列要求：**版本與變更控管、電子簽核與稽核軌跡、發布與通知** — Moodle 原生三項皆不足

### 候選方案

| 方案 | 內容 | 主要優缺點 |
|------|------|-----------|
| **A. Moodle Database + PHP Plugin 補強** | Moodle 原生 + 自寫/第三方 PHP 簽核 Plugin | **✗ 團隊不用 PHP** — 已排除 |
| **B. Python 自建 Moodle Plugin** | 用 Python 寫 Moodle Plugin | **✗ 不可行** — Moodle Plugin 必須 PHP |
| **C. Python 檔案管理系統 + Moodle 整合** ★ | 自建 Python 系統負責檔案/版本/簽核；Moodle 專注學習 | 技能重用（既有 Python/FastAPI 能力）；架構清楚；開發量中等 |
| **D. 外接成熟 DMS**（SharePoint / Alfresco / Nextcloud）| 檔案管理外包給 DMS，Moodle 學習 | DMS 功能完整、驗證成熟；但多一個系統、需評估組織是否已有 |

### 待決事項

- [ ] 確認走 C（Python 自建）還是 D（外接 DMS），或混合
- [ ] 若採 C：Python 系統的系統定位與命名（目前暫稱「Python 檔案管理系統」）
- [ ] 若採 C：Moodle 整合機制選擇 — URL Resource / LTI 1.3 / Web Services API 三者的組合與順序（MVP 用哪一個）
- [ ] 若採 C：是否要與 TSBMS 後端（FastAPI）同 repo，或獨立部署
- [ ] 若採 D：組織內是否已有可用 DMS？授權／採購程序？

### 影響範圍（若 C 定案，SA 規格連動調整）

| 文件 | 調整 |
|------|------|
| [ET-模組建構概念.md](ET-模組建構概念.md) | §1.2 / §2.3 / §3 / §4 / §5 全面調整：加入 Python 檔案管理系統、限縮 Moodle 範圍、新增整合接點 |
| [UCET011](../../use-cases/et/UCET011-維護SOP文件與版本.md) | 流程改為 Python 系統上傳 / 版本 / 簽核 |
| [UCET012](../../use-cases/et/UCET012-查閱線上操作手冊.md) | 目標系統從 Moodle Book → Python 系統 |
| [ET17-Wiki模組.md](functions/ET17-Wiki模組.md) | 廢棄 or 改為「Python 檔案管理系統（SOP）」|
| [ET18-書籍模組.md](functions/ET18-書籍模組.md) | 廢棄 or 改為「Python 檔案管理系統（操作手冊）」|
| [RQET.md](../../requirements/RQET.md) | 追蹤矩陣改引用 Python 系統 |

### 相關參考（對話討論過的分析）

- Moodle Database activity 特性與缺口（查自 docs.moodle.org）
- Moodle Plugin 只能 PHP（查自 moodledev.io）
- Moodle 支援的免費 DB：PostgreSQL 13+、MySQL 8.0+、MariaDB 10.6.7+
- Moodle 整合六接點：SS、URL Resource、LTI 1.3、Book 做導讀、Web Services API、線上操作手冊
