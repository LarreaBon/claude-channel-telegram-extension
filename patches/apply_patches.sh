#!/usr/bin/env bash
# apply_patches.sh — Apply (or re-apply) all three telegram plugin patches.
#
# Usage:
#   bash patches/apply_patches.sh
#   bash patches/apply_patches.sh --dry-run   # show what would be changed, no writes
#
# Patches:
#   A: reply_to_message_id  — surface reply context in MCP metadata
#   B: callback_query fixes — allowlist order + single loadAccess()
#   C: editMessage          — append chosen label + clear keyboard
#
# The script auto-detects the plugin cache path:
#   ~/.claude/plugins/cache/claude-plugins-official/telegram/<VERSION>/server.ts
#
# If multiple versions are found, all are patched.
# Already-patched files are skipped silently (idempotent).

set -euo pipefail

DRY_RUN=0
if [[ "${1:-}" == "--dry-run" ]]; then
  DRY_RUN=1
  echo "[dry-run] no files will be written"
fi

PLUGIN_GLOB="${HOME}/.claude/plugins/cache/claude-plugins-official/telegram/*/server.ts"

found=0
for TS_FILE in $PLUGIN_GLOB; do
  [ -f "$TS_FILE" ] || continue
  found=$((found + 1))
  echo "=== Processing: $TS_FILE ==="

  # ── Patch A: reply_to_message_id ─────────────────────────────────────────
  if grep -q "reply_to_message_id" "$TS_FILE"; then
    echo "[A] already applied — skip"
  else
    echo "[A] applying reply_to_message_id patch..."
    if [[ "$DRY_RUN" -eq 1 ]]; then
      echo "[A] dry-run: would patch $TS_FILE"
    else
      python3 - "$TS_FILE" <<'PYEOF'
import sys
path = sys.argv[1]
with open(path, 'r') as f:
    src = f.read()

NEEDLE = "          } : {}),\n        },\n      },\n    }).catch(err => {"
REPLACE = (
    "          } : {}),\n"
    "          ...(ctx.message?.reply_to_message?.message_id != null\n"
    "            ? { reply_to_message_id: String(ctx.message.reply_to_message.message_id) }\n"
    "            : {}),\n"
    "        },\n"
    "      },\n"
    "    }).catch(err => {"
)

if "reply_to_message_id" in src:
    print("[A] already present")
    sys.exit(0)

new_src = src.replace(NEEDLE, REPLACE, 1)
if new_src != src:
    with open(path, 'w') as f:
        f.write(new_src)
    print("[A] applied")
else:
    print("[A] WARNING: needle not found — upstream may have changed surrounding code", file=sys.stderr)
    sys.exit(1)
PYEOF
    fi
  fi

  # ── Patch B: callback_query handler (allowlist order + single loadAccess) ──
  if grep -q "check allowlist first" "$TS_FILE"; then
    echo "[B] already applied — skip"
  else
    echo "[B] applying callback_query fixes..."
    if [[ "$DRY_RUN" -eq 1 ]]; then
      echo "[B] dry-run: would patch $TS_FILE"
    else
      python3 - "$TS_FILE" <<'PYEOF'
import sys
path = sys.argv[1]
with open(path, 'r') as f:
    src = f.read()

marker = "check allowlist first"
if marker in src:
    print("[B] already present")
    sys.exit(0)

# Replacement 1: restructure the non-permission branch
needle1 = (
    "bot.on('callback_query:data', async ctx => {\n"
    "  const data = ctx.callbackQuery.data\n"
    "  const m = /^perm:(allow|deny|more):([a-km-z]{5})$/.exec(data)\n"
    "  if (!m) {\n"
    "    // Non-permission callback: answer immediately to clear spinner, then\n"
    "    // emit a channel notification so Claude can act on the button press.\n"
    "    await ctx.answerCallbackQuery({ text: '✓ 收到' }).catch(() => {})\n"
    "    const cb = ctx.callbackQuery\n"
    "    const cbMsg = cb.message\n"
    "    const from = cb.from\n"
    "    const access = loadAccess()\n"
    "    const senderId = String(from.id)\n"
    "    // Only forward to Claude if sender is allowlisted — same gate as text messages.\n"
    "    if (!access.allowFrom.includes(senderId)) return"
)

replace1 = (
    "bot.on('callback_query:data', async ctx => {\n"
    "  const data = ctx.callbackQuery.data\n"
    "  const m = /^perm:(allow|deny|more):([a-km-z]{5})$/.exec(data)\n"
    "  // Load access once and cache for both branches.\n"
    "  const access = loadAccess()\n"
    "  if (!m) {\n"
    "    // Non-permission callback: check allowlist first, then clear spinner.\n"
    "    const cb = ctx.callbackQuery\n"
    "    const cbMsg = cb.message\n"
    "    const from = cb.from\n"
    "    const senderId = String(from.id)\n"
    "    // Only forward to Claude if sender is allowlisted — same gate as text messages.\n"
    "    if (!access.allowFrom.includes(senderId)) {\n"
    "      await ctx.answerCallbackQuery({ text: 'Not authorized' }).catch(() => {})\n"
    "      return\n"
    "    }\n"
    "    await ctx.answerCallbackQuery({ text: '✓ 收到' }).catch(() => {})"
)

