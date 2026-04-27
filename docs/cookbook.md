# tg-reader-mcp · Tool Cookbook

本文档与 `server.py` 中 `@server.list_tools()` 注册的 **6 个** MCP tool 一一对应（实现上为 Python `mcp.types.Tool`，无 `@mcp.tool()` 装饰器）。每个 tool 下列 **3 组**「调用参数 → 预期响应形态」；具体字段值随你的账号与 Telegram 数据而变，示例中的占位值仅说明结构。

**通用前提**：本机存在已授权的 Telethon `.session`（见 README），且环境变量 `TG_SESSION_PATH` 等配置正确。错误时 MCP 返回 JSON，`error` 键为人类可读说明。

---

## `list_dialogs`

列出对话（频道 / 群 / 私聊），可选组合过滤 `unread` + `dm`/`channel`/`group`，或按标题 / username 子串匹配。

### 示例 1：只看有未读的私聊

**调用参数**

```json
{ "filter": "unread_dm", "limit": 30 }
```

**预期输出**

- 顶层：`dialogs`（数组）、`count`（整数，≤ `limit`）。
- 每条 dialog：`type` 恒为 `"dm"`；`name`、`username`（可能 `null`）、`unread_count` ≥ 1。
- 若当前无未读私聊：`dialogs` 为空数组，`count` 为 `0`。

```json
{
  "dialogs": [
    {
      "type": "dm",
      "name": "Alice",
      "username": "alice",
      "unread_count": 3
    }
  ],
  "count": 1
}
```

### 示例 2：未读频道 digest 列表

**调用参数**

```json
{ "filter": "unread_channel", "limit": 50 }
```

**预期输出**

- 仅 `type: "channel"` 且 `unread_count > 0` 的项。
- 用于后续对每条再调 `read_channel` / `mark_read`。

### 示例 3：按名称关键词筛选（非 unread 专用分支）

**调用参数**

```json
{ "filter": "alpha", "limit": 20 }
```

**预期输出**

- 标题 `name` 或 `username`（不区分大小写）包含子串 `alpha` 的对话，类型不限。
- 匹配不到时 `dialogs: []`，`count: 0`。

---

## `read_channel`

读取指定频道或群的**文本消息**（无文本或非 `Message` 实体会被跳过）。支持 `since`（严格晚于该 ISO 时间）与 `offset_date`（向前翻页）。

### 示例 1：拉最近 N 条

**调用参数**

```json
{ "channel": "durov", "limit": 10 }
```

**预期输出**

- `channel`：解析后的频道标题字符串。
- `messages`：每项含 `id`、`date`（ISO）、`text`（最长截断 2000 字符）、`views`（可能 `null`）。
- `count`：`messages.length`。
- 若满 `limit` 条，可能带 `next_offset_date`（最后一条的 `date`），供下次传 `offset_date` 翻页。

```json
{
  "channel": "Durov's Channel",
  "messages": [
    {
      "id": 12345,
      "date": "2026-04-26T12:00:00+00:00",
      "text": "…",
      "views": 100000
    }
  ],
  "count": 1,
  "next_offset_date": "2026-04-26T12:00:00+00:00"
}
```

### 示例 2：增量同步（只取某时点之后）

**调用参数**

```json
{
  "channel": "runesgangalpha",
  "limit": 50,
  "since": "2026-04-20T00:00:00+08:00"
}
```

**预期输出**

- 所有消息的 `date` 均 **严格晚于** `since`；服务端会多抓一些再截断，最多约 `min(limit*5, 500)` 条扫描窗口内满足条件的消息。
- 若没有新消息：`messages: []`，`count: 0`，通常无 `next_offset_date`。

### 示例 3：无法解析的 channel

**调用参数**

```json
{ "channel": "definitely_nonexistent_channel_xyz", "limit": 5 }
```

**预期输出**

```json
{
  "error": "Unable to resolve channel definitely_nonexistent_channel_xyz: …"
}
```

（冒号后为 Telethon 原始错误信息。）

---

## `search_channel`

在**单个**频道/群内按关键词搜索（Telethon `iter_messages(..., search=keyword)`）。

### 示例 1：群内搜关键词

**调用参数**

```json
{ "channel": "runesgangalpha", "keyword": "Polymarket", "limit": 15 }
```

**预期输出**

```json
{
  "channel": "Runes Gang Alpha",
  "keyword": "Polymarket",
  "messages": [
    {
      "id": 999,
      "date": "2026-04-15T08:30:00+00:00",
      "text": "…提到 Polymarket 的正文…"
    }
  ],
  "count": 1
}
```

### 示例 2：限制条数上限内无命中

**调用参数**

```json
{ "channel": "durov", "keyword": "zzzznomatchzzzz", "limit": 20 }
```

