# User Story 3 — UCET002 上傳教材（影片 / 引用 DM 文件）

> 返回總檔：[spec.md](spec.md) | 模組：教育訓練（ET） | UC：[UCET002](../../use-cases/et/UCET002-上傳教材.md)

管理者上傳課程教材至章節。**影片型**直接由 ET 上傳並播放（保留強制觀看追蹤能力以滿足 RQET004）；**文件型**（PDF / PPT / 圖文）改以連結引用 DM 模組之固定 URL（`https://dm.tbms.internal/doc/{DOC_ID}`），享 DM 版本管控。

**Why this priority** (P1): 教材是課程的內容主體，無教材無從學習。

**Independent Test**: 影片上傳後可在課程頁播放；文件型教材以 DM URL 引用後，DM 端更版時 ET 課程連結自動指向最新版。

## Acceptance Scenarios

1. **Given** 一個既有課程章節，**When** 管理者選擇「影片教材」並上傳影片檔，**Then** Moodle 驗證格式 / 大小通過後儲存影片，課程頁可直接播放
1a. **Given** 影片格式不支援或超過上傳大小限制，**When** 管理者上傳，**Then** 系統提示具體錯誤
2. **Given** DM 已發布一份 SOP 文件（DOC_ID 已知），**When** 管理者於章節新增「外部連結」教材並填入 DM 固定 URL，**Then** Moodle 儲存連結；學員點選即跳轉 DM 對應文件頁
3. **Given** 同一份 DM 文件更版（v2.0），**When** 學員再次點選 ET 課程章節之引用連結，**Then** DM 回最新版，ET 課程不需異動連結
4. **Given** DM 端文件被撤回（STATUS=WITHDRAWN），**When** 學員點選引用連結，**Then** DM URL 回 410 Gone（Phase 2 補 webhook 通知 ET 課程）
5. **Given** 章節同時包含影片、文件、圖文，**When** 管理者使用頁面編輯器（WYSIWYG）製作混合媒材頁面，**Then** Moodle 支援多媒體混排呈現

## 流程圖（Mermaid）

```mermaid
flowchart TD
    Start[管理者進入課程章節編輯頁] --> Type{教材類型}

    Type -->|影片| V1[Moodle 上傳影片檔]
    V1 --> V2{格式 / 大小檢核}
    V2 -->|不通過| VErr[提示具體錯誤]
    V2 -->|通過| V3[儲存影片 + 設定標題 / 說明]
    V3 --> V4[預覽 → 課程頁可直接播放<br/>保留 RQET004 強制觀看追蹤]

    Type -->|文件型 PDF / PPT / 圖文| D1[新增「外部連結」教材]
    D1 --> D2[填入 DM 固定 URL：<br/>https://dm.tbms.internal/doc/DOC_ID]
    D2 --> D3[設定章節標題 / 說明、預覽]
    D3 --> D4{學員點選連結}
    D4 -->|DM 文件 PUBLISHED| D5[DM 回最新發布版]
    D4 -->|DM 文件已撤回 WITHDRAWN| D6[DM URL 回 410 Gone<br/>顯示「此文件已撤回」]

    Type -->|混合媒材| W1[使用 WYSIWYG 編輯器<br/>並列文字 / 圖片 / 內嵌影片 / DM 連結]
    W1 --> W2[儲存章節]

    DMVer([DM 端文件更版 V1.0 → V2.0]) -.->|無需 ET 介入| D5
```

> **詳細 Activity Diagram**：見 [UCET002-上傳教材.md](../../use-cases/et/UCET002-上傳教材.md)（EA 匯出 PNG）

## 對應 RQ

- RQET001（直接上傳影片檔，課程頁直接播放）
- RQET002（拖拉式介面調整影片 / 文件 / 作業順序）
- RQET003（混合媒材呈現）
- RQET010（文件型教材引用 DM 固定 URL，享 DM 版本管控）

## 前置依賴

- US2（UCET001 建立課程）已完成
- DM 模組已上線；文件型教材已於 DM 上傳並 PUBLISHED（取得 DOC_ID）
- 影片型教材檔案儲存空間已配置
