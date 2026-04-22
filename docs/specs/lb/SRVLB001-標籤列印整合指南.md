# SRVLB001 標籤列印整合指南

**適用對象**: BC / CP / BS / TL 模組開發者
**版本**: v1.0（2026-04-16）
**對應程式**: LBSB01 標籤服務程式 v1.1r1

> 本文件說明如何透過 SRVLB001 送出列印指令給 LBSB01 標籤服務程式。
> 完整 SRV 契約見 `docs/specs/lb/contracts/srv-contracts.md`。

---

## 1. 架構總覽

![SRVLB001 架構圖](images/srvlb001-architecture.png)

**重點**：呼叫端只需 Call SRVLB001，中央負責路由到正確的 Printer Server。

---

## 2. 呼叫方式

### 2.1 Request

```
POST  SRVLB001（中央 DP Server 端點）
Content-Type: application/json
Authorization: Bearer <你的模組 TOKEN>
```

```json
{
  "bar_type":    "CP11",
  "site_id":     "S01",
  "specimen_no": "SPC-2026-0001",
  "data_1":      "0822505751",
  "data_2":      "0883305737",
  "data_3":      "05001",
  "data_4":      "紅血球濃厚液",
  "data_5":      "AB-",
  "...":         "...",
  "data_19":     "18721",
  "status":      0
}
```

### 2.2 參數說明

| 參數 | 型態 | 必填 | 說明 |
|------|------|------|------|
| `bar_type` | string | **Y** | 標籤代碼（見 Section 4 標籤類型表） |
| `site_id` | string | **Y** | 資料站點代碼 |
| `specimen_no` | string | N | 檢體號碼（供查詢追蹤用） |
| `data_1` ~ `data_19` | string | N | 標籤列印資料（每種標籤使用不同欄位，見 Section 5） |
| `status` | int | N | `0` = Online Queue（預設）；`2` = Offline Queue（僅測試頁用） |

> **不需要傳 `printer_id`**。中央 SRVLB001 會自動根據你的工作站 IP + bar_type，
> 透過 SRVDP010（資訊設備標籤印表機查詢）查出對應的印表機、連線資訊（SERVER_IP/port/校正參數）。
> 若未設定對應關係，會回傳 `"資訊設備標籤要先設定"`。

### 2.3 Response

**成功**：
```json
{
  "success":    true,
  "uuid":       "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "printer_id": "PRN-002",
  "message":    "OK"
}
```

**失敗（未設定設備標籤對應）**：
```json
{
  "success": false,
  "message": "資訊設備標籤要先設定"
}
```

| 回傳 | 型態 | 說明 |
|------|------|------|
| `success` | boolean | 是否成功 |
| `uuid` | string | 列印記錄的 UUID（成功時回傳） |
| `printer_id` | string | 系統解析出的印表機編號（成功時回傳） |
| `message` | string | 訊息（失敗時為錯誤說明） |

---

## 3. 呼叫流程

```
  你的模組            中央 SRVLB001          SRVDP010          LB_PRINTER       LBSB01 :9200
  ────────            ──────────────         ────────          ──────────       ────────────
     │                     │                    │                  │                │
     │  bar_type=CP11      │                    │                  │                │
     │  site_id=S01        │                    │                  │                │
     │  data_1~19          │                    │                  │                │
     │────────────────────→│                    │                  │                │
     │                     │                    │                  │                │
     │                     │ client_ip+bar_type │                  │                │
     │                     │───────────────────→│                  │                │
     │                     │                    │                  │                │
     │                     │    printer_id ←────│                  │                │
     │                     │   （或 not found）  │                  │                │
     │                     │                    │                  │                │
     │                     │  [找不到]           │                  │                │
     │  ← "資訊設備標籤  ──│                    │                  │                │
     │     要先設定"       │                    │                  │                │
     │                     │                    │                  │                │
     │                     │  [找到 PRN-002]     │                  │                │
     │                     │ query SERVER_IP ───│─────────────────→│                │
     │                     │                    │    192.168.1.10 ←│                │
     │                     │                    │                  │                │
     │                     │ POST :9200 ────────│──────────────────│───────────────→│
     │                     │                    │                  │    寫 Queue    │
     │                     │              200 OK│←─────────────────│────────────────│
     │       200 OK  ←─────│                    │                  │                │
     │  { uuid, printer_id │                    │                  │                │
     │    message: "OK" }  │                    │                  │                │
```

> 完整 SRVLB001 處理流程見 `contracts/srv-contracts.md` §SRVLB001；內部步驟 Drill-Down 見 [UCLB001](images/uclb001-flow.png) 中 SRVLB001 Block 的 CompositeStructure 子圖（EA：`SRVLB001-標籤列印通用API`）。

