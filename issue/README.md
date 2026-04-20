# LB Issue 目錄

記錄 LB 模組的設計變更 / 待實作項目，供 PG 實作參考。

## 編碼規則

| 編碼 | 用途 |
|------|------|
| `ISLB{三位流水號}` | Issue 編碼，如 `ISLB001`、`ISLB002` |

- 依建立順序遞增，**不可重複使用**
- 已結案的 Issue 編碼保留不動（不重新編號）
- 檔名格式：`ISLB{seq:03}-{簡短標題}.md`

## Issue 模板

每一份 Issue 至少包含：

1. **背景** — 為何要做這個變更
2. **設計決策** — 決定了什麼
3. **實作範圍** — 哪些檔案要改，怎麼改
4. **驗收條件** — checklist
5. **相依** — 主專案或其他模組待辦
6. **相關文件** — 連結到對應 SPEC / 規格書
7. **不在範圍** — 明確排除的事項

## Issue 清單

| 編碼 | 標題 | 優先 | 狀態 |
|------|------|------|------|
| [ISLB001](ISLB001-TOKEN與中央URL硬寫變更.md) | TOKEN 與中央 URL 硬寫變更 | HIGH | 待實作 |
| [ISLB002](ISLB002-CP11-移除-data-8-13-14-15.md) | CP11 移除 DATA_8/13/14/15 + CP19 移除 DATA_13 | MEDIUM | 待實作 |
| [ISLB003](ISLB003-CP01-移除-data-4-6-8-11.md) | CP01 標籤移除 DATA_4 / 6 / 8 / 11 | MEDIUM | 待實作 |

## 與 `project_lb_unimplemented.md` 的關係

| 檔案 | 用途 |
|------|------|
| `memory/project_lb_unimplemented.md` | 總覽清單（Claude memory，給後續對話參考） |
| `issue/ISLBxxx.md` | 單一 Issue 詳細規格（給 PG 實作依據） |

總覽清單條目若有獨立 Issue，可互相引用。
