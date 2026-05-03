# Changelog

All notable changes to this project will be documented in this file.

## [0.1.0] - 2026-05-03

### Added

- Patch A: `reply_to_message_id` in MCP notification metadata for `handleInbound()`
- Patch B: `callback_query:data` handler fixes (allowlist order, double IO, MCP notification emit)
- Patch C: `editMessageText` after callback to append "✓ 已選: [label]" and clear inline_keyboard
- `lib/tg_keyboard.py` Python wrapper with chunked layout, label truncation, callback_data length validation, options limit, auto-escape
- `skill/SKILL.md` Claude skill documentation (381 lines)
- `examples/example_keyboard_v2_demo.py` interactive keyboard demo
- `patches/apply_patches.sh` idempotent auto-apply script (works as Claude Code hook)
- `tests/test_tg_keyboard.py` 61 test cases
- `docs/INSTALL.md` step-by-step installation guide
- `docs/ARCHITECTURE.md` integration diagram and component roles
- `docs/ROADMAP.md` future improvement directions

### Notes

- Targets `claude-plugins-official/external_plugins/telegram` (TypeScript plugin)
- All patches are idempotent and verified by `apply_patches.sh`
