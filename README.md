# Claude Channel Telegram Extension

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)

Inline keyboard + reply_to + callback_query handler patches for `claude-plugins-official` telegram plugin.

## TL;DR

The official `anthropics/claude-plugins-official` telegram plugin is missing three features that make it
genuinely interactive: inline keyboard buttons, reliable callback_query handling, and message editing
after a button press. This repo provides three surgical patches plus a Python wrapper and a Claude skill
that together enable a full request-response-confirm loop without typing A/B/C.

## Why

The upstream plugin is intentionally minimal. Pull requests adding opinionated features (inline keyboards,
callback routing, message mutation) are unlikely to be merged upstream — the surface area is too broad and
the use cases are too specific to individual workflows.

This extension exists to:

1. Track the exact diffs needed to make the plugin interactive
2. Survive plugin cache invalidation (patches auto-reapply on next Claude Code session)
3. Give other users a single place to drop in the same capability

## What's Included

### Patch A - reply_to_message_id

Surfaces the Telegram `reply_to_message.message_id` in the MCP notification metadata. Without this patch,
Claude cannot know which earlier message a user replied to, breaking threaded conversation flows.

File: `patches/01-reply_to_message_id.patch`

### Patch B - callback_query handler fixes

Fixes two bugs in the upstream `callback_query:data` handler:

- Allowlist check happens before `answerCallbackQuery`, not after. Without this, unauthorized users
  receive a spinner-clear toast before being blocked.
- `loadAccess()` is called once at the handler top and shared between branches, eliminating a redundant
  file read on every button press.
- The non-permission branch emits an MCP channel notification to Claude so the main agent can react to
  button presses.

File: `patches/02-callback_query_fixes.patch`

### Patch C - editMessage after callback

After a button press, the plugin automatically:

1. Finds the chosen button label by scanning `inline_keyboard`
2. Appends `\n\n✓ 已選: [label]` to the original message text
3. Clears the `inline_keyboard` (prevents double-click)

This closes the loop for the user — the message updates in place to confirm their choice without
Claude sending a separate reply.

File: `patches/03-edit_message_clear_button.patch`

> **Note:** Telegram plugin **v0.0.6+** ships this behavior natively (their
> `server.ts` even credits this repo). The installer detects the upstream
> implementation via three fingerprints (`Patch C: editMessage`, the upstream
> credit comment, or the `editMessageText(newText, { reply_markup: undefined })`
> call) and skips the patch when any one matches.

### Skill - tg-helper

A Claude skill (`skill/SKILL.md`) that teaches Claude when and how to use inline keyboards: button layout
rules, `callback_data` namespace conventions, `markdownV2` escape reference, and the full
request-response-confirm loop. Drop it into `~/.claude/skills/tg-helper/` and Claude will use keyboards
automatically for yes/no and multi-choice decisions.

### Python Wrapper - tg_keyboard.py

`lib/tg_keyboard.py` provides `send_message_with_keyboard()` with:

- Chunked layout (auto or fixed buttons-per-row)
- Label truncation at 30 chars with stderr warning
- `callback_data` byte-length validation (64-byte Telegram limit)
- Three-layer BOT_TOKEN fallback (env -> `.env` file -> legacy file)
- Tests covering all edge cases

## Install

Step 1 — Clone this repo:

```
git clone git@github.com:LarreaBon/claude-channel-telegram-extension.git
cd claude-channel-telegram-extension
```

Step 2 — Apply patches to the plugin cache:

```
bash patches/apply_patches.sh
```

Step 3 — (Optional) Symlink the skill:

```
ln -s "$(pwd)/skill" ~/.claude/skills/tg-helper
```

Step 4 — (Optional) Copy the Python wrapper:

```
cp lib/tg_keyboard.py /your/project/scripts/lib/tg_keyboard.py
```

See `docs/INSTALL.md` for full step-by-step instructions including version detection and verification.

## Usage

```python
from lib.tg_keyboard import send_message_with_keyboard

result = send_message_with_keyboard(
    chat_id="YOUR_CHAT_ID",
    text=(
        "Sell LINEPAY?\n\n"
        "1) Sell all\n"
        "   Reason: no active thesis\n\n"
        "2) Hold at hard_stop NT$277.5\n"
        "   Reason: patient capital, wait for trigger"
    ),
    options=[
        ("1 Sell all", "linepay:sell_all"),
        ("2 Hold",     "linepay:hold"),
    ],
    parse_mode="HTML",
)
msg_id = result["result"]["message_id"]
```

When the user taps a button, the MCP plugin emits a channel notification:

```
<channel source="plugin:telegram:telegram" chat_id="..." callback_data="linepay:sell_all">
[button_pressed]
</channel>
```

Claude reads `callback_data`, executes the corresponding action, and replies with a confirmation.

## Roadmap

- `callback_data` expiration timestamp to prevent replay attacks on old buttons
- Multi-step wizard helper for chained button flows
- Additional examples: yes/no confirm, multi-select, action confirmation

See `docs/ROADMAP.md` for details.

## License

MIT. See `LICENSE`.

## Credits

Built with Claude Code (Anthropic).
Patches apply against `anthropics/claude-plugins-official` telegram plugin (tested on version 0.0.6+).

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
