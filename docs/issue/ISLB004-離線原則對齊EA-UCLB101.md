# ISLB004 — 離線原則對齊 EA UCLB101（移除健康檢查 + Timer 3 分鐘 + 以 Local 蓋中央）

**建立日期**: 2026-04-22
**優先順序**: HIGH
**類型**: 架構變更（修訂 R03）
**狀態**: 待 PG 實作（SA 側文件與 EA 模型已全部就緒）
**依據**: EA UCLB101 「離線原則」Rule（GUID `{2B94E1A9-8051-4083-BA45-80732128CA0C}`）

---

## 1. 背景

SA 文件（`spec.md` / `LBSB01-開發者指南.md` / `LBSB01-操作手冊.md` / `contracts/srv-contracts.md`）原本設計「健康檢查 ping + 60 秒自動重連」；與 EA UCLB101 「離線原則」Rule 不一致。以 EA UCLB 下 Diagram 為準，改為本 issue 所述規則。

### EA 離線原則原文（GUID `{2B94E1A9-8051-4083-BA45-80732128CA0C}`）

1. 沒有所謂 Login 動作，CALL API 一律用 Token，所以當使用 APILB 連不上中央 DB 時才會知道當下是離線。
2. 離線時要啟動 Timer 每 3 分鐘或按下 [更新] 時才去作 '同步' 動作；當 Call API 時才能得知目前是線上或是離線。
3. 建議不管線上或離線時，在 Call APILB 前就是先寫 Local DB，待連線時再 Sync 更新（一律以 Local DB 蓋中央 DB 即可），使離線時可修改印表機資料也可列印測試標籤。

---

## 2. 設計決策（對比 ISLB001）

| 項目 | ISLB001（舊設計） | 本 issue（新設計） |
|------|------------------|------------------|
| 線上/離線判定方式 | 啟動時及每 60 秒 ping `GET /api/health` | **不做獨立健康檢查**；以**實際 Call APILB 結果**判定 |
| 獨立健康檢查端點 | `HEALTH_CHECK_PATH`（硬寫常數） | **移除**；`login.py` 不再需要 `HEALTH_CHECK_PATH` 常數 |
| 離線時重試間隔 | 60 秒 | **3 分鐘**（OffLine Retry Timer）|
| 手動同步 | 無 | 主畫面 **[更新]** 按鈕 |
| 同步觸發時機 | 啟動、每 60 秒 ping、線上時每 30 秒背景 | **只有兩種**：OffLine Retry Timer 3 分鐘 / [更新] 按鈕 |
| 衝突處理 | 上線後全量從中央刷新 Local，以中央為準 | **一律以 Local DB 蓋中央 DB**（Local 為準）|
| Splash 文字 | 「正在檢查主系統連線 ...」 | 「正在啟動 ...」（或直接顯示主畫面）|

---

## 3. 實作範圍

### 3.1 `login.py`

- **刪除** `HEALTH_CHECK_PATH` 常數
- **刪除** `authenticate()` 中的 `urllib.request.urlopen(...{HEALTH_CHECK_PATH}...)` 健康檢查呼叫
- `authenticate()` 改為：只讀 `config.ini[site]` + 載入 `HARDCODED_TOKEN`，回傳 `Session(site_id, site_name, token, online=True, error_message='')`（`online` 預設 True，由首次實際 API 呼叫結果修正）
- `Session.online` 語意改為：「最近一次 Call APILB 的結果 — True=成功、False=失敗」

### 3.2 `main.py`

刪除舊重連機制，改為：

