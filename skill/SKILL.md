---
name: tg-helper
description: TG 互動全方位指南。使用時機: 1) 推 inline keyboard 選擇題 (替代打字 A/B/C) 2) markdownv2 format escape 規則 3) files 附件 (圖片/PDF) 4) callback_query handling (按鈕點擊 emit channel notification) 5) editMessage 動態更新訊息。涵蓋 send_message_with_keyboard wrapper + mcp plugin callback handler 整合。
---

# TG Helper

## 觸發時機 (必用)

主 agent 推 TG 含「選擇」「決策」「確認」時必用 inline keyboard:
- 「要不要 X」(yes/no)
- 「選 A 或 B 或 C」 (multi choice)
- 「砍 / 留」「進場 / 觀望」(action)
- 多步驟 wizard

不用 keyboard:
- 純資訊推播 (報告 / 摘要 / 提醒)
- 即時回覆 (短 ack)

## 用法

scripts/lib/tg_keyboard.py 含 send_message_with_keyboard:

▶️ CODE:
  import sys
  sys.path.insert(0, 'scripts')
  from lib.tg_keyboard import send_message_with_keyboard

  result = send_message_with_keyboard(
      chat_id='2143469044',
      text='要砍 LINEPAY 嗎?',
      options=[
          ('全砍 NT$282K', 'linepay:sell_all'),
          ('不動 等 hard_stop', 'linepay:hold'),
      ],
      parse_mode='HTML',  # 預設 None 純 text
  )
  msg_id = result['result']['message_id']

格式建議:
- label 不要太長 (不超過 30 字，超過自動截斷為 27 字 + ...)
- callback_data 用 namespace prefix: <topic>:<action> (例: linepay:sell_all)
- callback_data 上限 64 bytes (TG 限制)
- options 上限 8 顆

## 按鈕 label + 訊息 text 配對規範 (重要)

### 問題

TG button label 限約 30 字 (超過 truncate)。
若 label 含縮寫或多重動作，user 點完只看到「✓ 已選: [縮寫 label]」失去 context。

### 規範

推 inline keyboard 前 message text 必含「完整選項清單」格式:

```
要砍 LINEPAY 嗎?

選項 1) 全砍 NT$282K
理由: 沒 thesis 不該占 8.6%
風險: 鎖獲利 -38% 認賠
影響: cash flow +NT$282K

選項 2) 不動 等 hard_stop
理由: patient capital 失效線觸發才砍
風險: 繼續抱可能再跌
影響: 無新動作

選項 3) 部分減半
理由: 鎖部分獲利
風險: 兩邊不 100%
影響: cash flow +NT$141K
```

按鈕 label 用編號 / 短 ID 對應上面 text 編號:
- [1] / [2] / [3]
- 或 [1 全砍] / [2 不動] / [3 減半]
- 不要把整段塞進 label

### 為什麼

1. User 點完訊息保留 + 顯示「✓ 已選: 1」user 仍看到「1 是全砍」對應
2. 選項詳情 (理由 / 風險 / 影響) 在 text 不在 label
3. label 縮寫不失去 context

### 反例

❌ 推 keyboard 訊息只 1 行「砍 LINEPAY 嗎?」+ 按鈕 [全砍 NT$282K] [不動]
   → user 看到 [全砍 NT$282K] truncate 不知道理由 / 風險

✅ 推 keyboard 訊息 8 行含完整選項 + 按鈕 [1] [2] [3]
   → user 看完整 text 後點短按鈕，點完仍能看 text

### 禁止 reference message_id

❌ 「按鈕 2539 你選下一步」 (button message_id 對 user 沒意義)
✅ 「你選下一步:」 + 按鈕在訊息底部 user 直接看到

按鈕 message_id 是內部追蹤用，user 不需要看到。

### 主 agent 流程

1. 想清楚要問的決策有幾個選項
2. message text 列每個選項: 1) 動作 / 理由 / 風險 / 影響
3. 按鈕用 [1] / [2] / [3] 對應
4. callback_data namespace prefix 仍正常用 (`<topic>:<n>`)

### 範例

```python
result = send_message_with_keyboard(
    chat_id='2143469044',
    text=(
        '5/4 加碼決策:\n\n'
        '1) 全停 cash 保留 (推薦)\n'
        '   理由: 沒可動現金 還要付交屋裝潢\n'
        '   風險: 放棄 NT$25-38K 期望收益\n\n'
        '2) 進 1 張 1232 NT$148K\n'
        '   理由: 補真防禦 內需 + DY 4.8%\n'
        '   風險: cash buffer 接近 0\n\n'
        '3) 全進 NT$255K\n'
        '   理由: 進場 1232 + 2892\n'
        '   風險: cash 必補贖基金 強牛末段 risk 高'
    ),
    options=[
        ('1 全停', 'add54:hold'),
        ('2 進 1232', 'add54:1232_only'),
        ('3 全進', 'add54:full'),
    ],
)
```

