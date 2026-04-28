# LB 專案規則

LB（標籤列印）為 TSBMS 周邊獨立應用：本機 Python 服務（LBSB01）+ 中央 LB_TBMS（FastAPI + React）。本檔記錄協作 / 文件規範；技術細節見各 `docs/specs/lb/*` 與 `docs/use-cases/lb/*`。

## 協作提示詞參考

撰寫 SA / 規格文件、整理需求 / UseCase、產出 speckit 文件時，請先參考 `_refs/提示詞參考.md`（自 SA 專案同步），維持團隊產出格式一致。

## 跨 Repo 同步規範

- **lb 模組同步**：`_LB/docs/specs/lb/` 與 `TBMS/docs/specs/lb/` 必須同步（`contracts/` 除外，兩邊視角不同）。
- **SS / DM / ET 模組規格**：以主專案 `TBMS/docs/specs/` 為準；本 repo 之相關引用以路徑文字註明（不寫跨 repo 超連結）。

## docs 目錄結構

- `docs/requirements/` — 需求文件（RQET / RQDM 等本 repo 維護的子集）
- `docs/use-cases/{模組}/` — 各模組 UseCase 文件 + per-UC PNG（一 UC 一檔）
- `docs/specs/lb/` — LB 模組正式規格（與 TBMS 同步）
- `docs/specs/dm/`、`docs/specs/et/` — DM / ET 規格在本 repo 的版本
- `docs/issue/` — LB 端 Issue 記錄（編碼 ISLB{三位流水號}）

## 編碼規則

依 SA 專案統一規範（`{前綴}{模組代碼}{流水號}`，模組代碼見 SA 專案 `CLAUDE.md` §需求代碼）。

## Push 流程

「PUSH」於本 repo = `git pull --rebase` → 處理 MERGE → `git push`。先 sync 再 push，避免衝突。
