#!/usr/bin/env python3
"""
TG Reader MCP Server

Read-only Telegram MCP server. Exposes four tools (list_dialogs, read_channel,
search_channel, mark_read) to any MCP client. No send, edit, or delete tools
are registered.

Security notes:
- All network I/O goes to Telegram's official API via Telethon.
- The .session file stays local. Nothing is transmitted elsewhere.
- Each process gets its own temporary session copy to avoid SQLite contention
  between concurrent MCP clients.
"""

import os
import sys
import json
import stat
import uuid
import atexit
import asyncio
import shutil
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# MCP SDK
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Telethon
try:
    from telethon import TelegramClient
    from telethon.tl.types import Message
except ImportError:
    print("Install telethon first: pip install telethon", file=sys.stderr)
    sys.exit(1)

# ============ Config ============
# Defaults are Telegram Desktop's public API credentials — safe to use.
# Override with TG_API_ID / TG_API_HASH for your own (see https://my.telegram.org).
API_ID = os.getenv('TG_API_ID', '94575')
API_HASH = os.getenv('TG_API_HASH', 'a3406de8d171bb422bb6ddf3bbd800e2')

# Session file path (user's login credential).
# Preferred: set TG_SESSION_PATH env var to the absolute path of your .session file.
# Fallback: sibling ../tg-reader/ directory (for backward compatibility).
_env_session = os.getenv('TG_SESSION_PATH')
if _env_session:
    _raw = Path(_env_session).expanduser()
    # Refuse symlinks to avoid loading a session outside a trusted directory.
    if _raw.is_symlink():
        raise RuntimeError(
            f"TG_SESSION_PATH must not be a symlink: {_raw}. "
            "Point it at the real .session file."
        )
    SESSION_PATH = _raw.resolve()
    if SESSION_PATH.suffix == '.session':
        SESSION_PATH = SESSION_PATH.with_suffix('')
    TG_READER_DIR = SESSION_PATH.parent

    # Best-effort permission check on the session file itself.
    _session_file = SESSION_PATH.with_suffix('.session')
    if _session_file.exists():
        try:
            _st = _session_file.stat()
            if _st.st_mode & (stat.S_IRWXG | stat.S_IRWXO):
                print(
                    f"[tg-reader-mcp] Warning: {_session_file} is readable by group/others. "
                    "Recommend `chmod 600`.",
                    file=sys.stderr,
                )
            if hasattr(os, 'geteuid') and _st.st_uid != os.geteuid():
                print(
                    f"[tg-reader-mcp] Warning: {_session_file} not owned by current user.",
                    file=sys.stderr,
                )
        except OSError:
            pass
else:
    TG_READER_DIR = Path(__file__).parent.parent / 'tg-reader'
    SESSION_PATH = TG_READER_DIR / 'tg_session'
# ==============================

# Track the per-process session copy for atexit cleanup.
# Lock guards first-access race and prevents atexit double-registration.
_PID_SESSION_COPY: Path | None = None
_PID_LOCK = threading.Lock()
_ATEXIT_REGISTERED = False

# Initialize the MCP server.
server = Server("tg-reader-mcp")


def _get_pid_session_path() -> str:
    """Create a per-process session copy to avoid SQLite contention across MCP clients.

    Uses a UUID suffix (not just PID) to prevent PID-reuse collisions, and writes
    atomically via tempfile+rename. Copy is cleaned up on normal interpreter exit.
    Guarded by a lock so concurrent first-access calls don't create two copies.
    """
    global _PID_SESSION_COPY, _ATEXIT_REGISTERED
    with _PID_LOCK:
        # Reuse the same copy across multiple get_client calls within this process.
        if _PID_SESSION_COPY is not None and _PID_SESSION_COPY.exists():
            return str(_PID_SESSION_COPY.with_suffix(''))

        src = SESSION_PATH.with_suffix('.session')
        unique_stem = f'tg_session_mcp_{os.getpid()}_{uuid.uuid4().hex[:8]}'
        target = TG_READER_DIR / f'{unique_stem}.session'

        # Atomic copy: write to temp, then rename into place.
        fd, tmp_path = tempfile.mkstemp(
            prefix='.tg_session_', suffix='.tmp', dir=str(TG_READER_DIR)
        )
        os.close(fd)
        try:
            shutil.copy2(str(src), tmp_path)
            os.replace(tmp_path, str(target))
        except Exception:
            # Clean up temp file on any failure during copy/rename.
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

        _PID_SESSION_COPY = target
        if not _ATEXIT_REGISTERED:
            atexit.register(_cleanup_pid_session)
            _ATEXIT_REGISTERED = True
        return str(target.with_suffix(''))