主 agent 看到 callback_data='add54:1232_only' 即知 user 選 2 (對照 text 中編號)。

## 主 agent 處理 callback

User 點按鈕後 mcp plugin 推 channel notification，格式如下:

▶️ CODE:
  <channel source="plugin:telegram:telegram"
           chat_id="..."
           message_id="..."
           callback_data="linepay:sell_all">
  [button_pressed]
  </channel>

主 agent 識別流程:
1. channel tag 含 callback_data 屬性 = 按鈕點擊事件
2. 解析 callback_data 取得用戶選擇
3. 按 namespace prefix 分派對應動作 (linepay: → LINEPAY 持倉邏輯)

## 自動化效果 (plugin 端)

mcp plugin 收到按鈕點擊後自動執行:
1. answerCallbackQuery 顯示「✓ 收到」toast 通知
2. editMessageText 在原訊息末加「\n\n✓ 已選: [label]」
3. 清除 inline_keyboard (按鈕 disable，防止重複點)
4. emit channel notification 推給主 agent

主 agent 收到後直接讀 callback_data 執行動作，不需再問確認。

## callback_data namespace 慣例

<topic>:<action> 格式，topic 對應股票代號或功能模組:
- linepay:sell_all / linepay:hold
- 3665:entry_now / 3665:wait
- position:add / position:reduce / position:close
- alert:ack / alert:dismiss

## markdownv2 escape 規則

字符要 escape: _ * [ ] ( ) ~ ` > # + - = | { } . !

inline code 內反斜線除外 (但 _ 仍可能被解析)。
parse_mode='HTML' 是更安全的選擇，只需 escape & < >。

## 反例

❌ 「要砍嗎? A 全砍 / B 不動 / C 部分」(打字 A/B/C → 違反 user 規則)

✓ 推 inline keyboard 含 [全砍] [不動] [部分] 按鈕

## 整合點

- Patch C in mcp plugin cache server.ts 自動處理 ack + editMessage + disable 按鈕
- 主 agent 讀 channel tag callback_data 屬性辨識用戶選擇
- DCA immutable: 月扣決策不用 keyboard (沒選擇空間)
- library 路徑: scripts/lib/tg_keyboard.py (已存在，不重寫)

## Examples (常見使用情境)

### Example 1: 是非題 (yes/no confirm)

```python
result = send_message_with_keyboard(
    chat_id='2143469044',
    text=(
        '要砍 LINEPAY 嗎?\n\n'
        '1) 是 全砍\n'
        '   理由: 沒 thesis 不該占 8.6%\n'
        '   風險: 鎖虧損 -38%\n\n'
        '2) 否 維持 hard_stop NT$277.5\n'
        '   理由: patient capital 失效線觸發才砍\n'
        '   風險: 繼續抱可能再跌'
    ),
    options=[
        ('1 是', 'linepay:sell'),
        ('2 否', 'linepay:hold'),
    ],
)
```

### Example 2: 多選題 (3+ 選項)

```python
result = send_message_with_keyboard(
    chat_id='2143469044',
    text=(
        '5/4 開盤動作?\n\n'
        '1) 全停 0 加碼\n'
        '   理由: cash 保留\n'
        '   風險: 放棄期望收益\n\n'
        '2) 進 1 張 1232 大統益\n'
        '   理由: 補真防禦\n'
        '   風險: cash 緊\n\n'
        '3) 全進 1232 + 2892\n'
        '   理由: 補曝險完整\n'
        '   風險: cash 必贖基金'
    ),
    options=[
        ('1 全停', 'add54:hold'),
        ('2 1232 only', 'add54:1232'),
        ('3 全進', 'add54:full'),
    ],
)
```

### Example 3: 動作確認 (買/賣/砍)

```python
# 失效線觸發 alert
result = send_message_with_keyboard(
    chat_id='2143469044',
    text=(
        '⚠️ 漢翔 2634 跌破 NT$46.9 hard_stop\n\n'
        '當前: NT$46.5 (-1.9%)\n'
        '倉位: 1.5%\n'
        '建議動作:\n\n'
        '1) 立刻全砍 (按計畫 hard_stop 觸發)\n'
        '2) 等 30 分觀察反彈\n'
        '3) 加碼攤平 (違反 hard_stop 規則)'
    ),
    options=[
        ('1 砍', 'hanxiang:sell_all'),
        ('2 等 30 分', 'hanxiang:wait'),
        ('3 攤平', 'hanxiang:add'),
    ],
)
```

### Example 4: 推送圖表附件 (files)

```python
import sys
sys.path.insert(0, 'scripts')
from lib.tg_keyboard import send_message_with_keyboard