---

## 4. 標籤類型表（bar_type）

### 4.1 目前啟用

| bar_type | 名稱 | 群組 | 紙張尺寸 | 說明 |
|----------|------|------|---------|------|
| `CP01` | 血品小標籤 | CP 成分 | 80×35mm | 血品基本辨識標籤 |
| `CP11` | 血品核對標籤-合格 | CP 成分 | 80×75mm | 含 ISBT 條碼 + 抗原 + 注意事項 |
| `CP19` | 血品核對標籤-不適輸用 | CP 成分 | 80×75mm | 不合格血品標識 |
| `TL01` | 檢驗檢體標籤 | TL 檢驗 | 45×15mm | 檢驗用檢體標籤 |

### 4.2 規劃中（停用，待需求確認）

| bar_type | 名稱 | 群組 | 紙張尺寸 |
|----------|------|------|---------|
| `CP02` | 血品小標籤A | CP | 80×35mm |
| `CP12` | 血品核對標籤-特殊標識 | CP | 80×75mm |
| `CP91` | 成分藍色籃號 | CP | 80×35mm |
| `CP92` | 細菌小標籤 | CP | 45×15mm |
| `BC01` | 檢體小標籤 | BC | 45×15mm |
| `BC02` | 187標籤 | BC | 80×35mm |
| `BS01` | 運送器材借用標籤 | BS | 80×75mm |
| `BS02` | 運送器材條碼 | BS | 80×35mm |
| `BS03` | 血品裝箱大標籤 | BS | 100×200mm |
| `BS04` | 供應籃號標籤 | BS | 80×75mm |
| `BS05` | 供應特殊血品標籤 | BS | 80×75mm |
| `BS07` | 血品裝箱小標籤 | BS | 80×35mm |

> 需要啟用新的 bar_type 時，請聯繫 LB 模組負責人新增標籤定義。

---

## 5. data_1 ~ data_19 欄位對應

每種標籤使用的欄位不同，呼叫端依 `bar_type` 填入對應欄位即可，未使用的欄位留空或不傳。

### CP01 — 血品小標籤

> **2026-04-17 變更（[ISLB003](../../../issue/ISLB003-CP01-移除-data-4-6-8-11.md)）**：CP01 不再列印 `data_4` / `data_6` / `data_8` / `data_11`。Client 可繼續傳（向下相容），但不會出現在標籤上。

| 欄位 | 用途 | 範例 |
|------|------|------|
| `data_1` | 血袋號+捐血人+日期+袋序+袋數+型態（`\|`分隔） | `TW2024050001\|18721\|20180207\|01\|1\|S` |
| `data_3` | 日期時間 | `2018/02/07 10:11:12` |
| `data_5` | Rh | `+` |
| `data_7` | 血型 | `O` |
| `data_10` | 成分代碼 | `M33` |
| `data_12` | 組數 | `1` |
| `data_19` | 捐血人ID | `18721` |

### CP11 — 血品核對標籤-合格

> **2026-04-17 變更（[ISLB002](../../../issue/ISLB002-CP11-移除-data-8-13-14-15.md)）**：CP11 不再列印 `data_8` / `data_13` / `data_14` / `data_15`。Client 可繼續傳這些欄位（向下相容），但不會出現在標籤上。

| 欄位 | 用途 | 範例 |
|------|------|------|
| `data_1` | 血袋號（左側條碼） | `0822505751` |
| `data_2` | 相關血袋號（右側條碼） | `0883305737` |
| `data_3` | 血品3碼（條碼） | `05001` |
| `data_4` | 血品名稱（旋轉文字） | `紅血球濃厚液` |
| `data_5` | 血型（含 Rh） | `AB-` |
| `data_6` | ISBT DIN13+Flag+Check（16碼） | `T88661921675600D` |
| `data_7` | ISBT PD5 | `E0212V00` |
| `data_9` | 採血日期 | `2019/07/21` |
| `data_10` | 保存截止日 | `2019/08/25` |
| `data_11` | 注意事項（`\n`換行） | `注意事項：\n1.於2~6℃冷藏...` |
| `data_12` | 附加說明（`\n`換行） | `本血品含有3.0E+11個血小板。\n...` |
| `data_17` | 製備日期（空=用採血日期） | `` |
| `data_19` | 捐血人ID | `18721` |

### CP19 — 血品核對標籤-不適輸用

> **2026-04-17 變更（[ISLB002](../../../issue/ISLB002-CP11-移除-data-8-13-14-15.md)）**：CP19 不再列印 `data_13`。Client 可繼續傳（向下相容），但不會出現在標籤上。

