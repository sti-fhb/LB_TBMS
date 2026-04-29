# User Story 3 — UCLB101 LBSB01 內部運作（離線、同步、狀態回報）

> 返回總檔：[spec.md](spec.md) | 模組：標籤列印（LB）

LBSB01 程式的內部運作模型：啟動時處理未同步資料、常駐 Task Listener 接收中央派送、以 Retry Timer 補同步（離線偵測）、將狀態變更事件 append-only 地回寫中央（APILB006/007）。所有「離線行為」集中由 **EA Rule 「離線原則」**（GUID `{2B94E1A9-8051-4083-BA45-80732128CA0C}`）定義，詳見總檔 [§離線原則](spec.md#離線原則r03)。

**Why this priority**: Client 列印（[US1](spec_us1.md)）與歷史補印（[US2](spec_us2.md)）成功的前提，是 LBSB01 能在斷網、LBSB01 重啟、印表機故障等任何失常情境下仍**不遺失任何指令或狀態**。本 Story 規範 LBSB01 端的持久化與恢復行為，是整個 LB 模組可靠性的骨幹。

**Independent Test**:
- 關閉中央 → LBSB01 應在下一次 Call APILB 失敗時切換顯示為「離線」（綠燈→紅燈）
- 離線時啟動 Timer → 3 分鐘到或使用者按 [更新] → 執行同步 → 若 Call API 成功即視為線上（自動切回綠燈）
- 離線中對本地做的任何異動（印表機資料、列印狀態、測試頁列印）→ 寫 Local DB + 排 PENDING_OPS → 恢復連線後依 SEQ 順序 replay 回中央
- 模擬斷電 LBSB01：重啟後應自動處理 `PENDING_OPS` 內所有待同步項目

## Acceptance Scenarios

1. **Given** LBSB01 啟動，**When** 偵測 `PENDING_OPS` 有資料，**Then** 先嘗試補送未同步項目（以 SEQ 順序 replay 至 APILB006/007），成功者移除該筆
2. **Given** LBSB01 常駐 Task Listener（port 9200），**When** 收到中央 POST `/api/lb/task`，**Then** 驗證 Bearer Token、寫入 local.db（依 status 放 Online Queue 或 Offline Queue）、通知 GUI 刷新
3. **Given** 目前狀態為「線上」，**When** Call APILB 失敗（連線拒絕 / 逾時 / 5xx），**Then** 切為「離線」、啟動 Retry Timer（每 3 分鐘）、主畫面標題列 + 狀態標籤變紅
4. **Given** 目前狀態為「離線」，**When** Timer 到時或使用者按 [更新]，**Then** 執行同步：replay `PENDING_OPS`；若 Call API 成功即視為回復線上（靜默切回綠燈、停止 Timer）
5. **Given** 離線中完成列印，**When** 更新狀態，**Then** `local_db.update_print_log(uuid, status=1, result=...)` 立即更新 Local Cache，同時排一筆 `PENDING_OPS(op=UPDATE, target=LB_PRINT_LOG)`
6. **Given** 離線中新增 / 修改印表機，**When** 操作完成，**Then** 寫 Local Cache（標記「待同步」），排 `PENDING_OPS` 對應到 APILB003 / APILB004 / APILB005
7. **Given** LBSB01 與中央同時對同一 `LB_PRINTER` 有異動，**When** 上線後 replay，**Then** 採「**一律以 Local DB 蓋中央 DB**」策略（參見離線原則 R03 第 3 條）
8. **Given** LBSB01 的 Online Queue 有 Task 正在列印，**When** 印表機故障導致失敗，**Then** 該筆 Task 自動移入 Offline Queue（狀態碼 2），呼叫 APILB006 回報 `status=2, result_memo=OffLine`；Online Queue 不阻塞、繼續消化下一筆
9. **Given** 離線時產生的列印成功事件，**When** 同步到中央後，**Then** 中央 `LB_PRINT_LOG.STATUS` 由 0 → 1，`RESULT` 依 `local_db.build_result()` 格式寫入（如 `v1.1r1-W80H35L40T0D8`）
10. **Given** Online/Offline Queue 都持久化於 local.db（SQLite），**When** LBSB01 斷電重啟，**Then** Queue 內容完整還原，列印不中斷

## Activity Diagram（UC 內部流程）

```mermaid
flowchart TD
    Start([LBSB01 啟動]) --> Init[初始化]
    Init --> CheckPending{PENDING_OPS<br/>有資料?}
    CheckPending -->|是| Replay[依 SEQ 順序 replay<br/>呼叫 APILB006/007]
    Replay --> Listen
    CheckPending -->|否| Listen[啟動常駐 Task Listener<br/>:9200/api/lb/task]
    Listen --> Wait{事件}

    Wait -->|收到 POST Task| RecTask[驗證 Bearer Token<br/>寫 local.db<br/>通知 GUI 刷新]
    Wait -->|列印完成| UpdLog[更新 LB_PRINT_LOG<br/>STATUS=1, RESULT=...]
    Wait -->|印表機故障| Move[Task 移入 Offline Queue<br/>STATUS=2]
    Wait -->|Call API 失敗| Offline[切「離線」紅燈<br/>啟動 Retry Timer 3 分]

    RecTask --> WriteLog[排 PENDING_OPS<br/>背景 Thread Call APILB007]
    UpdLog --> WriteLog2[排 PENDING_OPS<br/>背景 Thread Call APILB006]
    Move --> WriteLog3[排 PENDING_OPS<br/>Call APILB006 status=2]

    Offline --> Timer{Timer 到 / 使用者按 [更新]?}
    Timer -->|是| Sync[執行同步<br/>replay PENDING_OPS]
    Sync --> SyncResult{Call API 成功?}
    SyncResult -->|是| Online[切回「線上」綠燈靜默<br/>停止 Timer]
    SyncResult -->|否| Offline

    WriteLog --> Wait
    WriteLog2 --> Wait
    WriteLog3 --> Wait
    Online --> Wait

    classDef startEnd fill:#e8f5e9,stroke:#2e7d32,color:#000
    classDef action fill:#fff,stroke:#666,color:#000
    classDef decision fill:#fff8e1,stroke:#f57c00,color:#000
    classDef errorAction fill:#ffebee,stroke:#c62828,color:#000

    class Start startEnd
    class Init,Replay,Listen,RecTask,UpdLog,Move,WriteLog,WriteLog2,WriteLog3,Sync,Online action
    class CheckPending,Wait,Timer,SyncResult decision
    class Offline errorAction
```

## 關聯 UseCase 與 API

| 項目 | 說明 |
|------|------|
| UseCase | UCLB101 — LBSB01 內部功能流程 |
| 對外 API（狀態回報）| [APILB006](./contracts/APILB006.md)（回報列印事件），[APILB007](./contracts/APILB007.md)（進件寫 LOG） |
| 中央入口 | 收 Task：LBSB01 Listener `:9200/api/lb/task`（由中央 SRVLB001 POST 進來） |
| EA Rule | 「離線原則」GUID `{2B94E1A9-8051-4083-BA45-80732128CA0C}` |

## 三層 Queue 架構

```
                    ┌─────────────────────┐
  API 傳入指令 ──→  │  1. Online Queue     │ ──→ 印表機列印
                    │     (本地暫存)       │
                    └──────────┬──────────┘
                               │ 可搬移
                    ┌──────────▼──────────┐
                    │  2. Offline Queue    │ ──→ 印表機列印
                    │     (本地暫存)       │
                    └─────────────────────┘

  指令進入/異動/完成/刪除 ──→  ┌──────────────────────┐
                              │  3. DB Log Queue      │ ──→ Call API 寫入中央 DB
                              │     (本地暫存,         │
                              │      背景非同步消化)    │
                              └──────────────────────┘
```

**為什麼 Queue 不實作在中央 DB？** — 斷網時 Local LAN 仍通，LBSB01 仍可驅動印表機列印；Queue 若在中央則斷網就無法取得待印資料。Queue 在 Local SQLite 保證斷網/斷電皆可復原。

## 指令生命週期與 DB Log 記錄時機

```
API 傳入指令
  │
  ├─→ 寫入 Online Queue（本地 SQLite）
  ├─→ 寫入 DB Log Queue（ACTION=RECEIVED）
  │     └─→ 背景 Thread → Call APILB007 寫入中央 DB
  │
  ▼ Online Queue 消化列印
  │
  ├─ 列印成功 ──→ 從 Online Queue 移除
  │               └─→ DB Log Queue（ACTION=PRINTED）→ APILB006
  │
  ├─ 列印失敗（印表機故障）──→ 自動移至 Offline Queue
  │                            └─→ DB Log Queue（ACTION=PRINT_FAILED, MOVED_OFFLINE）→ APILB006
  │                            ※ 不阻塞，Online Queue 繼續消化下一個 Task
  │
  ▼ Offline Queue 中的 Task
  │
  ├─ 故障排除 → 操作者移回 Online Queue → DB Log Queue（ACTION=MOVED_ONLINE）→ APILB006
  ├─ 變更印表機 → DB Log Queue（ACTION=MODIFIED）→ APILB006
  └─ 刪除       → DB Log Queue（ACTION=DELETED）→ APILB006
```

## PENDING_OPS（離線異動佇列）

離線時所有寫入操作先寫 Local DB，並排入 `PENDING_OPS` table，上線後依 SEQ 順序 replay：

| 操作類型 | 目標 Table | 中央對應 API |
|---------|-----------|------------|
| INSERT LB_PRINT_LOG | `LB_PRINT_LOG` | APILB007 |
| UPDATE LB_PRINT_LOG（status + result）| `LB_PRINT_LOG` | APILB006 |
| INSERT LB_PRINTER | `LB_PRINTER` | APILB003 |
| UPDATE LB_PRINTER | `LB_PRINTER` | APILB004 |
| DELETE LB_PRINTER | `LB_PRINTER` | APILB005 |

## 狀態機（LBSB01 視角）

| 狀態 | 顯示 | 觸發切換 |
|------|------|---------|
| 線上 | 綠燈 | 初始，或離線後 Call APILB 成功 |
| 離線 | 紅燈 | Call APILB 失敗（連線拒絕 / 逾時 / 5xx）|

離線→線上採**靜默切換**，無額外連線測試，同步動作本身即為下一次 Call API。