# Replacement 2: remove duplicate loadAccess in perm branch
needle2 = (
    "    return\n"
    "  }\n"
    "  const access = loadAccess()\n"
    "  const senderId = String(ctx.from.id)\n"
    "  if (!access.allowFrom.includes(senderId)) {\n"
    "    await ctx.answerCallbackQuery({ text: 'Not authorized.' }).catch(() => {})\n"
    "    return\n"
    "  }"
)

replace2 = (
    "    return\n"
    "  }\n"
    "  const senderId = String(ctx.from.id)\n"
    "  if (!access.allowFrom.includes(senderId)) {\n"
    "    await ctx.answerCallbackQuery({ text: 'Not authorized.' }).catch(() => {})\n"
    "    return\n"
    "  }"
)

new_src = src
changed = False

if needle1 in new_src:
    new_src = new_src.replace(needle1, replace1, 1)
    changed = True
else:
    print("[B] WARNING: needle-1 not found", file=sys.stderr)

if needle2 in new_src:
    new_src = new_src.replace(needle2, replace2, 1)
    changed = True
else:
    print("[B] WARNING: needle-2 not found", file=sys.stderr)

if changed and new_src != src:
    with open(path, 'w') as f:
        f.write(new_src)
    print("[B] applied")
else:
    print("[B] WARNING: no changes made — needles may not match current version", file=sys.stderr)
    sys.exit(1)
PYEOF
    fi
  fi

  # ── Patch C: editMessage after callback ──────────────────────────────────
  # Idempotency check: detect either our own marker OR upstream's native
  # implementation. As of telegram plugin v0.0.6 the upstream maintainer
  # merged Patches B+C inline (their server.ts even credits this repo by
  # name), but their version doesn't carry our "Patch C: editMessage"
  # comment, so a self-marker grep was returning false-negative on every
  # run and the script tried to re-apply against now-shifted code.
  if grep -q "Patch C: editMessage" "$TS_FILE" \
       || grep -q "Patches B+C from claude-channel-telegram-extension" "$TS_FILE" \
       || grep -qF "editMessageText(newText, { reply_markup: undefined })" "$TS_FILE"; then
    echo "[C] already applied — skip"
  else
    echo "[C] applying editMessage patch..."
    if [[ "$DRY_RUN" -eq 1 ]]; then
      echo "[C] dry-run: would patch $TS_FILE"
    else
      python3 - "$TS_FILE" <<'PYEOF'
import sys
path = sys.argv[1]
with open(path, 'r') as f:
    src = f.read()

# Same three-way detection as the shell guard, in case someone calls
# the python block directly or copy-pastes it elsewhere.
markers = (
    "Patch C: editMessage",
    "Patches B+C from claude-channel-telegram-extension",
    "editMessageText(newText, { reply_markup: undefined })",
)
if any(m in src for m in markers):
    print("[C] already present")
    sys.exit(0)

NEEDLE = (
    "    }).catch(err => {\n"
    "      process.stderr.write(`telegram channel: failed to deliver callback_query to Claude: ${err}\\n`)\n"
    "    })\n"
    "    return\n"
    "  }"
)

REPLACE = (
    "    }).catch(err => {\n"
    "      process.stderr.write(`telegram channel: failed to deliver callback_query to Claude: ${err}\\n`)\n"
    "    })\n"
    "    // Patch C: editMessage — find chosen button label, append to text and clear keyboard.\n"
    "    if (cbMsg) {\n"
    "      const inline_keyboard = cbMsg.reply_markup?.inline_keyboard ?? []\n"
    "      let chosenLabel = cb.data ?? 'unknown'\n"
    "      for (const row of inline_keyboard) {\n"
    "        for (const btn of row) {\n"
    "          if ('callback_data' in btn && btn.callback_data === cb.data) {\n"
    "            chosenLabel = btn.text\n"
    "            break\n"
    "          }\n"
    "        }\n"
    "      }\n"
    "      const originalText = ('text' in cbMsg ? cbMsg.text : '') ?? ''\n"
    "      const newText = `${originalText}\\n\\n✓ 已選: ${chosenLabel}`\n"
    "      await ctx.editMessageText(newText, { reply_markup: undefined }).catch(() => {})\n"
    "    }\n"
    "    return\n"
    "  }"
)

if NEEDLE in src:
    new_src = src.replace(NEEDLE, REPLACE, 1)
    with open(path, 'w') as f:
        f.write(new_src)
    print("[C] applied")
else:
    print("[C] WARNING: needle not found — upstream may have changed surrounding code", file=sys.stderr)
    sys.exit(1)
PYEOF
    fi
  fi

  echo "=== Done: $TS_FILE ==="
  echo ""
done

if [[ "$found" -eq 0 ]]; then
  echo "ERROR: no server.ts found at $PLUGIN_GLOB" >&2
  echo ""
  echo "Locate your plugin cache manually and set PLUGIN_GLOB, e.g.:"
  echo "  PLUGIN_GLOB='/path/to/cache/telegram/*/server.ts' bash patches/apply_patches.sh"
  exit 1
fi

echo "All patches processed ($found file(s))."