| 欄位 | 用途 | 範例 |
|------|------|------|
| `data_4` | 血品名稱 | `FFP from WB52 in 8hrs 新鮮冷凍血漿` |
| `data_6` | ISBT DIN13+Flag+Check（16碼） | `T88661921675600D` |
| `data_7` | ISBT PD5 | `E0212V00` |
| `data_9` | 採血日期 | `2019/07/21` |
| `data_12` | 右半文字（`\n`換行） | `本血品含有3.0E+11個血小板。\n...` |
| `data_16` | 左半文字—不適輸用原因（`\n`換行） | `不適輸用\nHBsAg 檢驗陽性` |
| `data_19` | 捐血人ID | `18721` |

### TL01 — 檢驗檢體標籤

| 欄位 | 用途 | 範例 |
|------|------|------|
| `data_1` | 血袋號+類別+日期（`\|`分隔） | `TW2024050001\|TL\|20180207` |

---

## 6. 印表機自動解析（呼叫端不需處理）

### 6.1 解析原理

呼叫端**不需要知道 printer_id**，中央 SRVLB001 會自動解析：

```
你的工作站 IP + bar_type
  → SRVDP010 查 DP_COMPDEVICE_LABEL
  → 找到對應的 PRINTER_ID
  → 查 LB_PRINTER.SERVER_IP
  → 轉發到正確的 LBSB01
```

### 6.2 前置設定（管理者操作）

管理者需在「資訊設備」功能中建立對應關係：

| 工作站 IP | 標籤類型 | 印表機 | 說明 |
|-----------|---------|--------|------|
| 192.168.1.50 | CP11 | PRN-002 | 採血室 1 號電腦 → 印 CP11 用 PRN-002 |
| 192.168.1.50 | TL01 | PRN-003 | 採血室 1 號電腦 → 印 TL01 用 PRN-003 |
| 192.168.1.51 | CP11 | PRN-002 | 採血室 2 號電腦 → 印 CP11 也用 PRN-002 |

> 同一台工作站可針對不同標籤類型指定不同印表機。

### 6.3 未設定時的錯誤

若管理者尚未設定對應關係，呼叫端會收到：

```json
{ "success": false, "message": "資訊設備標籤要先設定" }
```

**處理方式**：提示使用者聯繫管理者，在「資訊設備」功能中設定該工作站的標籤印表機對應。

---

## 7. 錯誤處理

### 7.1 呼叫端應處理的回傳

| success | message | 情境 | 建議處理 |
|---------|---------|------|---------|
| `true` | OK | 列印指令已送達 | 顯示成功訊息 + printer_id |
| `false` | 資訊設備標籤要先設定 | 工作站未設定標籤印表機對應 | 提示聯繫管理者設定 |
| `false` | Printer Server 不可達 | LBSB01 離線 | 提示稍後重試 |
| `false` | bar_type 不支援 | 標籤代碼錯誤 | 檢查 bar_type |

### 7.2 UUID 追蹤

回傳的 `uuid` 可用於：
- 查詢列印狀態（`LB_PRINT_LOG.STATUS`）
- 追蹤列印結果（`LB_PRINT_LOG.RESULT`）

| STATUS | 語意 |
|--------|------|
| 0 | 待列印（在 Online Queue 中） |
| 1 | 終態（已列印或人工刪除） |
| 2 | 離線區（在 Offline Queue 中） |

---

## 8. 呼叫範例

### 8.1 Python

```python
import json
import urllib.request

def call_srvlb001(bar_type: str, site_id: str, **data_fields):
    """呼叫 SRVLB001 送出列印指令（printer_id 由中央自動解析）。"""
    payload = {
        "bar_type": bar_type,
        "site_id": site_id,
        "status": 0,
        **data_fields,
    }
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        "http://中央DP_SERVER/api/lb/print",  # SRVLB001 端點
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer <YOUR_TOKEN>",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        result = json.loads(resp.read().decode("utf-8"))
        if result["success"]:
            print(f"列印成功，印表機={result['printer_id']}，UUID={result['uuid']}")
        else:
            print(f"列印失敗：{result['message']}")
            # message 可能為 "資訊設備標籤要先設定" → 提示管理者設定

# 範例：印一張 CP11 血品核對標籤（不需指定印表機）
call_srvlb001(
    bar_type="CP11",
    site_id="S01",
    specimen_no="SPC-2026-0001",
    data_1="0822505751",
    data_2="0883305737",
    data_3="05001",
    data_4="紅血球濃厚液",
    data_5="AB-",
    data_6="T88661921675600D",
    data_7="E0212V00",
    data_9="2019/07/21",
    data_10="2019/08/25",
)
```

