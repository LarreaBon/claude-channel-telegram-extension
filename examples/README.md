# Examples

## example_keyboard_v2_demo.py

Demonstrates the v2 callback architecture: button press travels through the MCP plugin and arrives
at Claude as a channel notification with `callback_data` attribute, rather than requiring a separate
polling process.

Run it:

```
python3 examples/example_keyboard_v2_demo.py --chat-id YOUR_CHAT_ID
```

What it does:

1. Sends a message with two inline buttons to the specified chat
2. Prints the expected channel notification format so you can verify the round-trip
3. When you tap a button, the plugin appends the chosen label to the message and emits a notification

Requires: `TELEGRAM_BOT_TOKEN` environment variable or `~/.claude/channels/telegram/.env`

## v1 vs v2 Architecture

v1 (old): `send_message_with_keyboard()` -> button -> `tg_callback_poller.py` polls `getUpdates`
           -> writes `callback_result.json` -> Claude polls the file

v2 (current): `send_message_with_keyboard()` -> button -> MCP plugin `bot.on('callback_query:data')`
               -> `answerCallbackQuery` + `editMessageText` -> `mcp.notification` channel event
               -> Claude receives `<channel ... callback_data="...">` tag directly

v2 removes the polling loop entirely and gives Claude sub-second button response time.