```python
OFFLINE_RETRY_INTERVAL_MS = 3 * 60 * 1000   # 3 分鐘（EA 離線原則 R03）

def __init__(self):
    ...
    self._retry_id = None  # OffLine Retry Timer 的 after id
    # 主畫面開啟後做一次首次同步（兼作開機連線探測）
    self.after(500, self._do_sync)

def _start_offline_retry_timer(self):
    """離線時啟動 OffLine Retry Timer（每 3 分鐘觸發 _do_sync）"""
    if self._retry_id is not None:
        self.after_cancel(self._retry_id)
    self._retry_id = self.after(OFFLINE_RETRY_INTERVAL_MS, self._do_sync)

def _stop_offline_retry_timer(self):
    if self._retry_id is not None:
        self.after_cancel(self._retry_id)
        self._retry_id = None

def _on_refresh_clicked(self):
    """主畫面 [更新] 按鈕：手動觸發同步"""
    self._do_sync()

def _do_sync(self):
    """唯一同步入口：replay PENDING_OPS → 依 API 回應判定線上/離線。"""
    ok = self._sync_local_to_db()   # 實際 Call APILB；回 True 代表至少一筆成功
    self.session.online = ok
    self._update_mode_display()
    if ok:
        self._stop_offline_retry_timer()
    else:
        self._start_offline_retry_timer()
```

**刪除**：
- 原 `_try_reconnect()`（60 秒重連）
- 原 30 秒背景同步 Timer（若有）
- Splash 「正在檢查主系統連線」提示（改為簡單啟動文字或直接進主畫面）

### 3.3 主畫面新增 **[更新]** 按鈕

- 位置：標題列右側、或訊息區上方（與標題【線上】/【離線】狀態標籤並排）
- 點擊呼叫 `_on_refresh_clicked()`
- 離線期間按下 → 觸發 `_do_sync()`；若回復線上，按鈕保留但 Timer 已停止

### 3.4 `local_db.py`

- **衝突處理改為「以 Local 蓋中央」**：
  - INSERT 衝突（中央已有同 PK）→ 改走 UPDATE（upsert），以 Local 值蓋中央
  - DELETE 回 404（中央已無）→ 視為成功，標記 STATUS=1
  - UPDATE 回 404 → 改走 INSERT（upsert），以 Local 值寫入中央
- **刪除** `_sync_local_to_db` 結尾的「從中央全量刷新 Cache」段落（如有）：不再用中央值覆蓋 Local

### 3.5 `config.ini`

無變更（`[site]` 保持；原本就不再有 `[token]` / `[api]`）。

---

## 4. 文件變更範圍（已同步更新）

已同步更新的 SA 文件：

| 文件 | 變更重點 |
|------|---------|
| `docs/specs/lb/spec.md` | L19 核心特性：移除健康檢查；Timer 60 秒 → 3 分鐘；新增「一律以 Local DB 蓋中央 DB」 |
| `docs/specs/lb/LBSB01-開發者指南.md` | §2.4 / §4 / §5 / §6 / §7 / §8 全面改寫；移除 `HEALTH_CHECK_PATH`；重寫 §6.4 為「OffLine Retry Timer + [更新]」|
| `docs/specs/lb/LBSB01-操作手冊.md` | §2.1~2.4 / 附錄 A：移除健康檢查敘述；新增 [更新] 按鈕說明；Timer 3 分鐘 |
| `docs/specs/lb/contracts/srv-contracts.md` | 移除「健康檢查端點（待主專案定義）」小節，改為「離線偵測規則」 |
| ~~`docs/specs/lb/images/offline-reconnect.mmd` + `.png`~~ | 已廢除（2026-04-22）：mermaid 衍生 PNG 全面移除，改以 `uclb101-flow.png` 為離線流程權威圖 |
| `docs/specs/lb/images/uclb001-flow.png` | 由 EA `UCLB001-標籤列印使用案例` Diagram 重匯（原 `LBL001`，已改名 + 改 Type 為 Activity）|
| `docs/specs/lb/images/uclb002-usecase.png` | 由 EA UCLB002 UseCase Diagram 匯出 |
| `docs/specs/lb/images/uclb002-flow.png` | 由 EA UCLB002 Activity Diagram 匯出 |
| `docs/specs/lb/images/uclb101-flow.png` | 由 EA UCLB101 Activity Diagram 匯出（含 OffLine Retry Timer、離線原則 Rule，為離線流程權威圖）|
| `docs/specs/lb/images/srvlb001-architecture.png` | 由 EA `SRVLB001-標籤列印通用API` CompositeStructure Diagram 匯出 |

