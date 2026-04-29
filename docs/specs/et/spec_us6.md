# User Story 6 — UCET005 邀請學員加入課程

> 返回總檔：[spec.md](spec.md) | 模組：教育訓練（ET） | UC：[UCET005](../../use-cases/et/UCET005-邀請學員加入課程.md)

管理者透過 Email 邀請或產生課程邀請碼，讓學員自行加入指定課程。

**Why this priority** (P2): 邀請是學員加入的主要管道，但管理者亦可手動加入或批次匯入作為替代方案。

**Independent Test**: 管理者輸入學員 Email → 系統寄出邀請信 → 學員點連結加入課程。

## Acceptance Scenarios

1. **Given** 一個既有課程，**When** 管理者於學員管理頁輸入 Email 清單並送出，**Then** 系統透過 eMail Server 寄發邀請信（含課程名稱、邀請連結、邀請碼）
2. **Given** 一個既有課程，**When** 管理者產生課程邀請碼，**Then** 系統顯示邀請碼供管理者自行發送
3. **Given** 管理者選擇手動加入，**When** 輸入學員帳號或批次匯入 CSV，**Then** Moodle 將該批學員加入課程
4. **Given** 邀請信送出，**When** SMTP 失敗，**Then** Moodle 顯示寄送失敗，可重新嘗試

## Activity Diagram（UC 內部流程）

```mermaid
flowchart TD
    Start([管理者進入學員管理頁]) --> Way{邀請方式}

    Way -->|Email 邀請| E1[輸入學員 Email 清單]
    E1 --> E2[Moodle 透過 SMTP 寄發邀請信<br/>含課程名 / 連結 / 邀請碼]
    E2 --> E3{SMTP 成功?}
    E3 -->|是| EndOK([結束 ✓])
    E3 -->|否| ERR[顯示寄送失敗<br/>可重試]
    ERR --> EndKO([結束 ✗])

    Way -->|產生邀請碼| C1[Moodle 產生邀請碼]
    C1 --> C2[管理者自行發送]
    C2 --> EndOK

    Way -->|手動加入| M1[輸入學員帳號<br/>或 CSV 批次匯入]
    M1 --> M2[Moodle 將學員加入課程]
    M2 --> EndOK

    classDef startEnd fill:#e8f5e9,stroke:#2e7d32,color:#000
    classDef action fill:#fff,stroke:#666,color:#000
    classDef decision fill:#fff8e1,stroke:#f57c00,color:#000
    classDef errorAction fill:#ffebee,stroke:#c62828,color:#000

    class Start,EndOK,EndKO startEnd
    class E1,E2,C1,C2,M1,M2 action
    class Way,E3 decision
    class ERR errorAction
```

## 對應 RQ

- RQET006（透過 Email 邀請或提供課程邀請碼）

## 前置依賴

- US2（UCET001 建立課程）已完成
- eMail Server（SMTP）已配置
