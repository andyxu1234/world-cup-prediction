# 辅助脚本

本目录包含一些辅助脚本，用于配置和测试服务。

## 脚本列表

### 1. get_telegram_chat_id.py

获取 Telegram Chat ID 的辅助工具。

**使用方法：**

```bash
cd server
python scripts/get_telegram_chat_id.py
```

**功能：**
- 验证 Bot Token 是否有效
- 获取与 Bot 交互的所有 Chat ID
- 生成 `.env` 配置示例

**前置条件：**
- 已在 `.env` 中配置 `TELEGRAM_BOT_TOKEN`

---

### 2. test_telegram.py

测试 Telegram 推送服务的完整测试脚本。

**使用方法：**

```bash
cd server
python scripts/test_telegram.py
```

**测试内容：**
1. 配置检查
2. Bot 连接测试
3. 消息发送测试
4. 消息格式化测试

**前置条件：**
- 已在 `.env` 中配置 `TELEGRAM_BOT_TOKEN` 和 `TELEGRAM_CHAT_IDS`
- 已安装依赖：`pip install httpx python-dotenv`

---

## 快速开始

### 配置 Telegram Bot

1. **创建 Bot**
   - 在 Telegram 中搜索 `@BotFather`
   - 发送 `/newbot` 创建新 Bot
   - 保存返回的 Bot Token

2. **获取 Chat ID**
   ```bash
   python scripts/get_telegram_chat_id.py
   ```

3. **配置环境变量**
   ```bash
   # 在 server/.env 中添加
   TELEGRAM_BOT_TOKEN=your_bot_token_here
   TELEGRAM_CHAT_IDS=your_chat_id_here
   ```

4. **测试配置**
   ```bash
   python scripts/test_telegram.py
   ```

5. **启动服务**
   ```bash
   uvicorn app.main:app --reload
   ```

6. **验证 API**
   - 访问 http://localhost:8000/docs
   - 测试 `/admin/telegram/test` 接口

---

## 常见问题

### Q: 如何获取群组的 Chat ID？

A: 
1. 将 Bot 添加到群组
2. 在群组中发送一条消息
3. 运行 `get_telegram_chat_id.py` 脚本
4. 脚本会显示群组的 Chat ID（通常是负数）

### Q: Bot Token 泄露了怎么办？

A: 
1. 立即向 @BotFather 发送 `/revoke` 命令
2. 选择你的 Bot
3. 生成新的 Token
4. 更新 `.env` 文件

### Q: 消息发送失败怎么办？

A: 检查以下几点：
1. Bot Token 是否正确
2. Chat ID 是否正确
3. Bot 是否被添加到群组（群组消息）
4. 用户是否与 Bot 开始过对话（个人消息）
5. 网络连接是否正常

### Q: 如何修改推送时间？

A: 编辑 `server/app/core/scheduler.py` 文件，找到 `telegram_daily_push` 任务，修改 `hour` 和 `minute` 参数：

```python
scheduler.add_job(
    daily_push,
    "cron",
    hour=22,      # 修改为 desired hour
    minute=0,     # 修改为 desired minute
    id="telegram_daily_push",
    replace_existing=True,
)
```

---

## 依赖

- Python 3.9+
- httpx
- python-dotenv（仅脚本需要）

安装依赖：
```bash
pip install httpx python-dotenv
```

---

## 注意事项

- **不要** 将 Bot Token 提交到 Git 仓库
- **不要** 在公开场合分享 Bot Token
- 生产环境建议使用环境变量或密钥管理服务
- 定期更换 Bot Token 以提高安全性