---

## 5. EA 側人工處理項目

全部已完成（2026-04-22）：

| # | 項目 | 狀態 |
|---|------|------|
| Q1a | `LBL001-標籤印出案例` Diagram 改名為 `UCLB001-標籤列印使用案例` | ✅ 完成（MCP 改名）|
| Q1b | 同 Diagram Type 由 `Use Case` 改為 `Activity` | ✅ 完成（EA GUI 手動）|
| Q2 | LBL001 左側大 Block 用途 — 確認為 Drill-Down 到 `SRVLB001-標籤列印通用API` CompositeStructure | ✅ 維持現狀（合理設計）|
| Q3 | 5 個印表機 CRUD Step — 確認 Classifier 已指向對應 APILB001~005（`<<API>>`）| ✅ 維持現狀（合理設計）|
| Q4 | `LBSB01 專用Token` Data → 拉 `Dependency<<IN>>` 到 `接收列印指令 StepN` | ✅ 完成（MCP 新增 connector `1776848339`）|
| Q5 | UCLB002 Activity 泳道 — 確認 `BMS使用者` DEP 已存在 (GUID `{528DB43D-A799-4f1b-B3FC-64F3FF39BAFA}`) | ✅ 維持現狀（本就有）|
| Q6 | UCLB101 的 `On Line QUEUE` / `Off Line QUEUE` Step Classifier 指向新建的 `Activity<<Data>>` 物件 | ✅ 完成（新建 `Online Queue` id 588021784、`Offline Queue` id -1650599665）|
| Q7 | UCLB101 的「補印」Step | ✅ 使用者採納（改 `<<Flow>>` 指 UCLB002 或刪除）|

另外同批處理：
- `ET-教育訓練 UseCase` Diagram 改名為 `ET-教育訓練`（與 Parent Collaboration 同名）✅

---

## 6. 業務邏輯補充說明（SA 本次討論整理，供 PG 實作參考）

本 issue 主軸是「離線原則」，但過程中釐清了幾個**容易被誤解的業務邏輯點**，在此集中列出。每條都是完整需求語意，PG 實作時需一併遵守。

### 6.1 同步時機「只有兩個入口」

```
_do_sync()  ←──────┬── OffLine Retry Timer 到期（3 分鐘一次，離線時才啟動）
                   └── 使用者按主畫面 [更新] 按鈕
```

**不可**加其他自動觸發來源（例如：啟動後每 N 秒、接收到 Task 後、印表機設定變更後）。若需要在開機時試連一次，就走「主畫面開啟完成後呼叫一次 `_do_sync()`」，不另建 Timer。

### 6.2 「一律以 Local DB 蓋中央 DB」的具體含義

不是單純「上線後推 Local 到中央」，而是 **Local 即為最終真相、中央只是異地備份**：

| 情境 | 動作 |
|------|------|
| Local 新增一筆印表機 → 中央已有同 ID | **以 Local 的欄位值 upsert 蓋中央**（不因中央已有就放棄）|
| Local 修改一筆 → 中央值較新 | **以 Local 蓋中央**（不走「以中央為準」的衝突解析）|
| Local 刪除一筆 → 中央已無 | DELETE 回 404 **視為成功**（Local 想刪，中央已無 = 目的達成）|
| 中央多出一筆 Local 沒有的資料 | **不動** Local（不做「上線後全量刷回 Local」）|

> 設計理由：LBSB01 駐在 Site 端，使用者只在這台機器上改印表機 / 列印，Local 的資料就是最新；中央只是讓其他 Site / 查詢功能可以看到。

### 6.3 SRVLB001 格式一 vs 格式二（補印）

