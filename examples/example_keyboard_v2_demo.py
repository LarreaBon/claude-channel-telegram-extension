#!/usr/bin/env python3
"""
example_keyboard_v2_demo.py

v2 keyboard demo: 透過 mcp plugin 直接把 callback 推給主 agent。

v1 (舊) 架構:
  send_message_with_keyboard() → TG 按鈕 → tg_callback_poller.py 輪詢 → 寫
  callback_result.json → 主 agent 輪詢 json

v2 (新) 架構:
  send_message_with_keyboard() → TG 按鈕 → mcp plugin bot.on('callback_query:data')
  → answerCallbackQuery (清 spinner) → mcp.notification channel event → 主 agent
  直接收到 <channel ... callback_data="demo:linepay_sell_all"> 標籤

主 agent 識別方式:
  <channel source="plugin:telegram:telegram" ... callback_data="demo:linepay_sell_all" ...>
  [button_pressed]
  </channel>

  → callback_data 屬性存在 → 是按鈕點擊事件
  → "demo:" prefix → 識別為 demo 測試，不做實際交易
  → 真實前綴例: "trade:" / "lurk:" / "alert:" 等

Usage:
    cd /path/to/runtime
    .venv/bin/python3 scripts/example_keyboard_v2_demo.py
    .venv/bin/python3 scripts/example_keyboard_v2_demo.py --chat-id 2143469044
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# 確保 lib/ 在 import 路徑
sys.path.insert(0, str(Path(__file__).parent))

from lib.tg_keyboard import send_message_with_keyboard


def main() -> None:
    parser = argparse.ArgumentParser(
        description="v2 keyboard demo: push button → mcp plugin → main agent channel notification"
    )
    parser.add_argument(
        "--chat-id",
        default="2143469044",
        help="Telegram chat ID to send demo to (default: 2143469044)",
    )
    args = parser.parse_args()

    # Demo: 模擬「要砍 LINEPAY 嗎？」決策按鈕
    # callback_data 長度上限 64 bytes（TG 限制），用冒號分隔 namespace
    result = send_message_with_keyboard(
        chat_id=args.chat_id,
        text=(
            "<b>v2 按鈕 demo</b>\n\n"
            "要砍 LINEPAY 嗎？\n\n"
            "點按鈕後，<code>callback_data</code> 會透過 mcp plugin 直接推給主 agent，"
            "主 agent 識別 <code>demo:</code> prefix → 認得是測試。"
        ),
        options=[
            ("全砍 NT$282K", "demo:linepay_sell_all"),
            ("不動", "demo:linepay_hold"),
        ],
        parse_mode="HTML",
    )

    if result.get("ok"):
        msg_id = result["result"]["message_id"]
        print(f"OK: message_id={msg_id}")
        print()
        print("主 agent 收到按鈕點擊時，channel tag 結構如下：")
        print()
        print(
            f'<channel source="plugin:telegram:telegram" '
            f'chat_id="{args.chat_id}" message_id="{msg_id}" '
            f'user="kjb" ts="2026-..." callback_data="demo:linepay_sell_all">'
        )
        print("[button_pressed]")
        print("</channel>")
        print()
        print("主 agent 識別邏輯：")
        print("1. callback_data 屬性存在 → 是按鈕點擊（非文字訊息）")
        print('2. "demo:" prefix → demo 測試，不執行實際交易')
        print('3. "demo:linepay_sell_all" → 回覆確認收到，不動倉位')
        print()
        print("真實用法前綴建議：")
        print('  "trade:sell_all:{symbol}"  → 觸發實際賣出流程')
        print('  "lurk:add:{symbol}"        → 加入潛伏名單')
        print('  "alert:dismiss:{alert_id}" → 關閉警示')
    else:
        desc = result.get("description", "unknown error")
        print(f"FAILED: {desc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
