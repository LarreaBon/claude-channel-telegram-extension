# Architecture

## System Overview

```
User (Telegram app)
     |
     | tap button
     v
Telegram Bot API
     |
     | callback_query update
     v
MCP Plugin (server.ts)  <-- Patches A + B + C applied here
     |            |
     |            | answerCallbackQuery (toast)
     |            | editMessageText (append label + clear keyboard)  <-- Patch C
     |            v
     |        Telegram Bot API
     |
     | mcp.notification channel event
     v
Claude (main agent)
     |
     | reads callback_data from <channel> tag
     | dispatches action by namespace prefix
     v
Python wrapper (tg_keyboard.py)  <-- optional, for sending keyboards
     |
     | sendMessage with inline_keyboard
     v
Telegram Bot API
     |
     | message delivery
     v
User (Telegram app)
```

## Component Roles

### server.ts (MCP Plugin)

The core of the three patches. The file lives in the plugin cache at:
`~/.claude/plugins/cache/claude-plugins-official/telegram/<VERSION>/server.ts`

Three functions are modified:

1. `handleInbound()` — Patch A adds `reply_to_message_id` to the notification metadata
2. `bot.on('callback_query:data')` — Patches B and C restructure this handler

### Patch A — Inbound metadata enrichment

```
Before:  metadata = { text, attachment_* }
After:   metadata = { text, attachment_*, reply_to_message_id? }
```

Claude can now see which message the user replied to, enabling threaded decision flows.

### Patch B — callback_query security + routing

The upstream handler had a logic error: it called `answerCallbackQuery` (clearing the spinner on the
user's phone) before checking the allowlist. An unauthorized user would see "✓ 收到" even though their
press was discarded.

Patch B fixes the order:

```
Before:  answerCallbackQuery -> loadAccess -> allowlist check -> emit notification
After:   loadAccess -> allowlist check -> answerCallbackQuery -> emit notification
```

It also removes a duplicate `loadAccess()` call in the permission branch (was reading the access file
twice per callback — once at the top and once in the perm branch).

### Patch C — Closed-loop feedback

Without Patch C, pressing a button leaves it active. The user has no visual confirmation their choice
was registered (beyond the brief toast). Worse, they can press the same button repeatedly.

Patch C adds a post-delivery edit:

```typescript
// Find the chosen button label
let chosenLabel = cb.data ?? 'unknown'
for (const row of inline_keyboard) {
  for (const btn of row) {
    if ('callback_data' in btn && btn.callback_data === cb.data) {
      chosenLabel = btn.text
      break
    }
  }
}
// Append to original message and clear keyboard
const newText = `${originalText}\n\n✓ 已選: ${chosenLabel}`
await ctx.editMessageText(newText, { reply_markup: undefined }).catch(() => {})
```

The `.catch(() => {})` ensures a stale message (>48h) or permission error does not break the handler.

### tg_keyboard.py (Python wrapper)

Optional. Provides `send_message_with_keyboard()` with input validation:

- `options > 8` raises `ValueError` (Telegram keyboard UI degrades above 8 buttons)
- `callback_data > 64 bytes` raises `ValueError` (hard Telegram API limit)
- `label > 30 chars` auto-truncates with stderr warning

Layout modes:

- `buttons_per_row=N` — fixed N buttons per row (default 2)
- `layout="auto"` — derives per-row count from label length (short < 10 chars -> 3/row, medium 10-20 -> 2/row, long > 20 -> 1/row)

### skill/SKILL.md (Claude skill)

Teaches Claude the full decision keyboard workflow:

- When to use keyboards vs plain text
- How to write message text that pairs with short button labels (labels reference numbered items in text)
- `callback_data` namespace conventions (`<topic>:<action>`)
- How to read and dispatch incoming `callback_data` from channel notifications
- `markdownV2` escape rules and why HTML parse_mode is safer

## Integration Points

### 1. Sending a keyboard

Claude invokes `send_message_with_keyboard()` from the Python wrapper. The wrapper calls
`sendMessage` with a `reply_markup` containing `inline_keyboard`.

### 2. Receiving a button press

The MCP plugin's `callback_query:data` handler (Patch B) emits:

```
mcp.notification -> Claude channel event:
<channel source="plugin:telegram:telegram"
         chat_id="..."
         message_id="..."
         callback_data="linepay:sell_all">
[button_pressed]
</channel>
```

Claude identifies this as a button press by the presence of the `callback_data` attribute.

### 3. Dispatching

Claude splits `callback_data` on `:` to get the namespace and action:

```
"linepay:sell_all" -> topic=linepay, action=sell_all -> execute LINEPAY sell logic
"lurk:add:2330"   -> topic=lurk,    action=add, symbol=2330 -> add to lurk watchlist
"alert:ack:003"   -> topic=alert,   action=ack, id=003      -> dismiss alert
```

### 4. Closed loop (Patch C)

Simultaneously with step 2, Patch C edits the original keyboard message:
- Appends `✓ 已選: [label]` to signal to the user that their choice was received
- Removes the `inline_keyboard` markup so the buttons are no longer tappable

The user sees the update within ~1 second of tapping.

## Failure Modes

| Failure | Effect | Mitigation |
|---------|--------|-----------|
| Plugin cache cleared by update | Patches lost | Re-run `apply_patches.sh`; add as hook |
| Patch needle not found after update | `apply_patches.sh` exits 1 with WARNING | Update needle strings to match new code |
| `editMessageText` on >48h message | Silent failure | `.catch(() => {})` prevents crash |
| `editMessageText` on non-bot message | Silent failure | Same `.catch()` guard |
| Network timeout on `sendMessage` | Returns `{"ok": false, "description": "..."}` | Caller checks `result["ok"]` |
