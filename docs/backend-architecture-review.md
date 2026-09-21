# 后端架构体检报告 — world-cup-prediction

> 审查范围：`server/app/`（FastAPI + SQLAlchemy 2.0 async + Alembic + APScheduler）
> 审查时间：2026-08-11
> 总体结论：**分层结构合理，但安全与可扩展性存在 P0 级缺陷，公网部署前必须整改。**

---

## 一、架构优点（先说好的）

- **分层清晰**：`api / services / models / schemas / core` 职责分离，24 个 service 文件把同步、预测、积分榜、赔率、Telegram 等能力拆得比较干净。
- **异步栈完整**：SQLAlchemy 2.0 `AsyncSession` + `async_sessionmaker`，连接池配了 `pool_pre_ping` 和 `pool_recycle`，对长耗时 AI 调用后的死连接有兜底。
- **Alembic 迁移体系在**：有独立的 `alembic/` 目录与 `entrypoint.sh` 启动自动 `upgrade head`。
- **缓存层存在**：`cachetools.TTLCache` 分只读/用户两类 TTL，并有命中率统计接口。
- **配置外部化**：大部分密钥走 `pydantic-settings` + `.env`；Windows/远程 MySQL 的驱动与事件循环坑都有注释说明（engineering 素质不错）。

---

## 二、P0 — 安全（公网部署前必修，否则等于开门）

### 1. 用户接口完全无鉴权，user_id 由客户端随意指定
- **现象**：`app/core/auth.py` 的 `verify_token()` **全项目从未被调用**（grep 确认仅定义）。`/users/vote`、`/users/upload-avatar`、`/users/profile`、`/users/update-profile` 等全部用 `user_id: int = Query(...)` 直接从请求取身份。
- **影响**：**任意用户可冒充/篡改他人账户**——改 `user_id` 就能替别人投票、覆盖别人头像、改别人资料。登录时生成的 JWT 从未被校验，等于没有认证。
- **修复**：
  - 新增依赖 `get_current_user`：`Authorization: Bearer <token>` → `verify_token` → 查库返回 `User`，所有受保护接口用 `Depends(get_current_user)`。
  - 路由内一律用 `current_user.id`，**不再信任客户端传入的 user_id**。

### 2. /admin/* 全部路由零鉴权
- **现象**：`app/api/v1/admin.py` 30+ 个路由（同步流水线、生成预测、删/加 VIP、Telegram 推送、清缓存）无任何 `Depends` 鉴权。
- **影响**：能触达后端的任何人可：触发全量同步、花 AI 网关费用生成预测、删除 VIP、向公众频道发消息、清空缓存。
- **修复**：加 `require_admin` 依赖（强令牌/共享密钥 + IP 白名单）；高危操作加审计日志。

### 3. JWT 默认密钥硬编码
- **现象**：`config.py` 中 `SECRET_KEY: str = "world-cup-prediction-2026-secret-key-change-in-production"`。
- **影响**：一旦补上 token 校验而未改密钥，攻击者可拿已知字符串伪造任意用户 token。
- **修复**：生产强制从 `.env` 读 `SECRET_KEY`，缺失即启动失败（`assert settings.SECRET_KEY != default`）。

### 4. Highlightly API Key 明文硬编码在源码
- **现象**：`config.py:47` `HIGHLIGHTLY_API_KEY = "bdc14b1e-4982-4bd4-8ec0-aeb38ce0b634"`。
- **影响**：凭据随代码泄露，可被冒用消耗配额。
- **修复**：移入 `.env`，config 仅留占位；并**立即轮换该 key**。

### 5. CORS 配置矛盾
- **现象**：`main.py` `allow_origins=["*"]` + `allow_credentials=True`。
- **影响**：等价于任意源带凭证访问（Starlette 会回显请求 Origin）。
- **修复**：`allow_origins` 限定为已知前端域名列表。

---

## 三、P1 — 可靠性 / 可扩展（多 worker 或规模上来就炸）

