# tg-reader-mcp

**What it is:** A Telegram MCP server that reuses **your** logged-in account to read channels, groups, DMs, and contact cards, with guarded `send_message` / `join_chat` write actions. Sends use exact-text dedupe by default. Message edit/delete tools are not exposed.  
**中文文档：** [README.md](./README.md)

---

## Quick Start

### 1. Install

```bash
git clone https://github.com/runesleo/tg-reader-mcp.git
cd tg-reader-mcp
uv venv && source .venv/bin/activate
uv pip install -e .
```

### 2. Create a Telethon session

You need a local `.session` file from a one-time user login (not a bot token):

```python
# login.py — run once anywhere convenient
from telethon import TelegramClient
client = TelegramClient('tg_session', 94575, 'a3406de8d171bb422bb6ddf3bbd800e2')
client.start()
print("OK: tg_session.session")
```

```bash
python login.py
```

The default `API_ID` / `API_HASH` match Telegram Desktop’s public pair. For your own app credentials, use [my.telegram.org](https://my.telegram.org) and set `TG_API_ID` / `TG_API_HASH`.

### 3. Claude Desktop (`claude_desktop_config.json`)

Merge the **`tg-reader` entry below** into the existing `mcpServers` object (macOS example path: `~/Library/Application Support/Claude/claude_desktop_config.json`). Swap in your absolute paths.

```json
{
  "mcpServers": {
    "tg-reader": {
      "command": "/ABSOLUTE/PATH/TO/tg-reader-mcp/.venv/bin/python",
      "args": ["/ABSOLUTE/PATH/TO/tg-reader-mcp/server.py"],
      "env": {
        "TG_SESSION_PATH": "/ABSOLUTE/PATH/TO/tg_session.session"
      }
    }
  }
}
```

Optional env: `TG_API_ID`, `TG_API_HASH`. If direct Telegram connectivity fails, set `TG_PROXY_URL`; `http://`, `socks5://`, and `socks4://` are supported (for example `http://127.0.0.1:7897` for a local proxy).

### 4. Claude Code (CLI)

```bash
claude mcp add tg-reader -s user \
  -e TG_SESSION_PATH=/absolute/path/to/tg_session.session \
  -- /absolute/path/to/tg-reader-mcp/.venv/bin/python /absolute/path/to/tg-reader-mcp/server.py
```

---

## Tools (matches `server.py`)

Each name is registered in `list_tools()` and dispatched in `call_tool()`.

### `download_media`

- **Purpose:** Explicitly download the photo/image/video/document attached to one Telegram message to a local path; remote-side behavior remains read-only.
- **Parameters:** `channel` (required), `message_id` (required), `out_dir` (optional; defaults to `~/.cache/tg-media`).
- **Example:**

```json
{ "channel": "durov", "message_id": 12345 }
```

### `list_dialogs`

- **Purpose:** List dialogs (channels, groups, DMs) with optional filters.
- **Parameters:**
  - `filter` (optional): e.g. `unread`, `unread_dm`, `unread_channel`, combine tokens; otherwise substring match on title/username.
  - `limit` (optional, default `50`).
- **Example:**

```json
{ "filter": "unread_channel", "limit": 40 }
```

### `read_channel`

- **Purpose:** Fetch recent text plus media-message metadata from one channel or group. Each message includes `from_me`, `sender_id`, and `sender`; media messages also include `media` / `media_hint`.
- **Parameters:**
  - `channel` (required): username or resolvable title.
  - `limit` (optional, default `20`, max `100`).
  - `since` (optional): ISO 8601; only messages **strictly after** this instant.
  - `offset_date` (optional): ISO instant to page **backward** from (use with `next_offset_date` from prior calls).
- **Example:**

```json
{ "channel": "durov", "limit": 8, "since": "2026-04-20T00:00:00Z" }
```

### `search_channel`

- **Purpose:** Keyword search inside **one** channel or group.
- **Parameters:** `channel` (required), `keyword` (required), `limit` (optional, default `20`).
- **Example:**

```json
{ "channel": "runesgangalpha", "keyword": "ETF", "limit": 12 }
```

### `send_message`

- **Purpose:** Send one plain-text message to a DM, group, or channel. Exact-text dedupe is enabled for the most recent 600 seconds by default to prevent accidental duplicates; `dedupe_window_seconds` can be raised up to 24 hours.
- **Parameters:** `channel` (required), `text` (required), `reply_to` (optional), `dedupe_window_seconds` (optional, default `600`).
- **Safety:** This is a remote write action; MCP clients should require explicit confirmation.

```json
{ "channel": "username", "text": "hello", "dedupe_window_seconds": 86400 }
```

### `join_chat`

- **Purpose:** Join a Telegram group/channel via private invite link or public username. If already joined, the operation returns idempotently without changing membership again.
- **Parameters:** `target` (required), e.g. `https://t.me/+...` or a public username / `t.me/...` link.
- **Safety:** This is a remote write action; MCP clients should require explicit confirmation.

```json
{ "target": "https://t.me/+invite_hash" }
```

### `mark_read`

- **Purpose:** Mark a dialog as read.
- **Parameters:** `channel` (required).
- **Example:**

```json
{ "channel": "Some Group Title" }
```

### `get_contact`

- **Purpose:** One user’s contact-level fields (names, username, phone when applicable, bio, private **note**, mutual flags, `common_groups_count`, `last_seen`). Phone and note depend on Telegram contact semantics.
- **Parameters:** `username` (required) — without `@`, or numeric user id.
- **Example:**

```json
{ "username": "44196397" }
```

### `list_contacts_matching`

- **Purpose:** Scan DM dialogs; return full contact dicts (same shape as `get_contact`) where `first_name` / `last_name` match `pattern`, optionally the private note when `match_note=true`. Turning on `match_note` triggers a FullUser fetch per scanned DM—keep `limit` and `dialog_scan_limit` tight.
- **Parameters:** `pattern` (required, non-empty), `match_note` (optional, default `false`), `limit` (optional, default `30`, cap `100`), `dialog_scan_limit` (optional, default `500`).
- **Example:**

```json
{ "pattern": "alpha", "match_note": false, "limit": 15 }
```

---

## When to use it

1. **Morning unread sweep:** Filter unread channels, read each, summarize, then `mark_read`.
2. **Polling only new posts:** Store last `since` timestamp per channel and pull deltas.
3. **Deep search in one alpha channel:** `search_channel` instead of scrolling by hand.
4. **Tags in contact notes:** Bulk-fetch contacts whose names or notes contain a tag string.
5. **Quick identity check:** `get_contact` for bio and rough social graph hints (`common_groups_count`).

---

## Notes

- This is a **userbot**: traffic looks like your personal account. Respect [Telegram ToS](https://telegram.org/tos) and [API terms](https://core.telegram.org/api/terms); avoid aggressive automation.
- Treat `.session` like a password—never commit or share it.
- Media is not downloaded automatically: `read_channel` / `search_channel` return media type/hints, and `download_media` is the explicit local-file step. Reactions and richer interaction remain out of scope.

## License

MIT — see [LICENSE](./LICENSE).
