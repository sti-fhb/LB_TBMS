# User Story 8 — UCET007 加入課程（學員）

> 返回總檔：[spec.md](spec.md) | 模組：教育訓練（ET） | UC：[UCET007](../../use-cases/et/UCET007-加入課程.md)

學員從 Email 取得邀請碼通知信，輸入邀請碼或點選邀請連結加入指定課程；系統驗證邀請碼有效性。

**Why this priority** (P1): 學員加入課程是後續學習的前置條件。

**Independent Test**: 學員以邀請碼加入後，課程列表即顯示該課程。

## Acceptance Scenarios

1. **Given** 管理者已寄發邀請信，**When** 學員開啟信件並點選邀請連結，**Then** Moodle 驗證邀請碼有效性後顯示課程資訊，學員確認加入
2. **Given** 學員已登入 Moodle（透過 SS），**When** 直接於 Moodle 輸入邀請碼，**Then** Moodle 驗證後顯示課程資訊
3. **Given** 邀請碼無效或已過期，**When** 學員嘗試加入，**Then** Moodle 提示具體錯誤
4. **Given** 學員已加入課程，**When** 進入「我的學習」頁面，**Then** 課程列表顯示該課程

## Activity Diagram（UC 內部流程）

```mermaid
flowchart TD
    Start([學員收到邀請信]) --> Way{加入方式}

    Way -->|點選邀請連結| L1[Moodle 驗證邀請碼有效性]
    Way -->|登入後輸入邀請碼| L2[Moodle 驗證]

    L1 --> Verify{邀請碼有效?}
    L2 --> Verify

    Verify -->|有效| Show[顯示課程資訊]
    Verify -->|無效 / 過期| Err[Moodle 提示具體錯誤]
    Err --> EndKO([結束 ✗])

    Show --> Confirm[學員確認加入]
    Confirm --> Joined[加入課程<br/>「我的學習」頁面顯示]
    Joined --> EndOK([結束 ✓])

    classDef startEnd fill:#e8f5e9,stroke:#2e7d32,color:#000
    classDef action fill:#fff,stroke:#666,color:#000
    classDef decision fill:#fff8e1,stroke:#f57c00,color:#000
    classDef errorAction fill:#ffebee,stroke:#c62828,color:#000

    class Start,EndOK,EndKO startEnd
    class L1,L2,Show,Confirm,Joined action
    class Way,Verify decision
    class Err errorAction
```

## 對應 RQ

- RQET006（學員端：邀請碼 / 邀請連結加入課程）

## 前置依賴

- US1（UCET013 登入）已完成
- US6（UCET005 邀請學員）已寄發邀請信 / 邀請碼
