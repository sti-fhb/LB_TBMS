# User Story 5 — UCDM002 線上文件查閱

> 返回總檔：[spec.md](spec.md) | 模組：文件管理（DM） | UC：[UCDM002](../../use-cases/dm/UCDM002-線上文件查閱.md)

使用者透過三個入口查閱已發布文件：（1）主系統各畫面之線上操作手冊按鈕（by func_name）；（2）ET 模組課程章節之引用連結（DOC_ID URL）；（3）DM 文件庫主動瀏覽 / 搜尋。三入口共用相同的最新版指向（`{DM_UPLOAD_PATH[CATEGORY]}/{BASE_FILENAME}`）。

**Why this priority** (P1): 文件被讀取是 DM 存在的最終目的。

**Independent Test**: 主系統按 [?] → 看到對應手冊；ET 模組教材點 SOP 連結 → 看到對應 SOP；DM 文件庫直接搜尋 → 找到並開啟最新發布版。

## Acceptance Scenarios

1. **Given** 主系統某畫面（例如 LBSB01）已維護 func_name → DOC_ID 對應，**When** 使用者點擊該畫面之 [?] 線上操作手冊按鈕，**Then** 主系統呼叫 `APIDM001 GET /api/dm/manual?func_name=XXX`，DM 回 `{ doc_id, url, title, version }` 並由瀏覽器轉跳對應文件頁
2. **Given** func_name 無對應 DOC_ID，**When** 主系統呼叫 APIDM001，**Then** DM 回 404；主系統前端顯示「尚無操作手冊」（不阻擋使用者繼續操作）
3. **Given** ET 模組課程章節以連結引用 DM 教材固定 URL（`https://dm.tbms.internal/doc/{DOC_ID}`），**When** 學員點選連結，**Then** DM 回最新發布版內容
4. **Given** 一份文件已撤回（STATUS=WITHDRAWN），**When** 使用者點選對應 URL，**Then** DM 回 410 Gone，搭配「此文件已撤回」頁
5. **Given** DM 端版本切換（V1.0 → V2.0 核准發布），**When** ET 模組課程或主系統下次點同一連結，**Then** 自動指向最新版（無需 ET / 主系統介入）
6. **Given** 歷史版本目錄被外部 URL 直接存取，**When** 任何來源嘗試，**Then** DM 後端 reject 403；歷史版實體檔案僅能透過 DM「查看版本歷程」介面下載（具 DM02 功能權限即可由後端轉發；系統權限管控僅至功能層）

## Activity Diagram（UC 內部流程）

```mermaid
flowchart LR
    subgraph 三入口
        A[主系統 [?] 按鈕<br/>by func_name]
        B[ET 課程章節連結<br/>by DOC_ID URL]
        C[DM 文件庫<br/>主動瀏覽 / 搜尋]
    end

    A --> M{APIDM001<br/>GET /api/dm/manual?func_name=XXX}
    M -->|有對應| Doc[DM 回 doc_id, url, title, version]
    M -->|無對應| NA[404 主系統前端顯示<br/>「尚無操作手冊」<br/>不阻擋使用者操作]
    B --> Doc
    C --> Doc

    Doc --> Status{文件 STATUS}
    Status -->|PUBLISHED| View[使用者瀏覽最新發布版<br/>原目錄/BASE_FILENAME]
    Status -->|WITHDRAWN| Gone[410 Gone<br/>「此文件已撤回」頁]

    View --> History{需查歷史版本?}
    History -->|是| HistDir[透過 DM 後端轉發下載<br/>具 DM02 功能權限即可<br/>歷史版本目錄不開放外部 URL]
    History -->|否| End([結束])

    DirectURL[/外部直接訪問<br/>歷史版本目錄/] -.->|被擋| Forbidden[403 Forbidden]
```

## 對應 RQ

- RQDM003（ET 課程章節引用 DM 教材固定 URL）
- RQDM004（線上操作手冊功能）

## 前置依賴

- US3（UCDM001 文件管理與版本管控）已上線且至少有一份 PUBLISHED 文件
- 主系統 / ET 模組已維護引用連結（func_name → DOC_ID 對照、教材內 DOC_ID URL）

## 穩定 URL 結構

| URL | 用途 |
|-----|------|
| `/doc/{DOC_ID}` | 文件瀏覽頁（含版本、下載按鈕）|
| `/manual?func={func_name}` | 線上操作手冊 |
| `/category/{CAT_ID}` | 分類清單頁 |
| `/search?q=XXX` | 搜尋頁 |
