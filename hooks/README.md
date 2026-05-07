# Hooks

Three Claude Code hooks that enforce keyboard discipline and keep patches alive.

## Files

hooks/pre_tg_keyboard_warn.py
  PreToolUse hook. Fires before any TG send_message / reply call. If the
  message text contains decision / choice / confirmation patterns but the
  tool is NOT send_message_with_keyboard, prints a [KEYBOARD MISSING WARN]
  advisory to stdout. Exit 0 always — warns, never blocks.

hooks/tg_keyboard_reminder.sh
  UserPromptSubmit hook. When the incoming prompt contains a Telegram channel
  tag, prints a one-line reminder to use send_message_with_keyboard for any
  reply that offers a choice or requires confirmation.

hooks/check_telegram_patch.sh
  UserPromptSubmit hook. Checks whether the plugin server.ts has been updated
  since the last run (via mtime cache). If changed (or first run), re-applies
  Patches A, B, and C automatically so they survive plugin cache invalidation.

## Install

Add to ~/.claude/settings.json under "hooks":

▶️ CODE:
  {
    "hooks": {
      "PreToolUse": [
        {
          "matcher": "mcp__plugin_telegram_telegram__",
          "hooks": [
            {
              "type": "command",
              "command": "python3 /path/to/hooks/pre_tg_keyboard_warn.py"
            }
          ]
        }
      ],
      "UserPromptSubmit": [
        {
          "matcher": "",
          "hooks": [
            {
              "type": "command",
              "command": "bash /path/to/hooks/tg_keyboard_reminder.sh"
            },
            {
              "type": "command",
              "command": "bash /path/to/hooks/check_telegram_patch.sh"
            }
          ]
        }
      ]
    }
  }

Replace /path/to/hooks/ with the absolute path to this hooks/ directory.

## Secret Safety

No hardcoded tokens or chat IDs. BOT_TOKEN is read at runtime via the
three-layer fallback in lib/tg.sh (env -> .env -> ~/.config/telegram).
check_telegram_patch.sh uses only local file paths under ~/.claude/.
