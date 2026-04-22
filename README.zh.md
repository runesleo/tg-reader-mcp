# tg-reader-mcp

一个**只读**的 Telegram MCP Server。给你的 AI agent 看 TG 的能力，但拿不到"发消息"这把刀。

[English](./README.md)

## 为什么坚持只读

给 bot 装"发消息"很常见，给 AI agent 装就是另一回事。prompt 滑一下、工具调用幻觉一次、频道 ID 抄错一位，下一秒 agent 就替你在别人群里说话了。

这个 MCP 直接把刀收走。只开放六个工具：`list_dialogs` / `read_channel` / `search_channel` / `mark_read` / `get_contact` / `list_contacts_matching`。没有 send、没有 edit、没有 delete，想用都没接口。

## 六个工具做什么

- **`list_dialogs`** — 列出频道、群组、私聊。支持按关键词、未读状态、类型组合过滤，比如 `unread_dm` 只给你未读私聊。
- **`read_channel`** — 读取指定频道/群的消息。`since` 按 ISO 时间戳正向过滤，`offset_date` 反向翻页。
- **`search_channel`** — 在单个频道里搜关键词。
- **`mark_read`** — 标记对话为已读。AI 消化完一批新消息后清掉"未读"状态，下次轮询不会再重复拉。
- **`get_contact`** — 读一个联系人的卡片：first_name / last_name / username / phone / bio / **note** / is_contact / common_groups_count / last_seen。其中 `note` 是你在 TG 客户端手打的那条私人备注，走 MTProto 存在服务器上——agent 拿到就是结构化的 CRM 字段，不用你另建一张表。
- **`list_contacts_matching`** — 批量扫 DM，把 first_name（可选连 note）里含某子串的联系人一次性捞出来。如果你习惯把标签直接写进联系人名字或备注（比如付费读者标 `VIP`、某期群标 `BSC`），这个工具就是干这件事的。返回结构跟 `get_contact` 完全一致。

## 工作流长什么样

先用 Telethon 登一次你的 Telegram 账号（userbot），生成本地 `.session` 文件。MCP 启动时加载这个 session 读消息。每次请求前跑一次 `catch_up()` 保证不是缓存的陈旧数据。

```
你：看看 @durov 最近发了啥
AI：[调用 read_channel，channel="durov", limit=5]
    → Durov 过去 48 小时发了 3 条，核心内容：...
```

自用踩过一个坑：多个 MCP 进程连同一个 session 文件，SQLite 会锁冲突，轻则查询挂起重则 session 损坏。所以代码内置了**按 PID 隔离 session 副本**的机制，Claude Code 跟其他客户端同时跑也不打架。这是我自己用半年攒出来的点，也是这个 repo 跟其他 Telegram MCP 的主要差异。

## 安装和登录

### 1. 拉代码

```bash
git clone https://github.com/runesleo/tg-reader-mcp.git
cd tg-reader-mcp
uv venv
source .venv/bin/activate
uv pip install -e .
```

### 2. 登录一次 Telegram

需要一个 Telethon 的 `.session` 文件。最简方式——跑一次交互式登录脚本：

```python
# login.py
from telethon import TelegramClient
client = TelegramClient('tg_session', 94575, 'a3406de8d171bb422bb6ddf3bbd800e2')
client.start()
print("登录成功，tg_session.session 已创建")
```

```bash
python login.py
# 输入手机号 + Telegram 发来的验证码 + 开启了 2FA 再输密码
```

当前目录下会生成 `tg_session.session`，这就是你的登录凭证。

