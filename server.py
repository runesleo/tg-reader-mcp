#!/usr/bin/env python3
"""
TG Reader MCP Server
Telegram 频道/群组消息读取 MCP 服务（只读）

安全说明：
- 仅提供只读功能，不能发送消息
- Session 文件存储在本地，不会传输到外部
- 所有数据处理在本地完成
"""

import os
import sys
import json
import asyncio
from datetime import datetime
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
    print("请先安装 telethon: pip install telethon", file=sys.stderr)
    sys.exit(1)

# ============ 配置 ============
# 使用 Telegram Desktop 公开凭证（不是用户私有信息）
API_ID = os.getenv('TG_API_ID', '94575')
API_HASH = os.getenv('TG_API_HASH', 'a3406de8d171bb422bb6ddf3bbd800e2')

# Session 文件路径（用户的登录凭证）
TG_READER_DIR = Path(__file__).parent.parent / 'tg-reader'
SESSION_PATH = TG_READER_DIR / 'tg_session'
# ==============================

# 创建 MCP Server
server = Server("tg-reader-mcp")


async def get_client():
    """获取 Telegram 客户端"""
    if not API_ID or not API_HASH:
        raise Exception("TG_API_ID 和 TG_API_HASH 未设置")

    if not SESSION_PATH.with_suffix('.session').exists():
        raise Exception(f"Session 文件不存在: {SESSION_PATH}.session，请先运行 tg-reader 登录")

    client = TelegramClient(str(SESSION_PATH), int(API_ID), API_HASH)
    await client.connect()

    if not await client.is_user_authorized():
        raise Exception("Telegram 未登录，请先运行 tg-reader 登录")

    return client


@server.list_tools()
async def list_tools() -> list[Tool]:
    """列出可用工具"""
    return [
        Tool(
            name="list_dialogs",
            description="列出所有 Telegram 对话（频道、群组、私聊）",
            inputSchema={
                "type": "object",
                "properties": {
                    "filter": {
                        "type": "string",
                        "description": "可选过滤关键词",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "返回数量限制（默认 50）",
                        "default": 50,
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="read_channel",
            description="读取 Telegram 频道/群组的消息",
            inputSchema={
                "type": "object",
                "properties": {
                    "channel": {
                        "type": "string",
                        "description": "频道/群组用户名（如 PolyBeats_Bot）或完整名称",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "获取消息数量（默认 20，最大 100）",
                        "default": 20,
                    },
                },
                "required": ["channel"],
            },
        ),
        Tool(
            name="search_channel",
            description="在 Telegram 频道/群组中搜索关键词",
            inputSchema={
                "type": "object",
                "properties": {
                    "channel": {
                        "type": "string",
                        "description": "频道/群组用户名",
                    },
                    "keyword": {
                        "type": "string",
                        "description": "搜索关键词",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "返回数量限制（默认 20）",
                        "default": 20,
                    },
                },
                "required": ["channel", "keyword"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """处理工具调用"""
    try:
        if name == "list_dialogs":
            result = await list_dialogs_impl(
                filter_keyword=arguments.get("filter"),
                limit=arguments.get("limit", 50),
            )
        elif name == "read_channel":
            result = await read_channel_impl(
                channel=arguments["channel"],
                limit=min(arguments.get("limit", 20), 100),  # 限制最大 100
            )
        elif name == "search_channel":
            result = await search_channel_impl(
                channel=arguments["channel"],
                keyword=arguments["keyword"],
                limit=arguments.get("limit", 20),
            )
        else:
            result = {"error": f"Unknown tool: {name}"}

        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

    except Exception as e:
        return [TextContent(type="text", text=json.dumps({"error": str(e)}, ensure_ascii=False))]


async def list_dialogs_impl(filter_keyword: str = None, limit: int = 50) -> dict:
    """列出对话"""
    client = await get_client()

    try:
        dialogs = []
        count = 0

        async for dialog in client.iter_dialogs():
            if count >= limit:
                break

            dtype = "频道" if dialog.is_channel else ("群组" if dialog.is_group else "私聊")
            username = getattr(dialog.entity, 'username', None)

            # 过滤
            if filter_keyword:
                name_match = filter_keyword.lower() in dialog.name.lower()
                username_match = username and filter_keyword.lower() in username.lower()
                if not name_match and not username_match:
                    continue

            dialogs.append({
                "type": dtype,
                "name": dialog.name,
                "username": username,
            })
            count += 1

        return {"dialogs": dialogs, "count": len(dialogs)}

    finally:
        await client.disconnect()


async def read_channel_impl(channel: str, limit: int = 20) -> dict:
    """读取频道消息"""
    client = await get_client()

    try:
        # 获取频道实体
        try:
            entity = await client.get_entity(channel)
            title = getattr(entity, 'title', channel)
        except Exception as e:
            return {"error": f"无法找到频道 {channel}: {e}"}

        # 获取消息
        messages = []
        async for message in client.iter_messages(entity, limit=limit):
            if isinstance(message, Message) and message.text:
                messages.append({
                    "id": message.id,
                    "date": message.date.isoformat(),
                    "text": message.text[:2000],  # 限制长度
                    "views": message.views,
                })

        return {
            "channel": title,
            "messages": messages,
            "count": len(messages),
        }

    finally:
        await client.disconnect()


async def search_channel_impl(channel: str, keyword: str, limit: int = 20) -> dict:
    """搜索频道消息"""
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


async def main():
    """启动 MCP Server"""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
