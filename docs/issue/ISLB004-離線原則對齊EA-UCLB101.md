# ISLB004 — 離線原則對齊 EA UCLB101（移除健康檢查 + Timer 3 分鐘 + 以 Local 蓋中央）

**建立日期**: 2026-04-22
**優先順序**: HIGH
**類型**: 架構變更（修訂 R03）
**狀態**: 待實作
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
| `docs/specs/lb/images/offline-reconnect.mmd` + `.png` | 重繪流程：首次同步 → API 成功? → 線上/離線；離線時 3 分鐘 Timer + [更新] 兩個觸發源 |
| `docs/specs/lb/images/uclb001-flow.png` | 由 EA `UCLB001-標籤列印使用案例` Diagram 重匯（原 `LBL001`）|
| `docs/specs/lb/images/uclb002-usecase.png` | 新增，由 EA UCLB002 UseCase Diagram 匯出 |
| `docs/specs/lb/images/uclb002-flow.png` | 由 EA UCLB002 Activity Diagram 重匯 |
| `docs/specs/lb/images/uclb101-flow.png` | 由 EA UCLB101 Activity Diagram 重匯（權威離線流程圖）|

---

## 5. EA 側需手動處理（SA 責任）

以下項目需要在 EA GUI 手動處理（MCP SQL 為唯讀，無法改 Diagram Type）：

1. **LBL001 Diagram 改 Type**：
   - Diagram: `UCLB001-標籤列印使用案例`（Diagram_ID `-1717655739`，已改名）
   - Type 目前：`Use Case`
   - 應改為：`Activity`（內容為 Step / ControlFlow 活動流程）
   - 操作：EA 中開啟該 Diagram → Right-click → Properties → Type 改為 `Activity`
   - 改完後重匯 `uclb001-flow.png`

2. **UCLB 其他圖內微調**（Q2~Q7，與本 issue 不衝突時可緩處理）：
   - Q2：LBL001 左側大 Block 的用途／補文字
   - Q3：印表機 CRUD 五個 Step 是否改 `<<功能選項>>` 或補 ControlFlow
   - Q4：`LBSB01 專用Token` Data 物件 → 拉 `Dependency<<IN>>` 到 StepN
   - Q5：UCLB002 Activity 是否補 DEP 泳道
   - Q6：UCLB101 的 `On Line QUEUE` / `Off Line QUEUE` 改 `<<Data>>` / `<<object>>`
   - Q7（已採用）：UCLB101 的「補印」Step 改為 `<<Flow>>` 指 UCLB002 或刪除

---

## 6. 驗收標準

- [ ] `login.py` 無 `HEALTH_CHECK_PATH` 常數、無 `GET /api/health` 呼叫
- [ ] `main.py` 無 60 秒 / 30 秒 Timer；僅 3 分鐘 OffLine Retry Timer
- [ ] 主畫面有 **[更新]** 按鈕，按下會觸發 `_do_sync()`
- [ ] 離線時中斷網路 → 程式可繼續操作 Queue / 印表機設定 / 測試頁
- [ ] 回復網路後，3 分鐘內 Timer 自動同步；或立即按 [更新] 也能同步
- [ ] 同步策略驗證：離線期間修改一筆印表機（Local），上線後該筆值**蓋到中央**（非相反）
- [ ] DELETE 目標在中央已不存在 → 回 404 視為成功、STATUS=1
- [ ] UPDATE 目標在中央已不存在 → 改走 INSERT（upsert），成功
- [ ] Log 記錄：回復線上時 `INFO: 回復線上，已同步 N 筆 PENDING_OPS`
