#!/usr/bin/env bash
# Auto-reapply telegram patches after plugin update.
# Triggered by UserPromptSubmit hook in settings.json
#
# Patch A: reply_to_message_id in handleInbound notification meta
# Patch B: callback_query handler fixes:
#   - answerCallbackQuery after allowlist check (not before)
#   - loadAccess() called once at handler top (no double IO)
#   - non-perm branch emits mcp.notification to Claude
# Patch C: editMessage after callback — find chosen button label, append
#   "✓ 已選: [label]" to original message text and clear inline_keyboard

LOG="/home/kjb/.claude/patches/patch.log"
TS=$(date '+%Y-%m-%d %H:%M:%S')

# version cache: skip if plugin unchanged
CACHE="/home/kjb/.claude/patches/.version_cache"
TS_FILES=$(ls /home/kjb/.claude/plugins/cache/claude-plugins-official/telegram/*/server.ts 2>/dev/null)
if [ -n "$TS_FILES" ]; then
  CURRENT_MTIME=$(stat -c %Y $TS_FILES 2>/dev/null | sort | tail -1)
  if [ -f "$CACHE" ] && [ "$(cat $CACHE)" = "$CURRENT_MTIME" ]; then
    exit 0  # plugin unchanged, patches already verified
  fi
fi

for TS_FILE in /home/kjb/.claude/plugins/cache/claude-plugins-official/telegram/*/server.ts; do
  [ -f "$TS_FILE" ] || continue

  # ── Patch A: reply_to_message_id ──────────────────────────────────────────
  if grep -q "reply_to_message_id" "$TS_FILE"; then
    : # already patched, silent
  else
    echo "[$TS] patch-A: MISSING in $TS_FILE — applying..." >> "$LOG"

    python3 - "$TS_FILE" <<'PYEOF' >> "$LOG" 2>&1
import sys
path = sys.argv[1]
with open(path, 'r') as f:
    src = f.read()

NEEDLE = "          } : {}),\n        },\n      },\n    }).catch(err => {"
REPLACE = """\
          } : {}),
          ...(ctx.message?.reply_to_message?.message_id != null
            ? { reply_to_message_id: String(ctx.message.reply_to_message.message_id) }
            : {}),
        },
      },
    }).catch(err => {"""

if "reply_to_message_id" not in src:
    new_src = src.replace(NEEDLE, REPLACE, 1)
    if new_src != src:
        with open(path, 'w') as f:
            f.write(new_src)
        print(f"patch-A applied: {path}")
    else:
        print(f"WARNING: patch-A needle not found in {path}", file=sys.stderr)
else:
    print(f"patch-A already present: {path}")
PYEOF

    echo "[$TS] patch-A: done for $TS_FILE" >> "$LOG"
  fi

  # ── Patch B: callback_query handler (allowlist order + single loadAccess) ──
  if grep -q "check allowlist first" "$TS_FILE"; then
    : # already patched, silent
  else
    echo "[$TS] patch-B: MISSING in $TS_FILE — applying..." >> "$LOG"

    python3 - "$TS_FILE" <<'PYEOF' >> "$LOG" 2>&1
import sys
path = sys.argv[1]
with open(path, 'r') as f:
    src = f.read()

NEEDLE = """\
bot.on('callback_query:data', async ctx => {
  const data = ctx.callbackQuery.data
  const m = /^perm:(allow|deny|more):([a-km-z]{5})$/.exec(data)
  if (!m) {
    // Non-permission callback: answer immediately to clear spinner, then
    // emit a channel notification so Claude can act on the button press.
    await ctx.answerCallbackQuery({ text: '\\u2713 \\u6536\\u5230' }).catch(() => {})
    const cb = ctx.callbackQuery
    const cbMsg = cb.message
    const from = cb.from
    const access = loadAccess()
    const senderId = String(from.id)
    // Only forward to Claude if sender is allowlisted \\u2014 same gate as text messages.
    if (!access.allowFrom.includes(senderId)) return\
"""

REPLACE = """\
bot.on('callback_query:data', async ctx => {
  const data = ctx.callbackQuery.data
  const m = /^perm:(allow|deny|more):([a-km-z]{5})$/.exec(data)
  // Load access once and cache for both branches.
  const access = loadAccess()
  if (!m) {
    // Non-permission callback: check allowlist first, then clear spinner.
    const cb = ctx.callbackQuery
    const cbMsg = cb.message
    const from = cb.from
    const senderId = String(from.id)
    // Only forward to Claude if sender is allowlisted \\u2014 same gate as text messages.
    if (!access.allowFrom.includes(senderId)) {
      await ctx.answerCallbackQuery({ text: 'Not authorized' }).catch(() => {})
      return
    }
    await ctx.answerCallbackQuery({ text: '\\u2713 \\u6536\\u5230' }).catch(() => {})\
"""

# Detect the second loadAccess() removal (perm branch)
NEEDLE2 = """\
    return
  }
  const access = loadAccess()
  const senderId = String(ctx.from.id)
  if (!access.allowFrom.includes(senderId)) {
    await ctx.answerCallbackQuery({ text: 'Not authorized.' }).catch(() => {})
    return
  }\
"""

REPLACE2 = """\
    return
  }
  const senderId = String(ctx.from.id)
  if (!access.allowFrom.includes(senderId)) {
    await ctx.answerCallbackQuery({ text: 'Not authorized.' }).catch(() => {})
    return
  }\
"""

marker = "check allowlist first"
if marker in src:
    print(f"patch-B already present: {path}")
    sys.exit(0)

changed = False

# Apply first replacement (callback_query handler top)
new_src = src
# Use literal strings with actual unicode characters
needle_literal = (
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
replace_literal = (
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

if needle_literal in new_src:
    new_src = new_src.replace(needle_literal, replace_literal, 1)
    changed = True
else:
    print(f"WARNING: patch-B needle-1 not found in {path}", file=sys.stderr)

# Apply second replacement (remove duplicate loadAccess in perm branch)
needle2_literal = (
    "    return\n"
    "  }\n"
    "  const access = loadAccess()\n"
    "  const senderId = String(ctx.from.id)\n"
    "  if (!access.allowFrom.includes(senderId)) {\n"
    "    await ctx.answerCallbackQuery({ text: 'Not authorized.' }).catch(() => {})\n"
    "    return\n"
    "  }"
)
replace2_literal = (
    "    return\n"
    "  }\n"
    "  const senderId = String(ctx.from.id)\n"
    "  if (!access.allowFrom.includes(senderId)) {\n"
    "    await ctx.answerCallbackQuery({ text: 'Not authorized.' }).catch(() => {})\n"
    "    return\n"
    "  }"
)

if needle2_literal in new_src:
    new_src = new_src.replace(needle2_literal, replace2_literal, 1)
    changed = True
else:
    print(f"WARNING: patch-B needle-2 not found in {path}", file=sys.stderr)

if changed and new_src != src:
    with open(path, 'w') as f:
        f.write(new_src)
    print(f"patch-B applied: {path}")
elif not changed:
    print(f"patch-B: no changes made (needles not found) for {path}")
PYEOF

    echo "[$TS] patch-B: done for $TS_FILE" >> "$LOG"
  fi

  # ── Patch C: editMessage after callback (find label, append, clear keyboard) ──
  if grep -q "Patch C: editMessage" "$TS_FILE"; then
    : # already patched, silent
  else
    echo "[$TS] patch-C: MISSING in $TS_FILE — applying..." >> "$LOG"

    python3 - "$TS_FILE" <<'PYEOF' >> "$LOG" 2>&1
import sys
path = sys.argv[1]
with open(path, 'r') as f:
    src = f.read()

marker = "Patch C: editMessage"
if marker in src:
    print(f"patch-C already present: {path}")
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
    print(f"patch-C applied: {path}")
else:
    print(f"WARNING: patch-C needle not found in {path}", file=sys.stderr)
PYEOF

    echo "[$TS] patch-C: done for $TS_FILE" >> "$LOG"
  fi
done

# update version cache after successful patch run
if [ -n "$TS_FILES" ] && [ -n "${CURRENT_MTIME:-}" ]; then
  echo "$CURRENT_MTIME" > "$CACHE"
fi
exit 0
