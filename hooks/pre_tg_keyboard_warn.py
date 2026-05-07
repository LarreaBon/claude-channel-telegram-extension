#!/usr/bin/env python3
"""
PreToolUse hook: warn when TG reply/send_message contains decision/choice patterns
but is NOT using send_message_with_keyboard.

Claude Code passes hook_event_name + tool_name + tool_input via stdin JSON.
Exit 0 = allow; exit 2 = block (we never block, only warn via stdout).
"""

import sys
import json
import re

# Keywords indicating a decision/choice/confirmation is being asked
DECISION_PATTERNS = [
    # Chinese yes/no / decision prompts
    r'要不要', r'是否', r'該不該', r'該.*嗎', r'好不好',
    r'OK嗎', r'可以嗎', r'同意嗎', r'確認嗎', r'確定嗎',
    r'派不派', r'進不進', r'砍不砍', r'買不買', r'賣不賣',
    r'留不留', r'hold不', r'抱不抱',
    # Chinese choice patterns
    r'選\s*[AB12一二]', r'[AB]\.\s', r'[1-3]\.\s.*[AB1-3]\.',
    r'方案[AB一二]', r'選項[AB一二]',
    # Decision keywords mid-sentence
    r'決定.*[嗎？?]', r'確認.*[嗎？?]', r'確定.*[嗎？?]',
    # English patterns
    r'\byes\s*/\s*no\b', r'\bY/N\b', r'\bOption\s+[AB1-3]\b',
    r'\bA\.\s+\w', r'\bB\.\s+\w', r'\bC\.\s+\w',
    r'\[1\].*\[2\]', r'\(1\).*\(2\)',
    # Action confirmation
    r'(派|進場|出場|停損|加碼|減碼|砍|留|hold)\s*(還是|or|或)',
]

# Patterns that indicate it's just an ACK or pure info push (no decision needed)
ACK_PATTERNS = [
    r'^(收到|好|OK|了解|好的|沒問題|確認收到|已收到)[\s。！]*$',
    r'^(現價|報告|更新|完成|執行完|已完成)',
    r'^\[?(分析|報告|更新|掃描|結果|完成)\]?',
    r'^(NT\$[\d.]+|USD\s*\$[\d.]+)',  # pure price push
]

# TG tool names that are "text-only" (no keyboard)
TEXT_ONLY_TOOLS = {
    'mcp__plugin_telegram_telegram__reply',
    'mcp__plugin_telegram_telegram__send_message',
}

# TG tool names that use keyboard (no warn needed)
KEYBOARD_TOOLS = {
    'mcp__plugin_telegram_telegram__send_message_with_keyboard',
}


def is_ack(text: str) -> bool:
    for pat in ACK_PATTERNS:
        if re.search(pat, text.strip(), re.IGNORECASE):
            return True
    return False


def find_triggered_keywords(text: str) -> list:
    triggered = []
    for pat in DECISION_PATTERNS:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            triggered.append(m.group(0))
    return triggered


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    tool_name = data.get('tool_name', '')
    tool_input = data.get('tool_input', {})

    # Only care about text-only TG tools
    if tool_name not in TEXT_ONLY_TOOLS:
        sys.exit(0)

    # Get message text (field name varies by tool)
    text = tool_input.get('text', '') or tool_input.get('message', '') or ''
    if not text:
        sys.exit(0)

    # Skip pure ACKs
    if is_ack(text):
        sys.exit(0)

    # Check for decision/choice patterns
    triggered = find_triggered_keywords(text)
    if not triggered:
        sys.exit(0)

    # Warn (stdout is shown as hook feedback to Claude)
    warn = (
        "[KEYBOARD MISSING WARN]\n"
        f"你的 TG 訊息用了 {tool_name}（純文字），但內容含「選擇/確認/決策」模式。\n"
        "建議改用 send_message_with_keyboard，讓 user 按按鈕回應而非打字。\n\n"
        "做法：\n"
        "  scripts/lib/tg_keyboard.py send_keyboard <chat_id> '<text>' '[{\"text\":\"[1] 砍\",\"callback_data\":\"cut\"},{\"text\":\"[2] 留\",\"callback_data\":\"hold\"}]'\n\n"
        f"觸發關鍵字：{triggered}\n"
        "若本訊息只是通知（不需 user 選擇），忽略此警告。"
    )
    print(warn)
    # Exit 0 = allow the tool call to proceed (we only warn, never block)
    sys.exit(0)


if __name__ == '__main__':
    main()