中央 SRVLB001 以傳入參數判格式：

| 格式 | 必填 | 使用情境 | 中央處理 |
|------|------|---------|---------|
| 格式一 | `bar_type` + `site_id` + `data_*`（client_ip 由 HTTP 自動取） | BC/CP/BS/TL 一般列印 | Call SRVDP010(client_ip, bar_type) 解析 PRINTER_ID + SERVER_IP + params；data_* 由 Client 傳入 |
| 格式二 | `printer_id` + `log_uuid` | UCLB002-LBSR01 補印 | 讀 LB_PRINT_LOG(log_uuid) 取回**原** BAR_TYPE + data_\*（**Client 不重傳**）；讀 LB_PRINTER(printer_id) 取 SERVER_IP + params |

**PG 注意**：補印時 `printer_id` **可以跟原紀錄不同**（使用者指定新的印表機），但 `bar_type` + `data_*` 一定是原紀錄（不重傳）。中央會 `INSERT LB_PRINT_LOG 新 UUID`（非 UPDATE 原紀錄），可由 `RES_ID` 欄位追溯原 log_uuid。

### 6.4 `PRINTER_ID = "USB"` 保留字

代表「Client 端的本機 USB 印表機」。遇到這個值時：
- SRVDP010：**跳過 LB_PRINTER 查詢**，`server_ip` / `printer_params` 回傳空白
- APILB007 新增 LOG：**跳過 LB_PRINTER 存在性驗證**
- Client 端：自行走 USB 直連輸出路徑（**不經 LBSB01 HTTP Listener**）

不要把 "USB" 當普通 PRINTER_ID 處理、不要對它做 LB_PRINTER JOIN。

### 6.5 Queue 不阻塞策略

Online Queue 中某筆 Task 送至印表機失敗（印表機故障 / 卡紙 / 離線）時：

1. 該 Task **自動移至 Offline Queue**（Status 0 → 2、RESULT 寫入失敗備註）
2. **Online Queue 繼續消化下一筆 Task**，不停擺
3. 使用者排除印表機故障後，**手動**（雙擊）將 Offline Queue 的 Task 移回 Online Queue 重列；或直接於 Offline 區變更指定印表機後移回

**PG 注意**：不要實作「重試 N 次才移至 Offline」之類的自動重試邏輯 — 使用者明確要求「一次失敗就移出，不要卡隊」。

### 6.6 Auto 自動列印 vs 手動列印（主畫面 Auto CheckBox）

| Auto 狀態 | 明細區行為 | 指定印表機欄 | 列印按鈕 |
|-----------|----------|--------------|---------|
| **未勾**（手動）| 顯示**使用者點選的** Queue Task 明細 | 可下拉覆寫（僅影響選中那筆）| 啟用，按下列印該筆 |
| **已勾**（自動）| 顯示**系統正在列印的**那筆（隨 Queue 消化切換）| Disabled（不可覆寫）| Disabled（不可按）|

### 6.7 「固定參數」CheckBox（紙張輸出規格區）

勾選行為：

| 狀態 | 紙張規格欄位（標籤類型 / 尺寸 / 寬 / 高 / 左位移 / 上位移 / 明暗）|
|------|-------|
| **未勾**（預設）| 自動反映目前選中 Task：標籤類型 → 帶入尺寸；指定印表機 → 查印表機設定檔帶入左/上位移/明暗 |
| **已勾**（固定）| 所有欄位**凍結不自動更新**，操作者可手動改；列印時使用**畫面上當時的值**（非自動帶入值）|

勾選「固定參數」時，RESULT 字串會多帶一個 `F`（例 `v1.1r1-FW80H35L40T0D8`）以供稽核追溯。

### 6.8 RESULT 備註代碼（Status 變更的旁敘述）

