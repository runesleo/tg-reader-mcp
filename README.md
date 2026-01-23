# TG Reader MCP Server

Telegram 频道/群组消息读取 MCP 服务（**只读**）。

## 安全说明

- **只读功能**：只能读取消息，不能发送消息
- **本地运行**：所有数据处理在本地完成，不传输到外部
- **Session 文件**：复用 `tg-reader` 的登录状态，存储在 `../tg-reader/tg_session.session`

## 前置条件

1. 确保 `tg-reader` 已登录（运行过 `python tg_reader.py --list`）
2. Session 文件存在于 `../tg-reader/tg_session.session`

## 安装

```bash
cd tg-reader-mcp
uv venv
source .venv/bin/activate
uv pip install -e .
```

## 配置 Claude Code

```bash
claude mcp add tg-reader -s user -- /Users/zhangxu/Projects/tg-reader-mcp/.venv/bin/python /Users/zhangxu/Projects/tg-reader-mcp/server.py
```

## 可用工具

| 工具 | 描述 | 参数 |
|------|------|------|
| `list_dialogs` | 列出所有对话 | `filter`, `limit` |
| `read_channel` | 读取频道消息 | `channel`, `limit` |
| `search_channel` | 搜索频道消息 | `channel`, `keyword`, `limit` |

## 使用示例

在 Claude Code 中：
- "帮我看看 PolyBeats 最新消息"
- "搜索 alphacalc 频道中关于套利的消息"
- "列出我所有的 Telegram 对话"
