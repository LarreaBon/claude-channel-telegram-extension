# Roadmap

## Near-term (next release)

### callback_data expiration timestamp

Current `callback_data` values like `linepay:sell_all` have no expiry. A user could tap an old button
hours after the decision context has changed and Claude would still execute the action.

Plan: embed a UTC Unix timestamp in the callback_data and reject presses older than N minutes.

Example format: `linepay:sell_all:1746345600` (topic:action:expires_at)

Tradeoff: reduces available bytes in the 64-byte limit. A 10-digit timestamp costs 11 bytes including
the separator, leaving 53 bytes for topic+action — sufficient for all current use cases.

### Multi-step wizard helper

Currently each step in a decision chain requires manual `send_message_with_keyboard()` calls and
manual routing in Claude's callback handler.

Plan: a `WizardSession` class in `tg_keyboard.py` that:

- Holds a step definition dict (`{ step_id: { text, options, next_step } }`)
- Automatically routes `callback_data` to the next step
- Stores intermediate selections so the final step receives the full path

Example:

```python
wizard = WizardSession(steps={
    "type": {
        "text": "Select asset class:",
        "options": [("Stocks", "type:stocks"), ("ETF", "type:etf")],
        "next": "timing",
    },
    "timing": {
        "text": "Entry timing?",
        "options": [("Now", "timing:now"), ("Wait", "timing:wait")],
    },
})
wizard.start(chat_id="...")
# On callback: wizard.advance(callback_data) -> sends next step or returns final selections
```

## Medium-term

### More example scenarios

- Yes/No confirmation with auto-dismiss on "No"
- Multi-select (select all that apply) with a "Done" commit button
- Action confirmation with countdown ("Confirm sell in 10s... [Cancel]")
- Inline search: text input + button to trigger a lookup

### callback_data analytics

Log all button presses with timestamp and user ID to a local JSONL file. Useful for:

- Auditing which decisions were made and when
- Replaying a decision sequence for debugging
- Building a decision frequency heatmap

### Upstream PR

Once Patches B and C are stable (3+ months of production use), consider opening a PR upstream
to `anthropics/claude-plugins-official`. The security fix in Patch B (allowlist before
answerCallbackQuery) is a clear correctness improvement with no controversial design decisions.
Patch C (editMessage) is more opinionated and may need to be opt-in via plugin config.

## Long-term

### TypeScript port of tg_keyboard.py

The Python wrapper is convenient for Python-based agents. A TypeScript equivalent would allow
the same keyboard-building logic to live inside the plugin itself (useful for server-side
keyboard generation without a Python subprocess).

### Webhook mode support

The current architecture assumes the MCP plugin runs in long-polling mode. A webhook variant
would allow the plugin to receive updates via HTTPS POST, enabling deployment on a server
rather than requiring a local Claude Code session to be running.