def _cleanup_pid_session() -> None:
    """Remove the per-process session copy on interpreter exit."""
    if _PID_SESSION_COPY is None:
        return
    for suffix in ('.session', '.session-journal'):
        p = _PID_SESSION_COPY.with_suffix(suffix)
        try:
            if p.exists():
                p.unlink()
        except OSError:
            pass


async def get_client():
    """Return a connected Telethon client for this process."""
    if not API_ID or not API_HASH:
        raise Exception("TG_API_ID and TG_API_HASH are not set")

    if not SESSION_PATH.with_suffix('.session').exists():
        raise Exception(
            f"Session file not found: {SESSION_PATH}.session. "
            "Log in once with Telethon to create it (see README)."
        )

    session_path = _get_pid_session_path()
    client = TelegramClient(session_path, int(API_ID), API_HASH)

    try:
        await client.connect()
        if not await client.is_user_authorized():
            raise Exception("Telegram session is not authorized. Re-run the Telethon login.")
        # Catch up to sync latest messages (fixes stale data issue).
        await client.catch_up()
    except Exception:
        # Release connection resources on any setup failure.
        try:
            await client.disconnect()
        except Exception:
            pass
        raise

    return client


@server.list_tools()
async def list_tools() -> list[Tool]:
    """Return the list of available MCP tools."""
    return [
        Tool(
            name="list_dialogs",
            description="List all Telegram dialogs (channels, groups, DMs). Supports combined filters like `unread_dm` (unread private chats only), `unread_channel`, `unread_group`, or any free-text keyword.",
            inputSchema={
                "type": "object",
                "properties": {
                    "filter": {
                        "type": "string",
                        "description": "Optional filter. Combine tokens: unread / dm / channel / group (e.g. `unread_dm`). Any other string is matched against dialog name and username.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max number of dialogs to return (default 50).",
                        "default": 50,
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="read_channel",
            description="Read recent messages from a Telegram channel or group. Use `since` (ISO timestamp) to return only messages after that time, or `offset_date` (ISO timestamp) to paginate backwards.",
            inputSchema={
                "type": "object",
                "properties": {
                    "channel": {
                        "type": "string",
                        "description": "Channel or group username (e.g. `durov`) or full title.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max messages to return (default 20, cap 100).",
                        "default": 20,
                    },
                    "since": {
                        "type": "string",
                        "description": "ISO timestamp. Only messages strictly after this time are returned (e.g. `2026-04-13T00:00:00+08:00`).",
                    },
                    "offset_date": {
                        "type": "string",
                        "description": "ISO timestamp. Paginate backwards from this time (feed in the `date` of the last message from a previous page).",
                    },
                },
                "required": ["channel"],
            },
        ),
        Tool(
            name="search_channel",
            description="Keyword search inside a single Telegram channel or group.",
            inputSchema={
                "type": "object",
                "properties": {
                    "channel": {
                        "type": "string",
                        "description": "Channel or group username.",
                    },
                    "keyword": {
                        "type": "string",
                        "description": "Keyword to search for.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max matching messages to return (default 20).",
                        "default": 20,
                    },
                },
                "required": ["channel", "keyword"],
            },
        ),
        Tool(
            name="mark_read",
            description="Mark a Telegram dialog (channel, group, or DM) as read.",
            inputSchema={
                "type": "object",
                "properties": {
                    "channel": {
                        "type": "string",
                        "description": "Channel, group, or DM username or full title.",
                    },
                },
                "required": ["channel"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Dispatch an MCP tool call to its implementation."""
    try:
        if name == "list_dialogs":
            result = await list_dialogs_impl(
                filter_keyword=arguments.get("filter"),
                limit=arguments.get("limit", 50),
            )
        elif name == "read_channel":
            result = await read_channel_impl(
                channel=arguments["channel"],
                limit=min(arguments.get("limit", 20), 100),
                since=arguments.get("since"),
                offset_date=arguments.get("offset_date"),
            )
        elif name == "search_channel":
            result = await search_channel_impl(
                channel=arguments["channel"],
                keyword=arguments["keyword"],
                limit=arguments.get("limit", 20),
            )
        elif name == "mark_read":
            result = await mark_read_impl(
                channel=arguments["channel"],
            )
        else:
            result = {"error": f"Unknown tool: {name}"}

        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

    except Exception as e:
        return [TextContent(type="text", text=json.dumps({"error": str(e)}, ensure_ascii=False))]


async def list_dialogs_impl(filter_keyword: str | None = None, limit: int = 50) -> dict:
    """List dialogs, optionally filtered by type / unread / keyword."""
    client = await get_client()

    try:
        dialogs = []
        count = 0

        async for dialog in client.iter_dialogs():
            if count >= limit:
                break

            if dialog.is_channel:
                dtype = "channel"
            elif dialog.is_group:
                dtype = "group"
            else:
                dtype = "dm"
            username = getattr(dialog.entity, 'username', None)

            # Filter: supports combinations like "unread_dm" = unread + direct messages.
            if filter_keyword:
                fk = filter_keyword.lower()
                want_unread = "unread" in fk
                want_dm = "dm" in fk
                want_channel = "channel" in fk
                want_group = "group" in fk
                has_type_filter = want_dm or want_channel or want_group

                if want_unread and not dialog.unread_count:
                    continue
                if has_type_filter:
                    type_match = (
                        (want_dm and dtype == "dm") or
                        (want_channel and dtype == "channel") or
                        (want_group and dtype == "group")
                    )
                    if not type_match:
                        continue
                if not want_unread and not has_type_filter:
                    # Plain name/username substring match.
                    name_match = fk in dialog.name.lower()
                    username_match = username and fk in username.lower()
                    if not name_match and not username_match:
                        continue

            dialogs.append({
                "type": dtype,
                "name": dialog.name,
                "username": username,
                "unread_count": dialog.unread_count or 0,
            })
            count += 1

        return {"dialogs": dialogs, "count": len(dialogs)}

    finally:
        await client.disconnect()


async def read_channel_impl(
    channel: str,
    limit: int = 20,
    since: str | None = None,
    offset_date: str | None = None,
) -> dict:
    """Read messages from a channel/group, with optional since/offset_date paging."""
    client = await get_client()

    try:
        # Resolve the channel/group entity.
        try:
            entity = await client.get_entity(channel)
            title = getattr(entity, 'title', channel)
        except Exception as e:
            return {"error": f"Unable to resolve channel {channel}: {e}"}

        # Parse time-window parameters.
        iter_kwargs: dict = {"limit": limit}
        since_dt = None

        if offset_date:
            dt = datetime.fromisoformat(offset_date)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            iter_kwargs["offset_date"] = dt

        if since:
            since_dt = datetime.fromisoformat(since)
            if since_dt.tzinfo is None:
                since_dt = since_dt.replace(tzinfo=timezone.utc)
            # Under `since` mode, loosen the fetch cap and rely on time cutoff.
            if not offset_date:
                iter_kwargs["limit"] = min(limit * 5, 500)

        # Iterate and collect messages.
        messages = []
        async for message in client.iter_messages(entity, **iter_kwargs):
            if not (isinstance(message, Message) and message.text):
                continue
            # iter_messages is reverse-chronological, so a message older than
            # `since` means we've passed the window and can stop early.
            if since_dt and message.date < since_dt:
                break
            messages.append({
                "id": message.id,
                "date": message.date.isoformat(),
                "text": message.text[:2000],
                "views": message.views,
            })
            if since_dt and len(messages) >= limit:
                break

        has_more = len(messages) == limit
        result: dict = {
            "channel": title,
            "messages": messages,
            "count": len(messages),
        }
        if has_more and messages:
            result["next_offset_date"] = messages[-1]["date"]

        return result

    finally:
        await client.disconnect()


async def search_channel_impl(channel: str, keyword: str, limit: int = 20) -> dict:
    """Keyword-search messages inside a single channel/group."""
    client = await get_client()

    try:
        entity = await client.get_entity(channel)
        title = getattr(entity, 'title', channel)

        messages = []
        async for message in client.iter_messages(entity, search=keyword, limit=limit):
            if isinstance(message, Message) and message.text:
                messages.append({
                    "id": message.id,
                    "date": message.date.isoformat(),
                    "text": message.text[:2000],
                })

        return {
            "channel": title,
            "keyword": keyword,
            "messages": messages,
            "count": len(messages),
        }

    finally:
        await client.disconnect()


async def mark_read_impl(channel: str) -> dict:
    """Mark a dialog (channel/group/DM) as read."""
    client = await get_client()

    try:
        try:
            entity = await client.get_entity(channel)
            name = getattr(entity, 'title', None) or getattr(entity, 'first_name', channel)
        except Exception as e:
            return {"error": f"Unable to resolve dialog {channel}: {e}"}

        await client.send_read_acknowledge(entity)
        return {"success": True, "channel": name, "message": f"Marked {name} as read"}

    finally:
        await client.disconnect()


async def main():
    """Run the MCP server over stdio."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
