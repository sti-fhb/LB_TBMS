# User Story 1 — UCDM004 DM 登入（SS）

> 返回總檔：[spec.md](spec.md) | 模組：文件管理（DM） | UC：[UCDM004](../../use-cases/dm/UCDM004-DM%20登入.md)

使用者於 DM 獨立登入頁輸入 SS 帳密；DM 透過 SS 認證 API（APISS001）取 Token + 角色 + 可用功能後建立 session；後續每次請求呼叫 APISS002 驗 Token。**不啟用 MFA**（DM 主要為文件查閱，敏感度較低）。

**Why this priority** (P1): 身分驗證為一切作業的入口，無此即 DM 不可用。

**Independent Test**: SS 帳密正確 → DM 進入主頁；帳密錯誤 → SS 回 401，DM 顯示「帳號或密碼錯誤」；帳號鎖定 → 503 對應訊息。

## Acceptance Scenarios

1. **Given** 使用者於 SS 已建立帳號並指派角色，**When** 於 DM 登入頁輸入正確 SS 帳密，**Then** DM 後端呼叫 APISS001 成功取得 `{ token, expires_in, user: { account, name, roles, functions } }`，DM 將 Token + functions 存入 session 並導向 DM 主頁
2. **Given** 帳密錯誤，**When** 使用者送出登入，**Then** APISS001 回 401（INVALID_CREDENTIAL），DM 顯示「帳號或密碼錯誤」（不顯示細節避免帳號列舉）；SS 累計失敗次數達 `SS_LOCK_THRESHOLD` 自動鎖定
3. **Given** 帳號已停用 / 鎖定，**When** 使用者送出登入，**Then** APISS001 回 403，DM 顯示「帳號暫時無法登入，請洽資訊人員」
4. **Given** 使用者首次登入或密碼到期，**When** APISS001 回 426（PASSWORD_CHANGE_REQUIRED），**Then** DM 導向 SS 變更密碼頁
5. **Given** SS 服務暫時不可達，**When** DM 呼叫 APISS001 逾時，**Then** DM 顯示「認證服務暫不可用」並進入只讀模式（公開分類仍可瀏覽，禁止任何寫入）
6. **Given** 使用期間 DM 後端定期呼叫 APISS002 驗 Token，**When** Token 過期 / 帳號停用 / 密碼變更，**Then** SS 回 401，DM 強制登出並導回登入頁

## Activity Diagram（UC 內部流程）

```mermaid
flowchart TD
    Start([開始]) --> A[使用者開啟 DM URL]
    A --> B[DM 顯示登入頁<br/>DM03]
    B --> C[使用者輸入 SS 帳號 / 密碼]
    C --> D[DM 呼叫 APISS001]
    D --> E{SS 回應}

    E -->|200 OK| F[Token + functions<br/>寫入 session<br/>HTTP-only cookie]
    F --> G[寫 DM_AUDIT]
    G --> H[重導 DM 主頁<br/>觸發 UCDM005]
    H --> End1([結束 ✓])

    E -->|401<br/>INVALID_CREDENTIAL| I1[顯示「帳號或密碼錯誤」]
    E -->|403<br/>ACCOUNT_DISABLED<br/>/ ACCOUNT_LOCKED| I2[顯示「帳號暫時無法登入」]
    E -->|426<br/>PASSWORD_CHANGE| I3[導向 SS 變更密碼頁]
    E -->|逾時 / SS 不可達| I4[顯示「認證服務暫不可用」<br/>進入只讀模式]

    I1 --> End2([結束 ✗])
    I2 --> End2
    I3 --> End2
    I4 --> End2

    classDef startEnd fill:#e8f5e9,stroke:#2e7d32,color:#000
    classDef action fill:#fff,stroke:#666,color:#000
    classDef decision fill:#fff8e1,stroke:#f57c00,color:#000
    classDef errorAction fill:#ffebee,stroke:#c62828,color:#000

    class Start,End1,End2 startEnd
    class A,B,C,D,F,G,H action
    class E decision
    class I1,I2,I3,I4 errorAction
```

## Sequence Diagram（互動序列）

```mermaid
sequenceDiagram
    actor U as 使用者（軍人）
    participant DM as DM 系統
    participant SS as SS 模組

    U->>DM: 開啟 DM URL → 顯示登入頁（DM03）
    U->>DM: 輸入 SS 帳號 / 密碼
    DM->>SS: APISS001 帳密驗證

    alt 帳密正確
        SS-->>DM: 200 { token, user{ roles, functions } }
        DM->>DM: Token + functions 寫入 session（HTTP-only cookie）
        DM->>DM: 寫 DM_AUDIT
        DM-->>U: 重導 DM 主頁（觸發 UCDM005）
    else 帳密錯誤
        SS-->>DM: 401 INVALID_CREDENTIAL
        DM-->>U: 「帳號或密碼錯誤」
        Note over SS: 累計失敗達 SS_LOCK_THRESHOLD<br/>自動鎖定
    else 帳號停用 / 鎖定
        SS-->>DM: 403 ACCOUNT_DISABLED / ACCOUNT_LOCKED
        DM-->>U: 「帳號暫時無法登入」
    else 首次登入 / 密碼到期
        SS-->>DM: 426 PASSWORD_CHANGE_REQUIRED
        DM-->>U: 導向 SS 變更密碼頁（UCSS002）
    else SS 不可達
        SS--xDM: 逾時
        DM-->>U: 「認證服務暫不可用」+ 進入只讀模式
    end

    loop 後續每次請求
        DM->>SS: APISS002 驗 Token
        alt Token 有效
            SS-->>DM: 200 OK + user 身分
            DM-->>U: 處理原始業務請求
        else Token 過期 / 帳號停用 / 密碼變更
            SS-->>DM: 401
            DM-->>U: 強制登出 → 回登入頁
        end
    end
```

## 對應 RQ

- RQSS013（SS 提供登入認證 API）
- RQSS014（SS 提供 Token 驗證 API）
- RQSS015（Token 具時效）
- RQSS018（登入歷程記錄）

## 前置依賴

- SS 模組（主專案 `TBMS/docs/specs/ss/spec.md`）已部署，APISS001 / APISS002 可用
- SS 端使用者帳號已建立並指派角色、角色↔功能對應已設定
