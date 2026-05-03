# Patches

Three patches for `anthropics/claude-plugins-official` telegram plugin (`server.ts`).

Apply order matters: A then B then C.

## Patch A — reply_to_message_id

File: `01-reply_to_message_id.patch`

Target: `handleInbound()` function in `server.ts`

What it does: Adds `reply_to_message_id` to the MCP notification metadata when the incoming Telegram
message is a reply to an earlier message. Allows Claude to maintain threaded conversation context.

Marker used for idempotent detection: string `reply_to_message_id` in `server.ts`

## Patch B — callback_query handler fixes

File: `02-callback_query_fixes.patch`

Target: `bot.on('callback_query:data', ...)` handler in `server.ts`

What it does:

1. Moves `loadAccess()` call to the top of the handler so it is shared between the permission branch
   and the non-permission branch (was duplicated, causing two file reads per button press)
2. Moves allowlist check before `answerCallbackQuery` so unauthorized users are blocked before receiving
   the spinner-clear toast
3. Emits an MCP channel notification to Claude for non-permission button presses

Marker used for idempotent detection: comment string `check allowlist first` in `server.ts`

## Patch C — editMessage after callback

File: `03-edit_message_clear_button.patch`

Target: non-permission branch of `bot.on('callback_query:data', ...)` in `server.ts`

What it does: After delivering the callback notification to Claude, scans `inline_keyboard` to find the
chosen button label, appends `\n\n✓ 已選: [label]` to the original message, and clears the keyboard
markup. Gives the user immediate visual feedback without a separate Claude reply.

Marker used for idempotent detection: comment string `Patch C: editMessage` in `server.ts`

## apply_patches.sh

Run `bash apply_patches.sh` from this directory to apply all three patches to the plugin cache.
The script is idempotent — already-applied patches are skipped silently.

## Manual reapply

If the upstream plugin updates and the needle strings no longer match, edit the `NEEDLE` / `needle_literal`
strings inside `apply_patches.sh` to match the new surrounding code, then re-run the script.

Patch failures are logged to stdout. Look for lines containing `WARNING: ... needle not found`.
