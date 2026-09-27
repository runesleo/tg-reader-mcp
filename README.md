# tg-reader-mcp

**中文：** Telegram MCP：复用你本机已登录的账号读取频道、群、私聊与联系人卡片，并提供受保护的 `send_message` / `join_chat` 写操作。发送默认做精确文本去重；不提供编辑或删除消息。  
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

### 2. 一次性登录 + 自检

```bash
tg-reader-init
```

首次运行会自动：

- 使用 Telegram **个人账号**登录（非 Bot Token）；按提示输入手机号、验证码，若开启 2FA 再输入密码。
- 创建或复用 `~/.tg-reader-mcp/tg_session.session`，并收紧本地文件权限。
- 做一次只读 dialog 拉取自检，确认 session 可用。
- 输出 Claude Desktop 可直接复制的 JSON 和 Claude Code 可直接执行的命令；session 与可执行文件路径都已展开，无需手填绝对路径。

默认 `API_ID` / `API_HASH` 与 Telegram Desktop 公开凭据一致。若要使用自己的应用凭据，可先在 [my.telegram.org](https://my.telegram.org) 申请，然后运行：

```bash
TG_API_ID=your_id TG_API_HASH=your_hash tg-reader-init
```

如果直连 Telegram 失败，可用 `TG_PROXY_URL`（支持 `http://`、`socks5://`、`socks4://`）：

```bash
TG_PROXY_URL=http://127.0.0.1:7897 tg-reader-init
```

初始化时显式设置的 `TG_API_ID`、`TG_API_HASH`、`TG_PROXY_URL` 会自动带进生成的 MCP 配置，避免首次登录与后续运行使用不同参数。

### 3. 接入 MCP 客户端

- **Claude Desktop：** 将 `tg-reader-init` 输出的 `tg-reader` 条目合并到现有 `mcpServers` 对象，然后重启 Claude Desktop。
- **Claude Code：** 直接运行 `tg-reader-init` 输出的 `claude mcp add ...` 命令。


---

## Tools（与源码一致）

以下名称与 `server.py` 中 `@server.list_tools()` 注册项一一对应。

### `download_media`

- **用途：** 显式下载某条 Telegram 消息附带的 photo / image / video / document 到本地路径；远端只读。
- **参数：** `channel`（必填）、`message_id`（必填）、`out_dir`（可选，默认 `~/.cache/tg-media`）。
- **示例：**

```json
{ "channel": "durov", "message_id": 12345 }
```

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

- **用途：** 读取指定频道或群的近期文本与媒体消息元数据；每条消息同时返回 `from_me`、`sender_id`、`sender`，媒体消息额外带 `media` / `media_hint`。
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

### `send_message`

- **用途：** 向私聊、群或频道发送一条纯文本消息。默认在最近 600 秒内做**精确文本去重**，避免重复发送；可用 `dedupe_window_seconds` 调整，最大 24 小时。
- **参数：** `channel`（必填）、`text`（必填）、`reply_to`（可选）、`dedupe_window_seconds`（可选，默认 `600`）。
- **安全：** 这是远端写操作，MCP 客户端应要求显式确认。

```json
{ "channel": "username", "text": "hello", "dedupe_window_seconds": 86400 }
```

### `join_chat`

- **用途：** 通过私有邀请链接或公开 username 加入 Telegram 群/频道；已加入时幂等返回，不重复改变成员状态。
- **参数：** `target`（必填）：如 `https://t.me/+...` 或公开 username / `t.me/...` 链接。
- **安全：** 这是远端写操作，MCP 客户端应要求显式确认。

```json
{ "target": "https://t.me/+invite_hash" }
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
- 媒体不会自动下载：`read_channel` / `search_channel` 只返回媒体类型与提示；需要本地文件时显式调用 `download_media`。反应链等更丰富能力仍不在当前工具范围。

## License

MIT — 见 [LICENSE](./LICENSE)。