| 備註 | 意義 | Status |
|------|------|--------|
| `W..H..L..T..D..`（純參數）| 列印成功 | 0/2 → 1 |
| `-OffLine` | 工作被移至離線區（手動 或 列印失敗自動搬）| → 2 |
| `-OnLine` | 工作從離線區移回線上 | 2 → 0 |
| `-Delete` | Online 區人工刪除 | 0 → 1 |
| `-Off_DEL` | Offline 區人工刪除 | 2 → 1 |

**一律透過 `local_db.build_result()` 組裝**，不自行拼字串（避免格式不一致）。

### 6.9 訊息區同步顯示 Log 的範圍（R06）

- `_log_msg(text)`：同時寫 Log 檔 + 主畫面訊息區（系統訊息：Login / Logout / 重連成功 / 同步完成 / 系統異常）
- `_add_msg(text)`：**只寫**訊息區（操作訊息：列印結果、佇列變更）

原則：**凡 Log 有記錄的系統訊息一律同步顯示給操作者**，讓操作者在訊息區就能看到系統運作狀態，不必去翻 Log 檔。

### 6.10 標籤測試頁走同條 Task Listener 路徑

測試頁（`sample_data_print.py`）**不另開獨立列印通道**：
- 測試頁送件 → `POST http://localhost:9200/api/lb/task`（本機迴路）
- Body 固定 `status = 2` → 直接進 **Offline Queue**（不影響 Online 正式排隊）
- 測試結果在主畫面 Offline Queue 區可見、可手動移回 Online Queue 重印

好處：驗證整條 Listener → local.db → Queue → GUI 路徑一次到位；測試不干擾正式作業。

---

## 7. 驗收標準

- [ ] `login.py` 無 `HEALTH_CHECK_PATH` 常數、無 `GET /api/health` 呼叫
- [ ] `main.py` 無 60 秒 / 30 秒 Timer；僅 3 分鐘 OffLine Retry Timer
- [ ] 主畫面有 **[更新]** 按鈕，按下會觸發 `_do_sync()`
- [ ] 離線時中斷網路 → 程式可繼續操作 Queue / 印表機設定 / 測試頁
- [ ] 回復網路後，3 分鐘內 Timer 自動同步；或立即按 [更新] 也能同步
- [ ] 同步策略驗證：離線期間修改一筆印表機（Local），上線後該筆值**蓋到中央**（非相反）
- [ ] DELETE 目標在中央已不存在 → 回 404 視為成功、STATUS=1
- [ ] UPDATE 目標在中央已不存在 → 改走 INSERT（upsert），成功
- [ ] Log 記錄：回復線上時 `INFO: 回復線上，已同步 N 筆 PENDING_OPS`

### 業務邏輯驗收（對應 §6 補充說明）

- [ ] 同步僅由 Timer（3 分鐘）或 [更新] 按鈕觸發，無其他自動入口（§6.1）
- [ ] 衝突測試：Local vs 中央同時改同一筆 → 上線後中央值 = Local 值（§6.2）
- [ ] 補印（UCLB002 格式二）：Client 只傳 `printer_id + log_uuid`，中央自行從 LB_PRINT_LOG 取回 `bar_type + data_*`，可指定新印表機（§6.3）
- [ ] `PRINTER_ID="USB"` 保留字：不經 LBSB01 Listener，Client 走 USB 直連（§6.4）
- [ ] Queue 不阻塞：印表機故障時該筆自動移至 Offline Queue，下一筆繼續列印（§6.5）
- [ ] Auto 勾選時：明細區隨佇列消化切換、指定印表機欄與列印按鈕皆 Disabled（§6.6）
- [ ] 固定參數勾選時：紙張規格欄位凍結 + RESULT 多 `F` 旗標（§6.7）
- [ ] RESULT 組字串一律透過 `local_db.build_result()`（§6.8）
- [ ] 訊息區：Login / Logout / 重連成功 / 同步完成同時顯示在訊息區與 Log 檔（§6.9）
- [ ] 測試頁走 `POST localhost:9200`（非獨立通道），Task 進 Offline Queue（§6.10）
