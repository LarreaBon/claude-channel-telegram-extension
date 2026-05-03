#!/usr/bin/env python3
"""
Telegram inline keyboard helper.

發送含按鈕的訊息，讓 user 在手機上點選回覆，
取代文字選擇題（A/B/C 會佔用主 agent token）。

Usage:
    from lib.tg_keyboard import send_message_with_keyboard, get_bot_token

    result = send_message_with_keyboard(
        chat_id="2143469044",
        text="要砍 LINEPAY 嗎？",
        options=[
            ("全砍", "linepay_sell_all"),
            ("不動", "linepay_hold"),
        ],
    )
    # result["ok"] == True 時 result["result"]["message_id"] 是後續追蹤用的 ID

    # 自動 layout（依 label 長度決定每行幾顆）
    result = send_message_with_keyboard(
        chat_id="2143469044",
        text="選擇動作",
        options=[...],
        layout="auto",
    )

Token 讀取順序（與 lib/tg.sh 一致）：
    1. 環境變數 TELEGRAM_BOT_TOKEN
    2. ~/.claude/channels/telegram/.env
    3. ~/.telegram_bot_token
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import requests

TG_API_BASE = "https://api.telegram.org/bot{token}"

# 每行最多幾顆按鈕（手機螢幕適合 2-3 顆）
BUTTONS_PER_ROW = 2

# Label 長度分類門檻
_LABEL_SHORT = 10   # < 10 字 → 一行 3 顆
_LABEL_MEDIUM = 20  # 10-20 字 → 一行 2 顆
                    # > 20 字 → 一行 1 顆

# Label truncation 上限
_LABEL_MAX_LEN = 30
_LABEL_TRUNCATE_LEN = 27

# Telegram callback_data 上限（bytes）
_CALLBACK_DATA_MAX_BYTES = 64

# options 顆數上限（超過 raise ValueError）
_OPTIONS_MAX = 8


def get_bot_token() -> str | None:
    """取得 BOT_TOKEN，三層 fallback 與 lib/tg.sh 一致。"""
    # 1. 環境變數
    token = os.environ.get("TELEGRAM_BOT_TOKEN") or os.environ.get("BOT_TOKEN")
    if token:
        return token.strip()

    # 2. ~/.claude/channels/telegram/.env
    env_path = Path.home() / ".claude" / "channels" / "telegram" / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("TELEGRAM_BOT_TOKEN=") or line.startswith("BOT_TOKEN="):
                _, _, val = line.partition("=")
                val = val.strip().strip('"').strip("'")
                if val:
                    return val

    # 3. ~/.telegram_bot_token（legacy）
    legacy = Path.home() / ".telegram_bot_token"
    if legacy.exists():
        val = legacy.read_text(encoding="utf-8").strip()
        if val:
            return val

    return None


def _auto_buttons_per_row(label: str) -> int:
    """依 label 長度決定一行幾顆（auto layout 用）。"""
    n = len(label)
    if n < _LABEL_SHORT:
        return 3
    elif n <= _LABEL_MEDIUM:
        return 2
    else:
        return 1


def _sanitize_label(label: str) -> str:
    """
    超過 30 字 truncate 到 27 字 + "..."，並 print warning 到 stderr。

    Returns:
        可能被截斷的 label 字串
    """
    if len(label) > _LABEL_MAX_LEN:
        truncated = label[:_LABEL_TRUNCATE_LEN] + "..."
        print(
            f"WARNING: tg_keyboard label truncated: {label!r} → {truncated!r}",
            file=sys.stderr,
        )
        return truncated
    return label


def _validate_callback_data(data: str) -> None:
    """
    檢查 callback_data 長度上限（Telegram 限制 64 bytes UTF-8）。

    Raises:
        ValueError: 超過 64 bytes 時
    """
    byte_len = len(data.encode("utf-8"))
    if byte_len > _CALLBACK_DATA_MAX_BYTES:
        raise ValueError(
            f"callback_data 超過 {_CALLBACK_DATA_MAX_BYTES} bytes（實際 {byte_len} bytes）: {data!r}"
        )


def _build_keyboard(
    options: list[tuple[str, str]],
    buttons_per_row: int | str = BUTTONS_PER_ROW,
) -> dict:
    """
    把 options list 切成 N 行，每行 buttons_per_row 顆。

    Args:
        options: [(button_label, callback_data), ...]
        buttons_per_row: 每行按鈕數，或 "auto"（依各 label 長度決定）

    Returns:
        TG reply_markup dict
    """
    rows: list[list[dict]] = []

    if buttons_per_row == "auto":
        # Auto layout：每顆按鈕獨立決定一行幾顆
        # 策略：取每顆的 per_row，把相鄰同值的顆填到同行
        i = 0
        while i < len(options):
            label, data = options[i]
            label = _sanitize_label(label)
            _validate_callback_data(data)
            per_row = _auto_buttons_per_row(label)
            row = [{"text": label, "callback_data": data}]
            # 嘗試把後面符合條件的顆填到同行
            j = i + 1
            while j < len(options) and len(row) < per_row:
                next_label, next_data = options[j]
                next_label = _sanitize_label(next_label)
                _validate_callback_data(next_data)
                next_per_row = _auto_buttons_per_row(next_label)
                if next_per_row == per_row:
                    row.append({"text": next_label, "callback_data": next_data})
                    j += 1
                else:
                    break
            rows.append(row)
            i = j
    else:
        for i in range(0, len(options), buttons_per_row):
            chunk = options[i : i + buttons_per_row]
            row = []
            for label, data in chunk:
                label = _sanitize_label(label)
                _validate_callback_data(data)
                row.append({"text": label, "callback_data": data})
            rows.append(row)

    return {"inline_keyboard": rows}


def send_message_with_keyboard(
    chat_id: str,
    text: str,
    options: list[tuple[str, str]],
    parse_mode: str = "HTML",
    reply_to_message_id: int | None = None,
    buttons_per_row: int | str = BUTTONS_PER_ROW,
    layout: str | None = None,
    token: str | None = None,
) -> dict:
    """
    送含 inline_keyboard 按鈕的 TG 訊息。

    Args:
        chat_id: TG chat ID（字串或整數皆可）
        text: 訊息主文（支援 HTML 或 MarkdownV2，依 parse_mode）
        options: [(button_label, callback_data), ...]
                 callback_data 長度上限 64 bytes（TG 限制）
                 label 超過 30 字自動截斷為 27 字 + "..."
        parse_mode: "HTML" | "MarkdownV2" | "" (純文字)
        reply_to_message_id: 引用回覆的 message_id，None 表示不引用
        buttons_per_row: 每行幾顆按鈕，預設 2；layout 優先
        layout: "auto" 依 label 長度自動排列；None 使用 buttons_per_row
        token: 若已知 token 可直接傳入，跳過自動偵測

    Returns:
        TG API response dict。成功時 result["ok"] == True，
        result["result"]["message_id"] 可用來追蹤 callback。
        失敗時 result["ok"] == False，result["description"] 含錯誤原因。

    Raises:
        ValueError: 沒找到 BOT_TOKEN、options > 8 顆、或 callback_data > 64 bytes 時
    """
    if len(options) > _OPTIONS_MAX:
        raise ValueError(
            f"options 超過 {_OPTIONS_MAX} 顆（實際 {len(options)} 顆）。"
            f"請分成多次呼叫，每次 ≤{_OPTIONS_MAX} 顆。"
        )

    if token is None:
        token = get_bot_token()
    if not token:
        raise ValueError(
            "找不到 TELEGRAM_BOT_TOKEN。"
            "請設環境變數、或存入 ~/.claude/channels/telegram/.env"
        )

    # layout 參數優先於 buttons_per_row
    effective_layout: int | str = "auto" if layout == "auto" else buttons_per_row

    api_url = f"https://api.telegram.org/bot{token}/sendMessage"
    reply_markup = _build_keyboard(options, buttons_per_row=effective_layout)

    payload: dict[str, Any] = {
        "chat_id": str(chat_id),
        "text": text,
        "reply_markup": json.dumps(reply_markup),
    }
    if parse_mode:
        payload["parse_mode"] = parse_mode
    if reply_to_message_id is not None:
        payload["reply_to_message_id"] = reply_to_message_id

    try:
        resp = requests.post(api_url, data=payload, timeout=15)
        return resp.json()
    except requests.RequestException as exc:
        return {"ok": False, "description": str(exc)}


def answer_callback_query(
    callback_query_id: str,
    text: str = "",
    show_alert: bool = False,
    token: str | None = None,
) -> dict:
    """
    回應 callback_query，清除按鈕的 spinning 狀態（TG 規範要求）。

    Args:
        callback_query_id: 從 update["callback_query"]["id"] 取得
        text: 回應文字（toast 通知，可空字串）
        show_alert: True 會彈出 alert 對話框，False 是短暫 toast
        token: 可選，跳過自動偵測

    Returns:
        TG API response dict
    """
    if token is None:
        token = get_bot_token()
    if not token:
        raise ValueError("找不到 TELEGRAM_BOT_TOKEN")

    api_url = f"https://api.telegram.org/bot{token}/answerCallbackQuery"
    payload: dict[str, Any] = {
        "callback_query_id": callback_query_id,
        "text": text,
        "show_alert": show_alert,
    }
    try:
        resp = requests.post(api_url, data=payload, timeout=10)
        return resp.json()
    except requests.RequestException as exc:
        return {"ok": False, "description": str(exc)}


def get_updates(
    offset: int | None = None,
    allowed_updates: list[str] | None = None,
    timeout: int = 0,
    token: str | None = None,
) -> dict:
    """
    呼叫 TG getUpdates API（polling 用）。

    Args:
        offset: 上次處理的 update_id + 1，用來跳過已處理的 update
        allowed_updates: 只接收哪類 update，例如 ["callback_query"]
        timeout: long polling 等待秒數（0 表示 short polling）
        token: 可選，跳過自動偵測

    Returns:
        TG API response dict，result 是 list[update]
    """
    if token is None:
        token = get_bot_token()
    if not token:
        raise ValueError("找不到 TELEGRAM_BOT_TOKEN")

    api_url = f"https://api.telegram.org/bot{token}/getUpdates"
    payload: dict[str, Any] = {"timeout": timeout}
    if offset is not None:
        payload["offset"] = offset
    if allowed_updates is not None:
        payload["allowed_updates"] = json.dumps(allowed_updates)

    try:
        resp = requests.post(api_url, data=payload, timeout=timeout + 10)
        return resp.json()
    except requests.RequestException as exc:
        return {"ok": False, "description": str(exc), "result": []}
