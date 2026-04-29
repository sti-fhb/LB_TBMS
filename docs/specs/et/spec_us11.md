# User Story 11 — UCET010 查看個人學習進度

> 返回總檔：[spec.md](spec.md) | 模組：教育訓練（ET） | UC：[UCET010](../../use-cases/et/UCET010-查看個人學習進度.md)

學員於「我的學習」儀表板檢視各課程完成百分比與測驗成績。

**Why this priority** (P3): 自我追蹤功能為輔助工具，非首要需求。

**Independent Test**: 學員至少加入一門課程並完成部分章節後，儀表板顯示對應進度。

## Acceptance Scenarios

1. **Given** 學員已加入至少一門課程，**When** 進入「我的學習」儀表板，**Then** Moodle 顯示各課程完成百分比
2. **Given** 學員已參加測驗，**When** 查看儀表板測驗成績區，**Then** Moodle 顯示各測驗最佳成績
3. **Given** 學員點選某課程，**When** 進入課程頁，**Then** 可從上次離開處繼續學習

## Activity Diagram（UC 內部流程）

```mermaid
flowchart TD
    Start([學員進入「我的學習」儀表板]) --> Show[Moodle 顯示各課程完成百分比]
    Show --> Choice{操作}
    Choice -->|查看測驗成績| Q[顯示各測驗最佳成績]
    Choice -->|繼續學習| Continue[點選某課程<br/>從上次離開處繼續]
    Q --> End([結束])
    Continue --> End

    classDef startEnd fill:#e8f5e9,stroke:#2e7d32,color:#000
    classDef action fill:#fff,stroke:#666,color:#000
    classDef decision fill:#fff8e1,stroke:#f57c00,color:#000

    class Start,End startEnd
    class Show,Q,Continue action
    class Choice decision
```

## 對應 RQ

- 無直接 RQET 對應（屬學員端輔助功能，分析資料新增）

## 前置依賴

- US8（UCET007 加入課程）已完成
- US9 / US10 已產生學習進度與測驗成績資料