> 上面的 `API_ID` / `API_HASH` 是 Telegram Desktop 的公开凭证，可以直接用。想要自己的（提升限流配额或独立审计），去 [my.telegram.org](https://my.telegram.org) 申请，然后设置 `TG_API_ID` / `TG_API_HASH` 环境变量。

### 3. 接入 Claude Code

```bash
claude mcp add tg-reader -s user \
  -e TG_SESSION_PATH=/absolute/path/to/tg_session.session \
  -- /absolute/path/to/.venv/bin/python /absolute/path/to/server.py
```

路径换成你本地的真实位置。

### 4. 接入其他 AI agent

任何兼容 MCP 协议的客户端都能用（Cursor / Claude Desktop / 自己写的 agent）。指向 `server.py`，用 `TG_SESSION_PATH` 告诉它 session 文件在哪就行。

## ⚠️ 用之前请读完这一段

这是 **userbot**，不是 bot token。两个概念差得远：

- 你是拿**自己的 Telegram 账号**登录的。每次读取对 Telegram 来说都是"你本人在读"。
- Telegram 的服务条款允许 userbot，但明确禁止骚扰、大规模抓取、冒充。别去大批量轮询、别比人工读更快、别把输出拼成垃圾信息管道。
- **推荐用专门的小号**跑自动化。一旦触发限制或封号，损失的是小号，不是你的主号。
- `.session` 文件**就是**你的登录凭证，按密码级别保管。别提交到 git、别发给别人。`.gitignore` 已经覆盖 `*.session` 和 `*.session-journal`。

Telegram ToS：[telegram.org/tos](https://telegram.org/tos) · API ToS：[core.telegram.org/api/terms](https://core.telegram.org/api/terms)

## 环境要求

- Python 3.10 以上
- `mcp>=1.0.0`、`telethon>=1.34.0`（`uv pip install -e .` 一条命令搞定）
- 一个能用 Telethon 登录的 Telegram 账号
- 就这些。不需要额外 API key、不连数据库、不走第三方服务。

## 支持的输入

| 参数 | 示例 | 解析方式 |
|------|------|---------|
| 频道 username | `durov` | 公开频道 |
| 群组 username | `runesgang` | 公开群组 |
| 频道完整名 | `Durov's Channel` | Telethon `get_entity` 模糊匹配 |
| ISO 时间戳 | `2026-04-13T00:00:00+08:00` | `since` / `offset_date` 用 |

## 典型用法

**每日摘要**：`list_dialogs` 拿 `filter="unread_channel"` → 逐个 `read_channel` → LLM 汇总 → `mark_read` 清未读队列。

**信号研究**：`search_channel` 在某个 alpha 频道搜关键词 → 把结果丢给 LLM 提炼观点。

**跨频道监听**：N 个频道循环 `read_channel`，`since=<上次轮询时间>`，只返回新消息。

## 真实示例频道

[@runesgangalpha](https://t.me/runesgangalpha) — 我的公开频道，用的就是这个 MCP 在做 Polymarket / AI / Crypto 信号的读取和消化，算是这个工作流的活样本。

## 当前版本限制（0.2.0）

- **不下载媒体**——只读文本。图片、视频、语音返回的 text 字段是空的。
- **反应/转发链未暴露**——`views` 浏览量有，但 reactions、forward chain 拿不到。
- **`since` 模式的翻页上限 500 条**——日常够用，深度回溯要配合 `offset_date` 多轮拉取。
- **`list_contacts_matching` 带 `match_note=true` 是 O(N) 成本**——每扫一个 DM 要发一次 `GetFullUser`，几千条私聊会慢。`limit` 保持小、`dialog_scan_limit`（默认 500）按实际需要设。

## Roadmap

**读的广度**
- [ ] 媒体下载（图片、文件、语音）
- [ ] Reactions 和转发链
- [ ] 论坛式群组的 topic/thread 支持

**性能**
- [ ] 跨请求的连接池复用
- [ ] 高频频道可选 Redis 缓存

**部署形态**
- [ ] Docker 镜像（挂载 session 文件）
- [ ] Remote MCP（HTTP 传输）多客户端方案

## 关于作者

*关于作者：Leo（[@runes_leo](https://x.com/runes_leo)），AI x Crypto 独立构建者。在 [Polymarket](https://polymarket.com/?r=githuball&via=runes-leo&utm_source=github&utm_content=tg-reader-mcp) 做量化交易，用 Claude Code 和 Codex 搭建数据分析与自动化交易系统。*

[leolabs.me](https://leolabs.me)：文章 · 社群 · 开源工具 · 独立项目 · 全平台账号

[X 订阅](https://x.com/runes_leo/creator-subscriptions/subscribe)：付费内容周更，或请我喝杯咖啡 😁

*Learn in public, Build in public.*

## License

MIT — 详见 [LICENSE](./LICENSE)。