### 6. 调度器在进程内启动，无分布式锁/JobStore
- **现象**：`scheduler.py` 的 `AsyncIOScheduler` 在 `main.py` lifespan 里 `start_scheduler()`。无 jobstore、无锁、无 misfire 策略。
- **影响**：标准多 worker 部署时，**每个进程各跑一份 cron** → 同步、AI 预测生成、Telegram 推送被重复执行 N 倍（重复烧钱、重复推送、数据竞争）。
- **修复**：调度器独立为单独 beat 进程；或用 Redis/DB 分布式锁保证单点执行；或明确单 worker 部署并在文档声明。

### 7. 缓存在进程内存，多 worker 不一致
- **现象**：`cache.py` 用模块级 `TTLCache` 全局变量。
- **影响**：多 worker 时各进程缓存互相看不到；`/cache/clear` 与 `/admin/cache/clear` 只清当前进程。
- **修复**：换 Redis 做共享缓存；否则锁定单 worker 并写进部署文档。

### 8. 无全局异常处理，内部异常直接回显
- **现象**：几乎每个路由手写 `try/except → raise HTTPException(500, detail=f"...{e}")`，把原始异常（SQL、堆栈）返回给客户端，且无统一错误结构。
- **影响**：信息泄露 + 前端无法稳定解析错误。
- **修复**：加 `@app.exception_handler(Exception)` / `RequestValidationError`，统一 `{error, code, message}`；生产不回显原始异常。

### 9. /health 不检查依赖
- **现象**：`/health` 恒返回 `{"status":"ok"}`，不探 DB/外部服务。
- **影响**：编排器（K8s/Docker）误判健康，实际已连不上库。
- **修复**：health 内做 DB `SELECT 1` 探活，失败时返回 503。

---

## 四、P2 — 可维护性

### 10. Alembic env.py 只 import 8/20 模型（详见前一轮）
- autogenerate 盲区，且可能生成 `DROP TABLE` 误删 12 张表。修复：`from app.models import *` + `__init__` 导出全部。

### 11. 后端零自动化测试
- `server/` 下无任何 `test_*.py`（仅 venv 自带）。对比 AI Collector 有 81 个 pytest。
- 修复：至少补 sync / prediction / auth 关键路径的集成测试 + CI 门禁。

### 12. get_db() 无条件 commit
- `database.py` 的 `get_db` 对 GET 请求也 `await session.commit()`，语义不清。
- 修复：读请求不提交，写请求显式提交；或按是否脏数据决定。

### 13. 长耗时 AI 生成跑在事件循环内
- `generate_predictions` 串 10+ LLM，无超时/并发上限/重试/断点；在调度与请求内直接 await。
- 修复：抽成后台任务（任务队列或独立 worker），加重试、超时、幂等。

### 14. 部分接口返回裸 dict、无 response_model
- 契约不稳定，前端难约束。修复：统一 `response_model=...`。

### 15. SSL 关闭证书校验
- `database.py` `ssl.CERT_NONE` + `check_hostname=False`。开发可接受（过代理），生产应校验。

### 16. DB 连接可能跨长 await 被钉死
- 若 service 在持有 `AsyncSession` 期间 `await` 外部 AI/HTTP 调用，连接会被占住，15 条连接池（pool_size5+overflow10）在并发下易耗尽。
- 建议：拿到 DB 数据后立即关闭 session，再做外部 AI 调用；或缩短事务边界。

---

## 五、整改优先级建议

| 优先级 | 项 | 工作量 | 阻断公网部署？ |
|--------|----|--------|----------------|
| P0 | #1 用户接口鉴权（Bearer + get_current_user） | 中 | 是 |
| P0 | #2 admin 路由鉴权 | 小 | 是 |
| P0 | #3 强制 SECRET_KEY | 小 | 是（补校验后） |
| P0 | #4 Highlightly key 移出源码 + 轮换 | 小 | 是 |
| P0 | #5 CORS 收敛 | 小 | 建议 |
| P1 | #6 调度器单点/分布式锁 | 中 | 多 worker 时 |
| P1 | #7 Redis 共享缓存 | 中 | 多 worker 时 |
| P1 | #8 全局异常 + 统一错误 | 小 | 否 |
| P1 | #9 依赖探活 health | 小 | 否 |
| P2 | #10~#16 | 各异 | 否 |

**一句话路线**：先把 P0 的鉴权与凭据问题堵上（这是"能不能上线"的门槛），再做 P1 的调度/缓存单点化以支持横向扩展，最后补测试与契约稳定性。
