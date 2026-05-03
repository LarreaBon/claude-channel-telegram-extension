# Contributing

Thank you for your interest in contributing to claude-channel-telegram-extension.

## Context

The upstream `anthropics/claude-plugins-official` repository does not accept external pull requests.
This repository serves as the contribution channel: patches, wrappers, and documentation are
maintained here so the community can benefit without waiting for upstream approval.

## How to File an Issue

1. Search existing issues first to avoid duplicates.
2. Use the appropriate issue template (bug report or feature request).
3. Include version information: plugin version, Python version, Bun version, OS.
4. For bugs, attach relevant logs from `~/.claude/patches/patch.log` or terminal output.

## How to Suggest a Feature

1. Open a Feature Request issue.
2. Describe the problem you are solving, not just the solution.
3. If you have a prototype, link to a branch or gist.

## How to Submit a Patch

Since upstream does not accept PRs, all improvements live in this repo:

1. Fork this repository and create a feature branch: `git checkout -b feat/my-improvement`
2. Add your patch file to `patches/` following the naming convention `patch_X_description.ts.patch`.
3. Update `patches/apply_patches.sh` to include your patch in the idempotent apply loop.
4. Update `CHANGELOG.md` under an `[Unreleased]` section.
5. Add or update tests in `tests/`.
6. Open a pull request against `main` using the PR template.

Patch files must be idempotent: running `apply_patches.sh` twice must not corrupt the target file.
See existing patches for the sentinel-comment pattern that enforces this.

## Code Style

Language: Python 3.10+
Standard: PEP 8
Maximum line length: 100 characters
Formatter: use `black --line-length 100` before committing (optional but preferred)
Type hints: encouraged for all public functions

For TypeScript patch snippets: follow the surrounding upstream code style (2-space indent).

## Test Requirement

All tests must pass before a PR can be merged:

```
pytest tests/ -v
```

New functionality must include corresponding test cases in `tests/test_*.py`.
Target: maintain or improve coverage reported by `pytest --cov=lib`.

## Commit Message Format

This project follows Conventional Commits (https://www.conventionalcommits.org/):

```
<type>(<scope>): <short summary>

[optional body]

[optional footer]
```

Types: `feat`, `fix`, `docs`, `test`, `chore`, `refactor`, `perf`

Examples:
```
feat(keyboard): add max_options validation
fix(patch_b): prevent double IO on callback_query
docs(readme): add installation badge
```

Co-Author policy: if a commit was written with AI assistance, include:
```
Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

## Questions

Open a Discussion or file an issue with the `question` label.
