# tg-reader-mcp

A **read-only** Telegram MCP server. Let your AI agent read channels, groups, and DMs — and do nothing else.

[中文版](./README.zh.md)

## Why read-only

Most Telegram bots can send, edit, delete, join, leave. That's fine for bots — it's dangerous for an AI agent with your own user session. A slip in a prompt, a hallucinated tool call, a mis-quoted channel ID, and suddenly your agent is posting in someone else's group.

This server removes the blast radius. The tools are: `list_dialogs`, `read_channel`, `search_channel`, `mark_read`. No send. No edit. No delete.

## What you get

- **`list_dialogs`** — list channels, groups, DMs. Filter by keyword, unread state, or type (`unread_dm` gives only unread private chats).
- **`read_channel`** — read recent messages from any channel or group. Paginate with `since` (ISO timestamp, forward) or `offset_date` (ISO timestamp, backward).
- **`search_channel`** — keyword search inside one channel.
- **`mark_read`** — mark a conversation as read. Useful when the agent has digested the new messages and should stop re-surfacing them.

## How it works

You log in once with your Telegram account (userbot, via Telethon). The session file lives locally. The MCP server reuses that session to read messages. Every request calls `catch_up()` first to avoid stale data.

```
You: What did @durov post recently?
AI:  [calls read_channel with channel="durov", limit=5]
     → Durov posted 3 messages in the last 48h. Summary: ...
```

Multi-process safety is built in. Each MCP process gets its own copy of the session file (keyed by PID) to avoid SQLite contention when multiple clients connect simultaneously — a real pain point if you run Claude Code and another MCP client against the same session.

## Setup

### 1. Install

```bash
git clone https://github.com/runesleo/tg-reader-mcp.git
cd tg-reader-mcp
uv venv
source .venv/bin/activate
uv pip install -e .
```

### 2. Log in once

You need a Telethon `.session` file. The simplest way: run Telethon interactively once.

```python
# login.py
from telethon import TelegramClient
client = TelegramClient('tg_session', 94575, 'a3406de8d171bb422bb6ddf3bbd800e2')
client.start()
print("Logged in. tg_session.session created.")
```

```bash
python login.py
# Enter your phone, the code Telegram sends you, and 2FA if enabled.
```

This creates `tg_session.session` in the current directory.

> The default `API_ID` / `API_HASH` above are Telegram Desktop's public credentials — safe to use. If you want your own (to raise rate limits or separate audit trails), get them at [my.telegram.org](https://my.telegram.org) and set `TG_API_ID` / `TG_API_HASH` env vars.

### 3. Wire into Claude Code

```bash
claude mcp add tg-reader -s user \
  -e TG_SESSION_PATH=/absolute/path/to/tg_session.session \
  -- /absolute/path/to/.venv/bin/python /absolute/path/to/server.py
```

Replace the paths with your actual locations.

### 4. Any other AI agent

Any MCP-compatible client works (Cursor, Claude Desktop, your own agent). Point it at `server.py` with `TG_SESSION_PATH` pointing to your `.session` file.

## ⚠️ Before you use

This is a **userbot**, not a bot-token bot. That has real consequences:

- You're logging in with your personal Telegram account. Every read looks like **you** are reading.
- Telegram's ToS permits userbots but bans automation that harasses, scrapes at scale, or impersonates. Don't mass-read, don't poll faster than a human would, don't feed the output into a spam pipeline.
- **Use a dedicated small account** if you'll be running heavy automation. If the account gets limited or banned, you lose access — not your main account.
- The `.session` file **is** your login. Treat it like a password. Don't commit it. Don't share it. The `.gitignore` already covers `*.session` and `*.session-journal`.

Telegram ToS: [telegram.org/tos](https://telegram.org/tos) · API ToS: [core.telegram.org/api/terms](https://core.telegram.org/api/terms)

## Requirements

- Python 3.10+
- `mcp>=1.0.0`, `telethon>=1.34.0` (both installed by `uv pip install -e .`)
- A Telegram account you can log into via Telethon
- That's it. No API keys beyond Telegram's, no database, no external services.

## Supported input

| Parameter | Example | Resolution |
|-----------|---------|-----------|
| Channel username | `durov` | Public channel |
| Group username | `runesgang` | Public group |
| Full channel name | `Durov's Channel` | Fuzzy match via Telethon `get_entity` |
| ISO timestamp | `2026-04-13T00:00:00+08:00` | Used by `since` / `offset_date` |

## Example workflows

**Daily digest**: `list_dialogs` with `filter="unread_channel"` → `read_channel` each → summarize → `mark_read` to clear the queue.

**Signal research**: `search_channel` for a keyword across one alpha channel → feed results into an LLM for thesis extraction.

**Cross-channel monitor**: loop `read_channel` with `since=<last_poll_time>` on N channels → only new messages come back.

## Real-world example channel

Follow [@runesgangalpha](https://t.me/runesgangalpha) — my public channel where I use this exact MCP to read and digest Polymarket, AI, and crypto signals. It's a live demo of the workflow.

## Known limitations (0.1.0)

- **No media download yet** — text only. Photos, videos, voice messages return empty text.
- **No reaction/view analytics beyond `views` count** — forwards, reactions not exposed.
- **Hard pagination limit at 500** when using `since` mode — enough for most use cases, but heavy backfills need multiple `offset_date` calls.

## Roadmap

**Read coverage**
- [ ] Media download (photos, documents, voice)
- [ ] Reactions and forward chain
- [ ] Topic/thread support in forum-style groups

**Performance**
- [ ] Persistent connection pooling across requests
- [ ] Optional Redis cache for frequently-read channels

**Deployment**
- [ ] Docker image with volume-mounted session file
- [ ] Remote MCP (HTTP transport) for multi-client setups

## About the author

*Leo ([@runes_leo](https://x.com/runes_leo)) — AI × Crypto independent builder. Trading on [Polymarket](https://polymarket.com/?r=githuball&via=runes-leo&utm_source=github&utm_content=tg-reader-mcp), building data and trading systems with Claude Code and Codex.*

[leolabs.me](https://leolabs.me) — writing · community · open-source tools · indie projects · all platforms.

[X Subscription](https://x.com/runes_leo/creator-subscriptions/subscribe) — paid content weekly, or just buy me a coffee 😁

*Learn in public, Build in public.*

## License

MIT — see [LICENSE](./LICENSE).
