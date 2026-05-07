#!/usr/bin/env bash
# UserPromptSubmit hook: remind Claude to use inline keyboard for TG decision/confirm.
PROMPT="${CLAUDE_USER_PROMPT:-}"
if echo "$PROMPT" | grep -qE '<channel source="plugin:telegram:telegram"'; then
  cat <<'EOF'
[TG KEYBOARD CHECK]
回覆若含選擇/是非/派工/action 確認/下一步選項 → 必用 send_message_with_keyboard（scripts/lib/tg_keyboard.py）。
按鈕 label 用 [1]/[2]/[3] 編號 + 短描述。message text 列完整選項+理由+風險。
不 reference 按鈕 message_id（user 看不懂）。詳見 ~/.claude/skills/tg-helper/SKILL.md。
EOF
fi