**预期输出**

- `messages: []`，`count: 0`；`channel`、`keyword` 仍有值。

### 示例 3：channel 合法但无搜索权限或实体错误

**调用参数**

依环境而定，例如私有群未加入时解析失败。

**预期输出**

- 与 `read_channel` 类似，可能返回顶层 `"error": "Unable to resolve channel …"`；或能解析但 `messages` 为空（无匹配）。

---

## `mark_read`

对指定对话发送已读回执（`send_read_acknowledge`），清除未读角标。

### 示例 1：标已读某个 username

**调用参数**

```json
{ "channel": "durov" }
```

**预期输出**

```json
{
  "success": true,
  "channel": "Durov's Channel",
  "message": "Marked Durov's Channel as read"
}
```

（`channel` / `message` 中的名称来自实体 `title` 或用户 `first_name`。）

### 示例 2：用群标题解析

**调用参数**

```json
{ "channel": "Team Standup" }
```

**预期输出**

- 成功时同上结构，`success: true`。
- 若标题不唯一或无法解析：顶层 `"error": "Unable to resolve dialog Team Standup: …"`。

### 示例 3：session 未授权时

**调用参数**

```json
{ "channel": "any" }
```

**预期输出**

- MCP 层捕获异常，返回 JSON 单行或紧凑对象：`{"error": "Telegram session is not authorized. Re-run the Telethon login."}` 或 `"Session file not found…"` 等。

---

## `get_contact`

解析**单个用户**（非频道），返回联系级详情；需 `GetFullUserRequest` 的字段在失败时见 `full_user_error`。

### 示例 1：按 username 查询

**调用参数**

```json
{ "username": "durov" }
```

**预期输出**

```json
{
  "id": 123456789,
  "username": "durov",
  "first_name": "Pavel",
  "last_name": "Durov",
  "phone": null,
  "is_contact": false,
  "is_mutual_contact": false,
  "bio": "…",
  "note": null,
  "common_groups_count": 0,
  "last_seen": "2026-04-26T10:00:00+00:00",
  "full_user_error": null
}
```

- `last_seen` 可能是 ISO 字符串，或隐私限制时的类型名如 `"UserStatusRecently"`。
- 已为联系人且客户端存有号码/备注时，`phone` / `note` 可能非空。

### 示例 2：传入数字 user id

**调用参数**

```json
{ "username": "123456789" }
```

**预期输出**

- 与示例 1 相同字段集合；能解析则填充，否则 `error` 说明无法 resolve。

### 示例 3：channel 用户名误传给 get_contact

**调用参数**

```json
{ "username": "telegram" }
```

**预期输出**

```json
{
  "error": "telegram is not a user (got Channel)"
}
```

---

## `list_contacts_matching`

扫描 **DM 对话**（频道/群不计入 `dialog_scan_limit` 扫描预算），按 `pattern` 匹配 `first_name` / `last_name`；`match_note: true` 时再对备注做匹配（每对话可能额外 FullUser 调用）。

### 示例 1：按显示名子串找 VIP 联系人

**调用参数**

```json
{ "pattern": "VIP", "limit": 30, "dialog_scan_limit": 200 }
```

**预期输出**

```json
{
  "pattern": "VIP",
  "match_note": false,
  "dialogs_scanned": 42,
  "contacts": [
    {
      "id": 111,
      "username": "bob",
      "first_name": "Bob",
      "last_name": "VIP",
      "phone": null,
      "is_contact": true,
      "is_mutual_contact": false,
      "bio": null,
      "note": null,
      "common_groups_count": 2,
      "last_seen": "UserStatusLastWeek",
      "full_user_error": null
    }
  ],
  "count": 1,
  "truncated": false
}
```

- `truncated`: 命中数达到 `limit` 时为 `true`。
- `dialogs_scanned`: 实际扫过的 DM 条数（≤ `dialog_scan_limit`）。

### 示例 2：同时匹配备注（高成本）

**调用参数**

```json
{ "pattern": "BSC", "match_note": true, "limit": 10, "dialog_scan_limit": 100 }
```

**预期输出**

- 名字未命中但 `note` 含 `bsc` 的用户会出现在 `contacts`。
- `dialogs_scanned` 可能小于 `dialog_scan_limit`（因 `limit` 或对话耗尽提前停止）。

### 示例 3：空 pattern（应失败）

**调用参数**

```json
{ "pattern": "   " }
```

**预期输出**

```json
{
  "error": "pattern must be a non-empty string"
}
```

（实现为 `ValueError`，经 `call_tool` 异常处理返回。）

---

## 参考

- 源码：`server.py`（`list_tools`、`call_tool`、各 `*_impl`）。
- 客户端配置：仓库根目录 `README.md`（Claude Desktop / Claude Code）。
