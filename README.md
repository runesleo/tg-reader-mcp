# tg-reader-mcp

**中文：** 只读 Telegram MCP：用你本机已登录的账号，让 AI 读频道、群、私聊与联系人卡片；不发消息、不改记录、不删内容（仅提供 `mark_read` 清未读）。  
**English:** [README.en.md](./README.en.md)

---

## Quick Start

### 1. 安装

```bash
git clone https://github.com/runesleo/tg-reader-mcp.git
cd tg-reader-mcp
uv venv && source .venv/bin/activate
uv pip install -e .
```

### 2. 准备 Telethon session

需要本机有一份已授权的 `.session`（userbot 登录，非 Bot Token）。最小示例：

```python
# login.py（在任意目录运行一次即可）
from telethon import TelegramClient
client = TelegramClient('tg_session', 94575, 'a3406de8d171bb422bb6ddf3bbd800e2')
client.start()
print("OK: tg_session.session")
```

```bash
python login.py
```

默认 `API_ID` / `API_HASH` 与 Telegram Desktop 公开凭据一致。若要自建应用，在 [my.telegram.org](https://my.telegram.org) 申请并设置环境变量 `TG_API_ID`、`TG_API_HASH`。

### 3. Claude Desktop（`claude_desktop_config.json`）

将下面 **`mcpServers` 里的键值对** 合并进你现有配置文件的 `mcpServers` 对象中（路径示例：macOS `~/Library/Application Support/Claude/claude_desktop_config.json`）。把占位路径换成你的绝对路径。

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

可选环境变量：`TG_API_ID`、`TG_API_HASH`（覆盖默认 Telegram Desktop 凭据）。

### 4. Claude Code（CLI）

```bash
claude mcp add tg-reader -s user \
  -e TG_SESSION_PATH=/absolute/path/to/tg_session.session \
  -- /absolute/path/to/tg-reader-mcp/.venv/bin/python /absolute/path/to/tg-reader-mcp/server.py
```

---

## Tools（与源码一致）

以下名称与 `server.py` 中 `@server.list_tools()` 注册项一一对应。

### `list_dialogs`

- **用途：** 列出对话（频道 / 群 / 私聊），支持组合过滤与关键词。
- **参数：**
  - `filter`（可选）：如 `unread`、`unread_dm`、`unread_channel`、`channel`、`group`、`dm` 等组合；否则按对话标题 / username 子串匹配。
  - `limit`（可选，默认 `50`）：最多返回条数。
- **示例：**

```json
{ "filter": "unread_dm", "limit": 30 }
```

### `read_channel`

- **用途：** 读取指定频道或群的近期文本消息。
- **参数：**
  - `channel`（必填）：username（如 `durov`）或可被 Telethon 解析的标题。
  - `limit`（可选，默认 `20`，上限 `100`）。
  - `since`（可选）：ISO 8601 时间，仅返回**严格晚于**该时间的消息。
  - `offset_date`（可选）：ISO 时间，从该时刻**向前翻页**（配合返回的 `next_offset_date`）。
- **示例：**

```json
{ "channel": "durov", "limit": 10, "since": "2026-04-20T00:00:00+08:00" }
```

### `search_channel`

- **用途：** 在**单个**频道/群内按关键词搜索消息。
- **参数：**
  - `channel`（必填）
  - `keyword`（必填）
  - `limit`（可选，默认 `20`）
- **示例：**

```json
{ "channel": "runesgangalpha", "keyword": "Polymarket", "limit": 15 }
```

### `mark_read`

- **用途：** 将某对话标为已读（清未读角标）。
- **参数：**
  - `channel`（必填）：频道、群或私聊标识（username 或标题）。
- **示例：**

```json
{ "channel": "某群名称或 username" }
```

### `get_contact`

- **用途：** 查询**单个用户**的联系级信息（含 bio、共同群数量、`last_seen` 等）。`note` 为你在官方客户端里写的**仅自己可见**的联系人备注（需对方已是联系人等条件才有电话/备注等字段）。
- **参数：**
  - `username`（必填）：不带 `@` 的 username 或数字 user id。
- **示例：**

```json
{ "username": "durov" }
```

### `list_contacts_matching`

- **用途：** 扫描私聊对话，找出 `first_name` / `last_name`（可选 `note`）中包含子串的联系人，返回结构与 `get_contact` 一致。`match_note=true` 时会对每个扫描到的 DM 调用 FullUser，成本随对话数上升，请控制 `limit` 与 `dialog_scan_limit`。
- **参数：**
  - `pattern`（必填）：非空子串，大小写不敏感。
  - `match_note`（可选，默认 `false`）
  - `limit`（可选，默认 `30`，上限 `100`）
  - `dialog_scan_limit`（可选，默认 `500`）：最多扫描多少条 DM。
- **示例：**

```json
{ "pattern": "VIP", "match_note": true, "limit": 20, "dialog_scan_limit": 200 }
```

---

## 使用场景

1. **未读频道 digest：** `list_dialogs` 过滤 `unread_channel` → 对每条调用 `read_channel` → 总结后 `mark_read`。
2. **增量监控：** 对固定频道保存上次拉取时间，下次用 `since` 只取新消息。
3. **单频道检索：** Alpha 群里搜关键词，用 `search_channel` 定位历史讨论。
4. **私域 CRM：** 把标签写在联系人备注里，用 `list_contacts_matching` 批量拉出对应人群。
5. **核对对方资料：** 用 `get_contact` 拉 bio、共同群数量等辅助判断账号背景。

---

## 重要说明

- 这是 **userbot**：行为等同于你的个人账号在读消息；请遵守 Telegram [ToS](https://telegram.org/tos) 与 [API 条款](https://core.telegram.org/api/terms)，避免高频轮询与大规模抓取。
- `.session` 等同于登录凭证：勿提交仓库、勿外泄。仓库 `.gitignore` 已忽略常见 session 文件。
- 当前实现以**文本**为主；媒体、反应链等能力见仓库内其他说明或 issue。

## License

MIT — 见 [LICENSE](./LICENSE)。
