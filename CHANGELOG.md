# Changelog

**Repository:** https://github.com/runesleo/tg-reader-mcp

All notable changes to this project will be documented in this file.

## [Unreleased]

### Documentation

- Bilingual README refresh ([#1](https://github.com/runesleo/tg-reader-mcp/pull/1), [`a998264`](https://github.com/runesleo/tg-reader-mcp/commit/a9982642908b4c94edbbd7a2841031ff1d38a8fa)).

## [0.2.1] - 2026-04-22

### Fixed
- **Packaging**: `pip install -e .` / `uv pip install -e .` now succeed. Hatchling wheel config was missing an explicit `only-include`, which blocked the editable install from generating metadata.
- **Console script**: `tg-reader-mcp` entry point now points at a synchronous `cli()` wrapper that calls `asyncio.run(main())`. Previous `server:main` returned a coroutine that was never awaited, so the installed script did nothing.

### Security
- `list_contacts_matching` now rejects empty / whitespace-only `pattern` (previously an empty pattern matched every DM contact — an unintentional full-contact-list export path for a misused agent).
- `get_client()` no longer embeds the absolute session-file path in the exception message returned to the MCP client. The full path is logged to stderr for the operator only.
- Symlink check now also refuses a symlinked `<stem>.session` file when `TG_SESSION_PATH` is set without the `.session` suffix.

### Changed
- `list_contacts_matching` documentation and tool schema now state that matching covers `first_name` / `last_name` (code behavior unchanged).
- `dialog_scan_limit` now counts only DM dialogs against the scan budget. Channels and groups are skipped before the counter increments, matching the documented intent.
- README tagline clarified: read-only content plus optional `mark_read`; still no send / edit / delete.

## [0.2.0] - 2026-04-22

### Added
- `get_contact` tool: read one user's first_name, last_name, username, phone, bio, **note** (the user-private contact note from TG client), is_contact, is_mutual_contact, common_groups_count, last_seen.
- `list_contacts_matching` tool: bulk-scan DM dialogs for users whose first_name contains a substring (e.g. `VIP` to tag a private cohort). Optional `match_note=true` also searches note bodies at the cost of one FullUser call per scanned dialog.
- Both tools surface `UserFull.note.text` from MTProto, which is server-persisted (not client-local), making contact notes usable as structured metadata — useful for private labels and cohort tags stored directly inside TG contacts instead of a separate database.

## [0.1.0] - 2026-04-17

First public release.

### Added
- Four read-only MCP tools: `list_dialogs`, `read_channel`, `search_channel`, `mark_read`
- `read_channel` pagination via `since` (ISO timestamp filter) and `offset_date` (backward paging)
- `list_dialogs` filtering: combine keyword / `unread` / `dm` / `channel` / `group` (e.g. `unread_dm` returns only unread private chats)
- Per-process session isolation: each MCP process copies the session file to avoid SQLite contention when multiple clients connect simultaneously
- `TG_SESSION_PATH` environment variable for custom session file location (recommended for new users)
- `catch_up()` on every client connect to prevent stale message data

### Security
- Read-only by design: no send, edit, or delete tools
- Session file stays local; nothing is transmitted beyond Telegram's own servers
- `.gitignore` covers `*.session`, `*.session-journal`, `.env`, `.env.*`
- Uses Telegram Desktop's public API_ID as default (not user-specific credentials)
- `TG_SESSION_PATH` refuses symlinks and warns on loose file permissions / foreign ownership
- Per-process session copy keyed by UUID (not just PID) to prevent reuse collisions, written via atomic rename, cleaned up on interpreter exit
- `get_client()` releases the Telethon client on any setup failure (no leaked sockets / SQLite handles)

### Notes
- Requires an existing Telethon user session. Log in once with the setup guide in README, then point the MCP at the resulting `.session` file.
