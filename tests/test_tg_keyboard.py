"""
pytest for scripts/lib/tg_keyboard.py

測試重點：
- _build_keyboard 正確把 options 切成行
- send_message_with_keyboard 組出正確的 TG API payload
- answer_callback_query payload 正確
- get_updates offset 傳遞正確
- 無 token 時 raise ValueError
- label truncation（超過 30 字）
- callback_data 長度檢查（> 64 bytes raise ValueError）
- auto layout（短/中/長 label 各 per_row）
- options > 8 顆 raise ValueError
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from lib.tg_keyboard import (  # noqa: E402
    _build_keyboard,
    _sanitize_label,
    _validate_callback_data,
    answer_callback_query,
    get_updates,
    send_message_with_keyboard,
)


# ---------------------------------------------------------------------------
# _build_keyboard
# ---------------------------------------------------------------------------

class TestBuildKeyboard:
    def test_two_options_one_row(self):
        opts = [("A 全砍", "sell_all"), ("B 不動", "hold")]
        kb = _build_keyboard(opts, buttons_per_row=2)
        assert "inline_keyboard" in kb
        rows = kb["inline_keyboard"]
        assert len(rows) == 1
        assert len(rows[0]) == 2
        assert rows[0][0] == {"text": "A 全砍", "callback_data": "sell_all"}
        assert rows[0][1] == {"text": "B 不動", "callback_data": "hold"}

    def test_three_options_two_rows(self):
        opts = [("A", "a"), ("B", "b"), ("C", "c")]
        kb = _build_keyboard(opts, buttons_per_row=2)
        rows = kb["inline_keyboard"]
        assert len(rows) == 2
        assert len(rows[0]) == 2
        assert len(rows[1]) == 1
        assert rows[1][0]["callback_data"] == "c"

    def test_single_option(self):
        opts = [("OK", "confirm")]
        kb = _build_keyboard(opts, buttons_per_row=3)
        rows = kb["inline_keyboard"]
        assert len(rows) == 1
        assert rows[0][0]["text"] == "OK"

    def test_exactly_per_row(self):
        opts = [("X", "x"), ("Y", "y"), ("Z", "z")]
        kb = _build_keyboard(opts, buttons_per_row=3)
        rows = kb["inline_keyboard"]
        assert len(rows) == 1
        assert len(rows[0]) == 3

    def test_empty_options(self):
        kb = _build_keyboard([], buttons_per_row=2)
        assert kb["inline_keyboard"] == []


# ---------------------------------------------------------------------------
# send_message_with_keyboard
# ---------------------------------------------------------------------------

class TestSendMessageWithKeyboard:
    def _mock_response(self, ok: bool = True, message_id: int = 42) -> MagicMock:
        resp = MagicMock()
        resp.json.return_value = {
            "ok": ok,
            "result": {"message_id": message_id},
        }
        return resp

    def test_basic_payload(self):
        """驗證 requests.post 收到正確的 data dict。"""
        with patch("lib.tg_keyboard.requests.post") as mock_post:
            mock_post.return_value = self._mock_response(message_id=100)
            result = send_message_with_keyboard(
                chat_id="2143469044",
                text="測試問題",
                options=[("A", "opt_a"), ("B", "opt_b")],
                parse_mode="HTML",
                token="fake_token_123",
            )

        assert result["ok"] is True
        assert result["result"]["message_id"] == 100

        call_args = mock_post.call_args
        assert call_args[0][0] == "https://api.telegram.org/botfake_token_123/sendMessage"
        payload = call_args[1]["data"]
        assert payload["chat_id"] == "2143469044"
        assert payload["text"] == "測試問題"
        assert payload["parse_mode"] == "HTML"

        # reply_markup 是 JSON 字串
        rm = json.loads(payload["reply_markup"])
        assert "inline_keyboard" in rm
        assert rm["inline_keyboard"][0][0]["callback_data"] == "opt_a"

    def test_reply_to_message_id(self):
        with patch("lib.tg_keyboard.requests.post") as mock_post:
            mock_post.return_value = self._mock_response()
            send_message_with_keyboard(
                chat_id="111",
                text="有 reply_to",
                options=[("OK", "ok")],
                reply_to_message_id=9999,
                token="tk",
            )
        payload = mock_post.call_args[1]["data"]
        assert payload["reply_to_message_id"] == 9999

    def test_no_parse_mode(self):
        """parse_mode="" 時不帶此欄位。"""
        with patch("lib.tg_keyboard.requests.post") as mock_post:
            mock_post.return_value = self._mock_response()
            send_message_with_keyboard(
                chat_id="111",
                text="pure text",
                options=[("A", "a")],
                parse_mode="",
                token="tk",
            )
        payload = mock_post.call_args[1]["data"]
        assert "parse_mode" not in payload

    def test_no_token_raises(self):
        with patch("lib.tg_keyboard.get_bot_token", return_value=None):
            try:
                send_message_with_keyboard(
                    chat_id="111",
                    text="test",
                    options=[("A", "a")],
                )
                assert False, "應拋 ValueError"
            except ValueError as exc:
                assert "TELEGRAM_BOT_TOKEN" in str(exc)

    def test_api_url_contains_token(self):
        with patch("lib.tg_keyboard.requests.post") as mock_post:
            mock_post.return_value = self._mock_response()
            send_message_with_keyboard(
                chat_id="111",
                text="t",
                options=[("X", "x")],
                token="MY_SECRET_TOKEN",
            )
        url = mock_post.call_args[0][0]
        assert "MY_SECRET_TOKEN" in url

    def test_network_error_returns_error_dict(self):
        import requests as req_lib
        with patch("lib.tg_keyboard.requests.post", side_effect=req_lib.RequestException("timeout")):
            result = send_message_with_keyboard(
                chat_id="111",
                text="t",
                options=[("X", "x")],
                token="tk",
            )
        assert result["ok"] is False
        assert "timeout" in result["description"]

    def test_inline_keyboard_structure(self):
        """確認 inline_keyboard JSON 結構符合 TG Bot API 規範。"""
        with patch("lib.tg_keyboard.requests.post") as mock_post:
            mock_post.return_value = self._mock_response()
            send_message_with_keyboard(
                chat_id="111",
                text="三選一",
                options=[
                    ("甲", "choice_a"),
                    ("乙", "choice_b"),
                    ("丙", "choice_c"),
                ],
                buttons_per_row=2,
                token="tk",
            )
        payload = mock_post.call_args[1]["data"]
        rm = json.loads(payload["reply_markup"])
        rows = rm["inline_keyboard"]
        # 3 options, 2 per row → 2 rows
        assert len(rows) == 2
        assert len(rows[0]) == 2
        assert len(rows[1]) == 1
        # 每顆按鈕都有 text 和 callback_data
        for row in rows:
            for btn in row:
                assert "text" in btn
                assert "callback_data" in btn


# ---------------------------------------------------------------------------
# answer_callback_query
# ---------------------------------------------------------------------------

class TestAnswerCallbackQuery:
    def test_payload(self):
        resp = MagicMock()
        resp.json.return_value = {"ok": True, "result": True}
        with patch("lib.tg_keyboard.requests.post", return_value=resp) as mock_post:
            result = answer_callback_query(
                callback_query_id="abc123",
                text="收到",
                show_alert=False,
                token="tk",
            )
        assert result["ok"] is True
        payload = mock_post.call_args[1]["data"]
        assert payload["callback_query_id"] == "abc123"
        assert payload["text"] == "收到"
        assert payload["show_alert"] is False

    def test_url(self):
        resp = MagicMock()
        resp.json.return_value = {"ok": True}
        with patch("lib.tg_keyboard.requests.post", return_value=resp) as mock_post:
            answer_callback_query("cq_id", token="MY_TK")
        url = mock_post.call_args[0][0]
        assert "answerCallbackQuery" in url
        assert "MY_TK" in url


# ---------------------------------------------------------------------------
# get_updates
# ---------------------------------------------------------------------------

class TestGetUpdates:
    def test_offset_passed(self):
        resp = MagicMock()
        resp.json.return_value = {"ok": True, "result": []}
        with patch("lib.tg_keyboard.requests.post", return_value=resp) as mock_post:
            get_updates(offset=500, token="tk")
        payload = mock_post.call_args[1]["data"]
        assert payload["offset"] == 500

    def test_no_offset(self):
        resp = MagicMock()
        resp.json.return_value = {"ok": True, "result": []}
        with patch("lib.tg_keyboard.requests.post", return_value=resp) as mock_post:
            get_updates(token="tk")
        payload = mock_post.call_args[1]["data"]
        assert "offset" not in payload

    def test_allowed_updates_serialized(self):
        resp = MagicMock()
        resp.json.return_value = {"ok": True, "result": []}
        with patch("lib.tg_keyboard.requests.post", return_value=resp) as mock_post:
            get_updates(allowed_updates=["callback_query"], token="tk")
        payload = mock_post.call_args[1]["data"]
        parsed = json.loads(payload["allowed_updates"])
        assert parsed == ["callback_query"]

    def test_network_error(self):
        import requests as req_lib
        with patch("lib.tg_keyboard.requests.post", side_effect=req_lib.RequestException("err")):
            result = get_updates(token="tk")
        assert result["ok"] is False
        assert result["result"] == []


# ---------------------------------------------------------------------------
# 新增：label truncation
# ---------------------------------------------------------------------------

class TestLabelTruncation:
    def test_short_label_unchanged(self):
        label = "短標籤"
        result = _sanitize_label(label)
        assert result == label

    def test_exactly_30_chars_unchanged(self):
        label = "a" * 30
        result = _sanitize_label(label)
        assert result == label

    def test_31_chars_truncated(self):
        label = "a" * 31
        result = _sanitize_label(label)
        assert len(result) == 30  # 27 + "..."
        assert result.endswith("...")

    def test_truncation_warning_to_stderr(self):
        label = "x" * 35
        captured = io.StringIO()
        with patch("sys.stderr", captured):
            _sanitize_label(label)
        assert "truncated" in captured.getvalue()

    def test_build_keyboard_truncates(self):
        long_label = "a" * 31  # 31 chars, definitely > 30
        assert len(long_label) > 30
        kb = _build_keyboard([(long_label, "data")], buttons_per_row=1)
        btn_text = kb["inline_keyboard"][0][0]["text"]
        assert len(btn_text) <= 30
        assert btn_text.endswith("...")

    def test_send_with_long_label(self):
        resp = MagicMock()
        resp.json.return_value = {"ok": True, "result": {"message_id": 1}}
        long_label = "x" * 35  # 35 chars, definitely > 30
        assert len(long_label) > 30
        with patch("lib.tg_keyboard.requests.post", return_value=resp):
            result = send_message_with_keyboard(
                chat_id="111",
                text="test",
                options=[(long_label, "data_ok")],
                token="tk",
            )
        assert result["ok"] is True


# ---------------------------------------------------------------------------
# 新增：callback_data 長度檢查
# ---------------------------------------------------------------------------

class TestCallbackDataLengthCheck:
    def test_short_data_ok(self):
        _validate_callback_data("short_data")  # should not raise

    def test_exactly_64_bytes_ok(self):
        data = "a" * 64
        _validate_callback_data(data)  # should not raise

    def test_65_bytes_raises(self):
        data = "a" * 65
        try:
            _validate_callback_data(data)
            assert False, "應拋 ValueError"
        except ValueError as e:
            assert "64" in str(e)

    def test_multibyte_utf8_counted_correctly(self):
        # 中文字 3 bytes each；22 字 = 66 bytes > 64
        data = "中" * 22
        assert len(data.encode("utf-8")) == 66
        try:
            _validate_callback_data(data)
            assert False, "應拋 ValueError"
        except ValueError as e:
            assert "66" in str(e)

    def test_build_keyboard_raises_on_long_callback(self):
        bad_data = "x" * 65
        try:
            _build_keyboard([("label", bad_data)], buttons_per_row=1)
            assert False, "應拋 ValueError"
        except ValueError:
            pass

    def test_send_raises_on_long_callback(self):
        bad_data = "x" * 65
        try:
            send_message_with_keyboard(
                chat_id="111",
                text="t",
                options=[("label", bad_data)],
                token="tk",
            )
            assert False, "應拋 ValueError"
        except ValueError as e:
            assert "64" in str(e)


# ---------------------------------------------------------------------------
# 新增：auto layout
# ---------------------------------------------------------------------------

class TestChunkedLayoutAuto:
    def test_short_labels_3_per_row(self):
        # < 10 字 → 3 per row
        opts = [("A", "a"), ("B", "b"), ("C", "c")]
        kb = _build_keyboard(opts, buttons_per_row="auto")
        rows = kb["inline_keyboard"]
        assert len(rows) == 1
        assert len(rows[0]) == 3

    def test_medium_labels_2_per_row(self):
        # 10-20 字 → 2 per row
        label = "十個字元按鈕測試標籤"  # 9 chars (< 10, short)
        label_med = "十到二十字元的按鈕標籤測試"  # 13 chars (medium)
        opts = [(label_med, "a"), (label_med, "b"), (label_med, "c")]
        kb = _build_keyboard(opts, buttons_per_row="auto")
        rows = kb["inline_keyboard"]
        # 3 medium labels: first row gets 2, second row gets 1
        assert len(rows) == 2
        assert len(rows[0]) == 2
        assert len(rows[1]) == 1

    def test_long_labels_1_per_row(self):
        # > 20 字 → 1 per row
        long = "這個按鈕標籤的長度超過了二十個字元的限制"  # 20 chars, need > 20
        long2 = "這個按鈕標籤的長度超過了二十個字元的限制X"  # 21 chars
        assert len(long2) > 20
        opts = [(long2, "a"), (long2, "b")]
        kb = _build_keyboard(opts, buttons_per_row="auto")
        rows = kb["inline_keyboard"]
        assert len(rows) == 2
        for row in rows:
            assert len(row) == 1

    def test_layout_auto_param_in_send(self):
        resp = MagicMock()
        resp.json.return_value = {"ok": True, "result": {"message_id": 1}}
        opts = [("A", "a"), ("B", "b"), ("C", "c")]
        with patch("lib.tg_keyboard.requests.post", return_value=resp) as mock_post:
            send_message_with_keyboard(
                chat_id="111",
                text="test",
                options=opts,
                layout="auto",
                token="tk",
            )
        payload = mock_post.call_args[1]["data"]
        rm = json.loads(payload["reply_markup"])
        rows = rm["inline_keyboard"]
        # 3 short labels (< 10 chars) → 1 row of 3
        assert len(rows) == 1
        assert len(rows[0]) == 3

    def test_mixed_label_lengths(self):
        opts = [
            ("短", "a"),            # short → 3 per row
            ("十到二十字按鈕標籤測試", "b"),  # medium → 2 per row
        ]
        kb = _build_keyboard(opts, buttons_per_row="auto")
        rows = kb["inline_keyboard"]
        # different per_row → each gets its own row
        assert len(rows) >= 2


# ---------------------------------------------------------------------------
# 新增：options > 8 顆 raise ValueError
# ---------------------------------------------------------------------------

class TestTooManyOptionsRaises:
    def test_8_options_ok(self):
        resp = MagicMock()
        resp.json.return_value = {"ok": True, "result": {"message_id": 1}}
        opts = [(f"btn{i}", f"data{i}") for i in range(8)]
        with patch("lib.tg_keyboard.requests.post", return_value=resp):
            result = send_message_with_keyboard(
                chat_id="111",
                text="t",
                options=opts,
                token="tk",
            )
        assert result["ok"] is True

    def test_9_options_raises(self):
        opts = [(f"btn{i}", f"data{i}") for i in range(9)]
        try:
            send_message_with_keyboard(
                chat_id="111",
                text="t",
                options=opts,
                token="tk",
            )
            assert False, "應拋 ValueError"
        except ValueError as e:
            assert "8" in str(e)

    def test_many_options_raises(self):
        opts = [(f"btn{i}", f"data{i}") for i in range(20)]
        try:
            send_message_with_keyboard(
                chat_id="111",
                text="t",
                options=opts,
                token="tk",
            )
            assert False, "應拋 ValueError"
        except ValueError as e:
            assert "20" in str(e)
