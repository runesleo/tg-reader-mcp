# Changelog

All notable changes to this project will be documented in this file.

## [0.2.0] - 2026-04-22

### Added
- `get_contact` tool: read one user's first_name, last_name, username, phone, bio, **note** (the user-private contact note from TG client), is_contact, is_mutual_contact, common_groups_count, last_seen.
- `list_contacts_matching` tool: bulk-scan DM dialogs for users whose first_name contains a substring (e.g. `PMQ` to enumerate paid-reader contacts). Optional `match_note=true` also searches note bodies at the cost of one FullUser call per scanned dialog.
- Both tools surface `UserFull.note.text` from MTProto, which is server-persisted (not client-local), making contact notes usable as structured CRM data — useful for encoding paid-reader tags, cohort labels, payment TX hashes directly in TG contacts without an external CRM.

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
