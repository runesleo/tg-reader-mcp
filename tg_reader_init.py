#!/usr/bin/env python3
"""One-time Telegram user login and MCP config helper."""

import json
import os
import shlex
import sys
from pathlib import Path

from telethon import TelegramClient
from server import API_HASH, API_ID, _telethon_proxy

APP_DIR = Path.home() / ".tg-reader-mcp"
DEFAULT_SESSION_FILE = APP_DIR / "tg_session.session"


def _session_file() -> Path:
    raw = os.getenv("TG_SESSION_PATH")
    path = Path(raw).expanduser() if raw else DEFAULT_SESSION_FILE
    if path.is_symlink():
        raise RuntimeError("TG_SESSION_PATH must not be a symlink")
    path = path if path.suffix == ".session" else path.with_suffix(".session")
    if path.exists() and path.is_symlink():
        raise RuntimeError("The .session file must not be a symlink")
    return path.resolve()


def _tighten_session_permissions(session_file: Path) -> None:
    for path in (session_file, session_file.with_suffix(".session-journal")):
        if not path.exists():
            continue
        try:
            path.chmod(0o600)
        except OSError:
            pass


def main() -> int:
    session_file = _session_file()
    custom_session = bool(os.getenv("TG_SESSION_PATH"))

    try:
        api_id = int(API_ID)
    except ValueError:
        print("ERROR: TG_API_ID must be an integer", file=sys.stderr)
        return 2

    parent_existed = session_file.parent.exists()
    old_umask = os.umask(0o077)
    client = None
    try:
        session_file.parent.mkdir(parents=True, exist_ok=True)
        # Only change directory mode when it belongs to this helper: the default
        # app dir, or a custom directory that we just created. Never chmod an
        # existing user-selected directory (for example $HOME or a shared dir).
        if not custom_session or not parent_existed:
            try:
                session_file.parent.chmod(0o700)
            except OSError:
                pass
        _tighten_session_permissions(session_file)

        client = TelegramClient(
            str(session_file.with_suffix("")),
            api_id,
            API_HASH,
            proxy=_telethon_proxy(),
        )
        print(f"Telegram session: {session_file}")
        print("Log in once below. Telegram may ask for your phone, login code, and 2FA password.\n")

        client.start()
        if not client.is_user_authorized():
            raise RuntimeError("Telegram session is not authorized")
        me = client.get_me()
        client.get_dialogs(limit=1)  # read-only smoke test
    finally:
        if client is not None:
            try:
                client.disconnect()
            except Exception:
                pass
        os.umask(old_umask)
        _tighten_session_permissions(session_file)

    label = f"@{me.username}" if getattr(me, "username", None) else str(me.id)
    print(f"\nOK: authorized as {label}; dialog read check passed.")

    env = {"TG_SESSION_PATH": str(session_file)}
    for key in ("TG_API_ID", "TG_API_HASH", "TG_PROXY_URL"):
        if os.getenv(key):
            env[key] = os.environ[key]

    bindir = Path(os.path.abspath(sys.executable)).parent
    server_cmd = bindir / ("tg-reader-mcp.exe" if os.name == "nt" else "tg-reader-mcp")
    config = {"mcpServers": {"tg-reader": {"command": str(server_cmd), "env": env}}}

    print("\nClaude Desktop — merge the tg-reader entry into mcpServers:")
    print(json.dumps(config, indent=2, ensure_ascii=False))

    parts = ["claude", "mcp", "add", "tg-reader", "-s", "user"]
    for key, value in env.items():
        parts += ["-e", f"{key}={value}"]
    parts += ["--", str(server_cmd)]
    print("\nClaude Code — run:")
    print(shlex.join(parts))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
