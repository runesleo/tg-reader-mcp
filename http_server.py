#!/usr/bin/env python3
"""
TG Reader HTTP Server
为豆丁（OpenClaw）提供 TG 频道只读接口

用法:
  python http_server.py        # 默认 127.0.0.1:8765
  python http_server.py 8766   # 指定端口

接口:
  GET /channels/{name}/messages?limit=20
  GET /channels/{name}/search?keyword=xxx&limit=20
  GET /dialogs?filter=xxx&limit=50
  GET /health
"""

import os
import sys
import json
import asyncio
from pathlib import Path
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
import threading

# 复用 tg-reader-mcp 的配置
sys.path.insert(0, str(Path(__file__).parent))
API_ID = os.getenv('TG_API_ID', '94575')
API_HASH = os.getenv('TG_API_HASH', 'a3406de8d171bb422bb6ddf3bbd800e2')
TG_READER_DIR = Path(__file__).parent.parent / 'tg-reader'
SESSION_PATH = TG_READER_DIR / 'tg_session'

try:
    from telethon import TelegramClient
    from telethon.tl.types import Message
except ImportError:
    print("请先安装 telethon: pip install telethon", file=sys.stderr)
    sys.exit(1)


async def get_client():
    if not SESSION_PATH.with_suffix('.session').exists():
        raise Exception(f"Session 不存在: {SESSION_PATH}.session，请先登录")
    client = TelegramClient(str(SESSION_PATH), int(API_ID), API_HASH)
    await client.connect()
    if not await client.is_user_authorized():
        raise Exception("Telegram 未登录")
    await client.catch_up()
    return client


async def read_channel(channel: str, limit: int = 20) -> dict:
    client = await get_client()
    try:
        entity = await client.get_entity(channel)
        title = getattr(entity, 'title', channel)
        messages = []
        async for msg in client.iter_messages(entity, limit=min(limit, 100)):
            if isinstance(msg, Message) and msg.text:
                messages.append({
                    "id": msg.id,
                    "date": msg.date.isoformat(),
                    "text": msg.text[:2000],
                    "views": msg.views,
                })
        return {"channel": title, "messages": messages, "count": len(messages)}
    finally:
        await client.disconnect()


async def search_channel(channel: str, keyword: str, limit: int = 20) -> dict:
    client = await get_client()
    try:
        entity = await client.get_entity(channel)
        title = getattr(entity, 'title', channel)
        messages = []
        async for msg in client.iter_messages(entity, search=keyword, limit=limit):
            if isinstance(msg, Message) and msg.text:
                messages.append({
                    "id": msg.id,
                    "date": msg.date.isoformat(),
                    "text": msg.text[:2000],
                })
        return {"channel": title, "keyword": keyword, "messages": messages, "count": len(messages)}
    finally:
        await client.disconnect()


async def list_dialogs(filter_kw: str = None, limit: int = 50) -> dict:
    client = await get_client()
    try:
        dialogs = []
        count = 0
        async for d in client.iter_dialogs():
            if count >= limit:
                break
            dtype = "频道" if d.is_channel else ("群组" if d.is_group else "私聊")
            username = getattr(d.entity, 'username', None)
            if filter_kw:
                if filter_kw.lower() not in d.name.lower() and \
                   not (username and filter_kw.lower() in username.lower()):
                    continue
            dialogs.append({"type": dtype, "name": d.name, "username": username})
            count += 1
        return {"dialogs": dialogs, "count": len(dialogs)}
    finally:
        await client.disconnect()


def run_async(coro):
    """在新 event loop 里同步跑 async 函数"""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class TGHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # 静默

    def send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False, indent=2).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', len(body))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        parts = [p for p in parsed.path.split('/') if p]
        qs = parse_qs(parsed.query)

        try:
            # GET /health
            if parts == ['health']:
                self.send_json({"status": "ok", "session": str(SESSION_PATH)})

            # GET /dialogs
            elif parts == ['dialogs']:
                filt = qs.get('filter', [None])[0]
                limit = int(qs.get('limit', [50])[0])
                result = run_async(list_dialogs(filt, limit))
                self.send_json(result)

            # GET /channels/{name}/messages
            elif len(parts) == 3 and parts[0] == 'channels' and parts[2] == 'messages':
                channel = parts[1]
                limit = int(qs.get('limit', [20])[0])
                result = run_async(read_channel(channel, limit))
                self.send_json(result)

            # GET /channels/{name}/search
            elif len(parts) == 3 and parts[0] == 'channels' and parts[2] == 'search':
                channel = parts[1]
                keyword = qs.get('keyword', [''])[0]
                limit = int(qs.get('limit', [20])[0])
                result = run_async(search_channel(channel, keyword, limit))
                self.send_json(result)

            else:
                self.send_json({"error": f"Unknown path: {self.path}"}, 404)

        except Exception as e:
            self.send_json({"error": str(e)}, 500)


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    server = HTTPServer(('127.0.0.1', port), TGHandler)
    print(f"TG Reader HTTP running on http://127.0.0.1:{port}")
    print(f"  GET /health")
    print(f"  GET /channels/{{name}}/messages?limit=20")
    print(f"  GET /channels/{{name}}/search?keyword=xxx")
    print(f"  GET /dialogs?filter=xxx")
    server.serve_forever()


if __name__ == '__main__':
    main()
