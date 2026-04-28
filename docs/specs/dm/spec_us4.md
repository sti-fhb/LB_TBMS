# User Story 4 — UCDM006 文件審查作業流程

> 返回總檔：[spec.md](spec.md) | 模組：文件管理（DM） | UC：[UCDM006](../../use-cases/dm/UCDM006-文件審查作業流程.md)

使用者透過 DM05 建立**審查單（ticket）**並加入多份文件明細，狀態機 `DRAFT → SUBMITTED → APPROVED / REJECTED`；任一狀態使用者可主動「結案（軟刪除）」標記 DELETED 不可逆。**核准 / 退件僅 SOP_REVIEWER 硬卡點**；建單 / 加文件 / 送審 / 讀取由「任一帳號 + DM05 功能權限」即可，不限自審。

**Why this priority** (P1): 簽核軌跡為文件版本管控的法規面要求，與 US3 並列為 MVP。

**Independent Test**: 建立審查單 → 加入 2 份文件 → 送審 → SOP_REVIEWER 核准 → 兩份文件依原子搬移流程同步發布；退件 → 兩份回 DRAFT。

## Acceptance Scenarios

1. **Given** 使用者具 DM05 功能權限，**When** 進入審查作業頁建立審查單，**Then** 系統建立 ticket（STATUS=DRAFT, SUBMITTER_USER_ID=當前使用者）
2. **Given** 一張 DRAFT ticket，**When** 使用者加入文件明細（任意分類），**Then** 系統寫入 DM_APPROVAL_TICKET_DOC（不檢查文件鎖定，**同一文件可同時加入多張 ticket**）
3. **Given** 一張 DRAFT ticket 含 ≥1 份文件明細，**When** 使用者送審，**Then** ticket 狀態 → SUBMITTED；系統通知具 SOP_REVIEWER 角色之使用者
4. **Given** 一張 SUBMITTED ticket，**When** SOP_REVIEWER 核准，**Then** ticket → APPROVED；系統批次為 ticket 內每份文件執行原子搬移流程（per ticket 內逐份文件，詳見 spec_us3.md §目錄結構）
5. **Given** 一張 SUBMITTED ticket，**When** SOP_REVIEWER 整批退件並填退件原因，**Then** ticket → REJECTED；ticket 內所有文件回 DRAFT；待審查檔保留於 `待審查/` 不動；送審者修改後可建新 ticket 重送
6. **Given** 任一狀態（DRAFT / SUBMITTED / REJECTED）之 ticket，**When** 使用者主動「結案」，**Then** ticket → DELETED（軟刪除，final）
7. **Given** 同一文件已加入 ticket A（PENDING）與 ticket B（PENDING），**When** ticket A 先核准發布，**Then** ticket B 仍可繼續審查；ticket B 通過時若文件已 PUBLISHED 則 noop（仍記動作歷程）
8. **Given** 任一簽核動作（送審 / 核准 / 退件 / 結案），**When** 完成，**Then** 系統寫入 DM_APPROVAL（動作歷程，append-only）+ DM_AUDIT；跨系統重大事件同步寫 DP_AUDIT_LOG（透過 SRVDP003）
9. **Given** 一般使用者（非 SOP_REVIEWER），**When** 嘗試核准 / 退件，**Then** 系統拒絕並提示權限不足

## 流程圖（Mermaid）

### 審查單狀態機

```mermaid
stateDiagram-v2
    [*] --> DRAFT: 建立審查單
    DRAFT --> SUBMITTED: 送審
    SUBMITTED --> APPROVED: SOP_REVIEWER 核准
    SUBMITTED --> REJECTED: SOP_REVIEWER 退件<br/>（必填退件原因）
    REJECTED --> SUBMITTED: 修改後重送
    DRAFT --> DELETED: 結案（軟刪除，final）
    SUBMITTED --> DELETED: 結案
    REJECTED --> DELETED: 結案
    APPROVED --> [*]: 系統批次原子搬移<br/>→ ticket 內每份文件 PUBLISHED
    DELETED --> [*]
```

### 核准後原子搬移流程（per ticket 內每份文件）

```mermaid
flowchart TD
    Start([ticket APPROVED]) --> Loop{ticket 內每份文件}
    Loop --> Lock[鎖定 DOC_ID<br/>避免並行上傳]
    Lock --> First{是否第一版 V1.0?}
    First -->|是| Move3
    First -->|否| Archive[舊最新檔重命名加版號<br/>移到 原目錄/歷史版本/]
    Archive --> Move3[待審查檔 → 原目錄/BASE_FILENAME<br/>取代最新版位置]
    Move3 --> Tx[DB transaction:<br/>DM_DOC_VERSION IS_CURRENT 切換<br/>+ DM_DOC.CURRENT_VERSION_ID<br/>+ DM_APPROVAL ACTION=APPROVE<br/>+ DM_AUDIT]
    Tx --> Unlock[釋放鎖]
    Unlock --> Notify[發訂閱通知]
    Notify --> Loop

    Tx -.->|失敗| Rollback[完整回滾<br/>檔案 + DB transaction<br/>釋放鎖<br/>標記 ticket FAILED<br/>由 admin 介入]
    Rollback --> AdminLog[寫 DM_AUDIT + DP_AUDIT_LOG]
```

### 同一文件多 ticket 並行處理

```mermaid
sequenceDiagram
    participant A as ticket A
    participant DOC as 文件 X (DOC_ID=001)
    participant B as ticket B

    Note over A,B: 兩張 ticket 同時包含 DOC_ID=001<br/>系統不檢查鎖定
    A->>DOC: ticket A 核准 → 觸發原子搬移
    DOC-->>A: 文件 STATUS=PUBLISHED
    Note over B: ticket B 仍為 SUBMITTED
    B->>DOC: ticket B 核准
    DOC-->>B: 該版本已 PUBLISHED → noop
    Note over B: 仍寫 DM_APPROVAL 動作歷程
```

> **詳細 Activity Diagram（送審者 / 審查者 swim lane）**：見 [UCDM006-文件審查作業流程.md](../../use-cases/dm/UCDM006-文件審查作業流程.md)（EA 匯出 PNG）

## 對應 RQ

- RQDM001（電子簽核與稽核軌跡）
- RQSS011（角色↔功能對應，SOP_REVIEWER 由 SS 端設定）

## 前置依賴

- US3（UCDM001 文件管理與版本管控）已完成；至少有一份 DRAFT 文件
- 使用者具 DM05 功能權限；核准 / 退件動作執行者具 SOP_REVIEWER 角色

## 角色卡點

| 操作 | 角色卡點 |
|------|---------|
| 建立審查單 / 加文件 / 送審 / 讀取 | 任一帳號 + DM05 功能權限 |
| **核准 / 退件** | **`SOP_REVIEWER` 硬卡點** |
| 自審 | **不限制**（同一人若兼具 SOP_REVIEWER 角色可核准自己送審的 ticket）|
| 退件範圍 | **僅 ticket 級別**（整批退），不可單一文件退件 |
