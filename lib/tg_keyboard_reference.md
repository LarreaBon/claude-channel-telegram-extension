# tg_keyboard_reference.md

詳細說明 send_message_with_keyboard() 參數、回傳值、異常、範例。

## Args 詳細

chat_id
  TG chat ID，字串或整數皆可。

text
  訊息主文，支援 HTML 或 MarkdownV2（依 parse_mode）。
  parse_mode='MarkdownV2' 且 auto_escape=True 時，傳原始未 escape 文字即可。

options
  [(button_label, callback_data), ...]
  - callback_data 長度上限 64 bytes（TG 限制）
  - label 超過 30 字自動截斷為 27 字 + "..."
  - MarkdownV2 + auto_escape=True 時 label 也會自動 escape
  - callback_data 不需 escape（純 ASCII，TG 不渲染）
  - 最多 8 顆（超過 raise ValueError）

parse_mode
  "HTML" | "MarkdownV2" | "" (純文字)，預設 "HTML"

reply_to_message_id
  引用回覆的 message_id，None 表示不引用

buttons_per_row
  每行幾顆按鈕，預設 2；layout="auto" 時忽略此參數

layout
  "auto" 依 label 長度自動排列；None 使用 buttons_per_row

token
  若已知 token 可直接傳入，跳過自動偵測（env → .env → ~/.config）

auto_escape
  預設 True。parse_mode='MarkdownV2' 時自動 escape text 與 label。
  設 False 表示呼叫方已自行 escape。

## Returns

TG API response dict：
  result["ok"] == True  → 成功
  result["result"]["message_id"]  → 可用來追蹤 callback
  result["ok"] == False → result["description"] 含錯誤原因

## Raises

ValueError
  - 沒找到 BOT_TOKEN
  - options 超過 8 顆
  - callback_data 超過 64 bytes

## Example

```python
# HTML（預設，最簡單）
send_message_with_keyboard(
    chat_id="2143469044",
    text="確認進場 2330 @ 950？",
    options=[("[1] 確認進場", "confirm"), ("[2] 取消", "cancel")],
)

# MarkdownV2 自動 escape
send_message_with_keyboard(
    chat_id="2143469044",
    text="~/.claude/agents 已同步 (5 個 .md)",
    options=[("確認", "confirm"), ("取消", "cancel")],
    parse_mode="MarkdownV2",
    auto_escape=True,   # 預設，可省略
)

# 引用回覆
send_message_with_keyboard(
    chat_id="2143469044",
    text="選擇下一步：",
    options=[("[1] 繼續", "go"), ("[2] 停止", "stop")],
    reply_to_message_id=12345,
)
```
