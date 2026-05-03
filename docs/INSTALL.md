# Install Guide

## Prerequisites

- Claude Code with the telegram MCP plugin installed
- Python 3.10+
- `requests` library (`pip install requests`)
- A Telegram bot token in `~/.claude/channels/telegram/.env` as `TELEGRAM_BOT_TOKEN=...`

## Step 1 — Clone this repo

```
git clone git@github.com:LarreaBon/claude-channel-telegram-extension.git
cd claude-channel-telegram-extension
```

## Step 2 — Locate the plugin cache

The telegram plugin cache lives at:

```
~/.claude/plugins/cache/claude-plugins-official/telegram/<VERSION>/server.ts
```

Find the current version:

```
ls ~/.claude/plugins/cache/claude-plugins-official/telegram/
```

You should see one or more version directories, e.g. `0.0.6`. The `apply_patches.sh` script
auto-detects all versions using a glob pattern, so you do not need to hardcode the path.

## Step 3 — Apply patches

From the repo root:

```
bash patches/apply_patches.sh
```

Expected output (first run):

```
=== Processing: /home/USER/.claude/plugins/cache/.../server.ts ===
[A] applying reply_to_message_id patch...
[A] applied
[B] applying callback_query fixes...
[B] applied
[C] applying editMessage patch...
[C] applied
=== Done: /path/to/server.ts ===

All patches processed (1 file(s)).
```

On subsequent runs, already-applied patches are skipped:

```
[A] already applied — skip
[B] already applied — skip
[C] already applied — skip
```

If you see `WARNING: needle not found`, the upstream plugin has changed the surrounding code.
See `patches/README.md` for manual reapply instructions.

## Step 4 — Restart the plugin process

After patching, the running plugin process needs to reload:

```
# Kill the plugin process — Claude Code will automatically respawn it
pkill -f "claude-plugins-official/telegram"
```

Or simply close and reopen Claude Code.

## Step 5 — (Optional) Symlink the skill

```
ln -s "$(pwd)/skill" ~/.claude/skills/tg-helper
```

After this, Claude will automatically use inline keyboards for yes/no and multi-choice decisions
instead of asking you to type A/B/C.

## Step 6 — (Optional) Copy the Python wrapper

```
cp lib/tg_keyboard.py /your/project/scripts/lib/tg_keyboard.py
```

Or add the `lib/` directory to your Python path.

## Step 7 — Verify

Run the demo:

```
python3 examples/example_keyboard_v2_demo.py --chat-id YOUR_CHAT_ID
```

You should receive a Telegram message with two inline buttons. Tap one. You should see:

1. A toast notification ("✓ 收到") briefly appear on your phone
2. The original message text update with `\n\n✓ 已選: [label]` appended
3. The buttons disappear

If step 2 or 3 does not happen, Patch C may not have been applied. Check:

```
grep -c "Patch C" ~/.claude/plugins/cache/claude-plugins-official/telegram/*/server.ts
```

Expected output: `1` (or more if multiple versions).

## Auto-reapply on plugin update

The upstream plugin may update and clear the cache, removing your patches. To auto-reapply on
each Claude Code session start, add a hook in `~/.claude/settings.json`:

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "bash /path/to/claude-channel-telegram-extension/patches/apply_patches.sh"
          }
        ]
      }
    ]
  }
}
```

The script is idempotent — running it on every prompt submit costs only a grep per file.
