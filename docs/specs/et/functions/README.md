# ET 模組功能清單（Moodle LMS）

教育訓練模組採 **Moodle LMS** 作為平台，下列 19 個功能為 EA `usecase/ET-教育訓練/Moodle LMS` 下的 `Activity<<功能選項>>`，UC Step 的 classifier 指向這些功能。

每個功能後續獨立建立 SPEC（輸入/輸出、Moodle 原生 vs 客製、權限、整合細節等）。

## 功能對照表

| 編碼 | 名稱 | Moodle 路徑 | 關聯 UseCase |
|------|------|-------------|--------------|
| [ET01](ET01-建立編輯課程.md) | 建立/編輯課程 | Site administration → Courses → Add a new course | UCET001 |
| [ET02](ET02-上傳檔案資源.md) | 上傳檔案資源 | Course → Turn editing on → Add activity or resource → File | UCET002 |
| [ET03](ET03-頁面編輯器.md) | 頁面編輯器（混合媒材） | Add activity → Page | UCET002 |
| [ET04](ET04-章節格式編排.md) | 章節格式編排 | Course format → Topics format | UCET003 |
| [ET05](ET05-活動完成條件.md) | 活動完成條件 | Activity settings → Activity completion | UCET003, UCET008 |
| [ET06](ET06-存取限制.md) | 存取限制（前置條件） | Activity settings → Restrict access | UCET003 |
| [ET07](ET07-測驗活動.md) | 測驗活動 | Add activity → Quiz | UCET004 |
| [ET08](ET08-題庫管理.md) | 題庫管理 | Course → Question bank | UCET004 |
| [ET09](ET09-手動加入學員.md) | 手動加入學員 | Course → Participants → Enrol users | UCET005 |
| [ET10](ET10-自助註冊.md) | 自助註冊（邀請碼） | Course → Enrolment methods → Self enrolment | UCET005, UCET007 |
| [ET11](ET11-課程完成報表.md) | 課程完成報表 | Course → Reports → Course completion | UCET006 |
| [ET12](ET12-成績簿.md) | 成績簿 | Course → Grades | UCET006 |
| [ET13](ET13-學員儀表板.md) | 學員儀表板 | Dashboard | UCET010 |
| [ET14](ET14-課程頁面瀏覽.md) | 課程頁面瀏覽 | Course page | UCET003, UCET008 |
| [ET15](ET15-測驗作答.md) | 測驗作答 | Quiz → Attempt quiz | UCET009 |
| [ET16](ET16-個人成績查看.md) | 個人成績查看 | User menu → Grades | UCET010 |
| ~~ET17~~ | ~~Wiki 模組（SOP 文件）~~ | — | **已廢棄，改由 DM 模組 UCDM001 處理**（[詳](ET17-Wiki模組.md)）|
| ~~ET18~~ | ~~書籍模組（操作手冊）~~ | — | **已廢棄，改由 DM 模組 UCDM002 處理**（[詳](ET18-書籍模組.md)）|
| [ET19](ET19-寄發課程邀請信.md) | 寄發課程邀請信 | enrol_invitation Plugin | UCET005, UCET007 |