# 直接呼 mcp tool 推圖 (不用 keyboard)
import requests, os
token = open('~/.claude/channels/telegram/.env').read().split('=')[1].strip()
url = f'https://api.telegram.org/bot{token}/sendPhoto'

with open('/tmp/chart_pie.webp', 'rb') as f:
    response = requests.post(url, data={
        'chat_id': '2143469044',
        'caption': '今日持倉圓餅圖'
    }, files={'photo': f})
```

或用 mcp__plugin_telegram_telegram__reply with files 參數:

```python
mcp__plugin_telegram_telegram__reply(
    chat_id='2143469044',
    text='今日持倉圖表',
    files=['/tmp/chart_pie.webp', '/tmp/chart_pnl.webp'],
)
```

### Example 5: 多步驟 wizard (chain buttons)

```python
# Step 1: 大選擇
send_message_with_keyboard(
    chat_id='2143469044',
    text='選 lurk 候選類型?\n\n1) AI 鏈\n2) 金融\n3) 內需',
    options=[
        ('1 AI', 'wizard:type:ai'),
        ('2 金融', 'wizard:type:finance'),
        ('3 內需', 'wizard:type:domestic'),
    ],
)

# Step 2: user 選 [1 AI] 後主 agent 收到 callback_data='wizard:type:ai'
# 推第二層按鈕:
send_message_with_keyboard(
    chat_id='2143469044',
    text='AI 鏈哪個 segment?\n\n1) AI server ODM\n2) ABF 載板\n3) probe card',
    options=[
        ('1 ODM', 'wizard:ai:odm'),
        ('2 ABF', 'wizard:ai:abf'),
        ('3 probe', 'wizard:ai:probe'),
    ],
)
```

### Example 6: editMessage 動態更新

```python
# 推一條訊息後，過幾秒更新內容 (e.g., 跑 deep-research 完成後改訊息)
mcp__plugin_telegram_telegram__edit_message(
    chat_id='2143469044',
    message_id='2548',
    text='✓ Deep research 完成\n\n結果: 6589 台康生技 watch_with_caution\n進場: NT$42-44',
)
```

注意: editMessage 限制 48 小時內訊息 + bot 自己發的訊息。

## Dependencies

此 skill 需要以下 component 才能 work:

1. Telegram MCP plugin
   - 路徑: `~/.claude/plugins/cache/claude-plugins-official/telegram/<VERSION>/server.ts`
   - 版本: 0.0.6+ 含以下 patches:
     - Patch A: reply_to_message_id 屬性 (handleInbound)
     - Patch B: callback_query handler allowlist 順序 + double IO 修
     - Patch C: editMessageText 加「✓ 已選: [label]」+ 清按鈕

2. send_message_with_keyboard Python wrapper
   - 路徑: `<runtime>/scripts/lib/tg_keyboard.py`
   - 提供 chunked layout / label truncation / callback_data 長度檢查
   - 上游 wrapper 維護點

3. Patch auto-reapply hook
   - 路徑: `~/.claude/hooks/check_telegram_patch.sh`
   - 觸發: UserPromptSubmit
   - 自動偵測 patch 是否在 cache server.ts，若無則 reapply

4. TG bot token
   - 路徑: `~/.claude/channels/telegram/.env`
   - 環境變數: TELEGRAM_BOT_TOKEN

## Troubleshooting

### Plugin 更新導致 patch 失效

當 plugin 更新到新版 (e.g., 0.0.6 → 0.0.7):
1. Cache 清空 → patches 消失
2. Hook (check_telegram_patch.sh) 在下次 UserPromptSubmit 自動偵測 + reapply
3. 若 reapply 失敗:
   - 看 `~/.claude/patches/patch.log` 找 "WARNING: needle not found"
   - 上游可能改了周圍 code → needle 不 match
   - 手動修法見 `~/.claude/patches/README.md` (各 patch 的 manual reapply 步驟)

### 按鈕點擊後沒清空

可能原因:
1. Plugin process 沒 reload (跑舊版 cache)
   解: kill plugin process 觸發 respawn (Claude Code 自動拉)
2. patch C 沒 apply (檢查 grep "已選:" cache server.ts)
3. editMessage permission 問題 (Bot 在 group 必須是 admin)

### Callback 接不到

可能原因:
1. Plugin 沒重啟 (新 callback_query handler 沒 load)
2. mcp plugin disconnect (ToolSearch 看 mcp tool 是否可用)
3. user 不在 allowlist (看 ~/.claude/channels/telegram/access.json)
