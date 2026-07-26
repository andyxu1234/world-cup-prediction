# Telegram 推送配置指南

本指南将帮助你配置 Telegram Bot，实现每日比赛和预测信息推送。

## 1. 创建 Telegram Bot

1. 在 Telegram 中搜索 `@BotFather` 并开始对话
2. 发送 `/newbot` 命令
3. 按提示输入 Bot 名称和用户名（用户名必须以 `bot` 结尾）
4. 保存返回的 **Bot Token**（格式类似：`123456789:ABCdefGHIjklMNOpqrsTUVwxyz`）

## 2. 获取 Chat ID

### 个人 Chat ID

1. 在 Telegram 中搜索 `@userinfobot`
2. 向它发送任意消息
3. 它会返回你的 **Chat ID**（纯数字）

### 群组 Chat ID

1. 将你的 Bot 添加到群组
2. 在群组中发送一条消息
3. 访问：`https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
4. 在返回的 JSON 中找到 `chat.id`（通常为负数，如 `-1001234567890`）

## 3. 配置环境变量

在 `server/.env` 文件中添加以下配置：

```bash
# Telegram Bot 推送
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_CHAT_IDS=123456789,-1001234567890
```

**说明：**
- `TELEGRAM_BOT_TOKEN`：从 @BotFather 获取的 Bot Token
- `TELEGRAM_CHAT_IDS`：推送目标 Chat ID，多个用逗号分隔
  - 个人 Chat ID：纯数字（如 `123456789`）
  - 群组 Chat ID：负数（如 `-1001234567890`）

## 4. 测试配置

启动后端服务后，可以通过以下 API 测试配置：

### 测试 Bot 连接

```bash
curl http://localhost:8000/api/v1/admin/telegram/test
```

成功响应：
```json
{
  "status": "ok",
  "message": "Telegram Bot 连接成功",
  "bot": {
    "id": 123456789,
    "username": "your_bot_username",
    "first_name": "Your Bot Name"
  }
}
```

### 查看配置状态

```bash
curl http://localhost:8000/api/v1/admin/telegram/status
```

### 手动触发推送

```bash
curl -X POST http://localhost:8000/api/v1/admin/telegram/push
```

### 发送测试消息

```bash
curl -X POST "http://localhost:8000/api/v1/admin/telegram/send?message=Hello%20from%20World%20Cup%20Prediction!"
```

## 5. 定时推送

系统已配置每日自动推送：

| 时间 | 内容 |
|------|------|
| 每日 22:00 | 今日比赛预测、昨日赛果 |
| 每周一 22:00 | AI 模型排行榜（额外） |

## 6. 推送内容示例

### 今日比赛预测

```
📅 2026年07月24日 比赛预测
共 3 场比赛

🏆 English Premier League
────────────────────
⏰ 20:00 | *曼联* vs *利物浦*
  🏠 共识: *主胜* | 热门比分: 2-1 (3票)

⏰ 22:00 | *阿森纳* vs *切尔西*
  🤝 共识: *平局* | 热门比分: 1-1 (4票)
```

### 昨日赛果

```
📋 昨日赛果
共 2 场比赛

🏆 English Premier League
• 曼城 *3* - *1* 热刺
• 纽卡斯尔 *2* - *0* 西汉姆
```

## 7. 故障排查

### Bot Token 无效

- 确认 Token 格式正确（`数字:字母数字字符串`）
- 向 @BotFather 发送 `/mybots` 查看你的 Bot 列表

### 消息发送失败

- 确认 Chat ID 正确
- 确认 Bot 已被添加到群组（群组消息）
- 确认用户已与 Bot 开始过对话（个人消息）

### 查看日志

```bash
# 查看后端日志
tail -f /tmp/worldcup-server.log | grep -i telegram
```

## 8. 安全提示

- **不要** 将 Bot Token 提交到 Git 仓库
- **不要** 在公开场合分享 Bot Token
- 定期更换 Bot Token（通过 @BotFather 的 `/revoke` 命令）
- 生产环境建议使用环境变量或密钥管理服务

## 9. 高级配置

### 多群组推送

在 `.env` 中配置多个 Chat ID：

```bash
TELEGRAM_CHAT_IDS=123456789,-1001234567890,-1009876543210
```

### 自定义推送时间

修改 `server/app/core/scheduler.py` 中的 `telegram_daily_push` 任务：

```python
# 每日 22:00 推送
scheduler.add_job(
    daily_push,
    "cron",
    hour=22,      # 修改小时
    minute=0,     # 修改分钟
    id="telegram_daily_push",
    replace_existing=True,
)
```

### 禁用推送

在 `.env` 中清空配置即可禁用：

```bash
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_IDS=
```

## 10. API 参考

| 端点 | 方法 | 说明 |
|------|------|------|
| `/admin/telegram/test` | GET | 测试 Bot 连接 |
| `/admin/telegram/status` | GET | 查看配置状态 |
| `/admin/telegram/push` | POST | 手动触发每日推送 |
| `/admin/telegram/send` | POST | 发送自定义消息 |

---

如有问题，请查看日志或联系管理员。