### 8.2 Delphi（主系統常用）

```delphi
procedure CallSRVLB001(const BarType, SiteId: string;
                       DataFields: TJSONObject);
var
  Http: TIdHTTP;
  Body: TStringStream;
  Payload, Response: TJSONObject;
begin
  Payload := TJSONObject.Create;
  try
    Payload.AddPair('bar_type', BarType);
    Payload.AddPair('site_id', SiteId);
    Payload.AddPair('status', TJSONNumber.Create(0));
    // 不需傳 printer_id — 中央自動解析
    // 合併 data_1 ~ data_19
    Payload.MergeFields(DataFields);

    Http := TIdHTTP.Create(nil);
    Body := TStringStream.Create(Payload.ToString, TEncoding.UTF8);
    try
      Http.Request.ContentType := 'application/json';
      Http.Request.CustomHeaders.AddValue('Authorization', 'Bearer ' + Token);
      Http.Post('http://DP_SERVER/api/lb/print', Body);
      // 解析 Response...
    finally
      Body.Free;
      Http.Free;
    end;
  finally
    Payload.Free;
  end;
end;

// 範例（不需傳 printer_id）
var Fields: TJSONObject;
begin
  Fields := TJSONObject.Create;
  Fields.AddPair('data_1', '0822505751');
  Fields.AddPair('data_4', '紅血球濃厚液');
  Fields.AddPair('data_5', 'AB-');
  CallSRVLB001('CP11', 'S01', Fields);
end;
```

---

## 9. Port 規則

| Port | 用途 | 設定 |
|------|------|------|
| **9100** | GoDEX 印表機 TCP 列印 | 印表機端固定 |
| **9200** | LBSB01 HTTP Task Listener | **固定，不可更改** |

> Port 9200 由 LBSB01 綁定，中央 SRVLB001 自動轉發到此 Port。呼叫端不需要知道 9200 的存在。

---

## 10. 常見問題

### Q: 收到 "資訊設備標籤要先設定" 怎麼辦？

代表管理者尚未在「資訊設備」功能中設定該工作站的標籤印表機對應。
請聯繫管理者，告知：
1. 你的工作站 IP
2. 要印的標籤類型（bar_type）
3. 要使用哪台印表機

管理者設定完成後，再次呼叫即可正常列印。

### Q: 我需要指定印表機嗎？

**不需要**。中央 SRVLB001 會根據你的工作站 IP + bar_type 自動解析出對應的印表機。
呼叫成功後，Response 會回傳 `printer_id` 讓你知道系統選了哪台。

### Q: 我的模組還沒有標籤定義（bar_type），怎麼辦？

聯繫 LB 模組負責人，提供：
1. 標籤代碼（建議格式：`{模組代碼}{流水號}`，如 `BS01`）
2. 標籤中文名稱
3. 紙張尺寸（mm）
4. data_1 ~ data_19 各欄位用途說明

LB 模組會在 `labels.py` 新增定義，並在 LBSB01 中加入對應的列印邏輯。

### Q: 一張標籤 = 一次 Call？

**是的**。新系統每一次 Call SRVLB001 = 一張標籤 = 一筆 LB_PRINT_LOG 記錄。
如果需要印 5 張，就 Call 5 次（每次帶不同的 data）。

### Q: status 什麼時候填 2？

**一般不需要**。`status=0`（預設）= 進 Online Queue 正常列印。
`status=2` 僅供 LBSB01 標籤測試頁使用（進 Offline Queue），外部模組請勿使用。

### Q: 印表機離線或 LBSB01 關機怎麼辦？

中央 SRVLB001 會：
1. 嘗試轉發到 LBSB01（HTTP POST :9200）
2. 如果 LBSB01 不可達 → 回傳 `success=false`
3. 呼叫端收到失敗後，可提示使用者稍後重試

> LB_PRINT_LOG 已在中央寫入（Step 2），即使轉發失敗，記錄不會遺失。

---

## 11. 相關文件

| 文件 | 路徑 | 說明 |
|------|------|------|
| SRV 契約 | `docs/specs/lb/contracts/srv-contracts.md` | SRVLB001 完整 I/O 定義 |
| 開發者指南 | `docs/specs/lb/LBSB01-開發者指南.md` | LBSB01 內部架構（LB 模組開發者用） |
| 操作手冊 | `docs/specs/lb/LBSB01-操作手冊.md` | LBSB01 操作說明 |
| 功能規格 | `docs/specs/lb/spec.md` | SA 設計文件 |
