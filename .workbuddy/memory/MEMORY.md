# MEMORY.md — 长期记忆

## 项目：world-cup-prediction（React/Taro 前端 + FastAPI 后端 + MySQL）
- 后端 `server/app/`，API 聚合 `server/app/api/router.py`(前缀 `/api/v1`)，各域 `server/app/api/v1/*`；FastAPI `StaticFiles` 挂 `static/`(`main.py`)。
- **私密赔率台**：`/internal/odds` 静态页 + `server/app/api/v1/odds.py` 只读接口，靠 `ODDS_VIEW_TOKEN`(默认 `odds-dev-local`)令牌闸，与小程序隔离。
- **公开 web 页现状（2026-07-23 实测纠正）**：`server/app/static/public/` 的公开 home 页**实际从未落库**，旧记"已新增 /home"是错的；如要做需新建 `static/public/` 并在 main.py 加 `/home` 挂载。当前 `static/` 只挂了私密赔率台。

## 数据库 / 迁移（踩坑）
- **库在远程阿里云 MySQL 47.101.167.103**（`.env` 的 `DATABASE_URL`），非本机。alembic 用 sync `DATABASE_URL_SYNC`(pymysql) 能连；sync pymysql 在 Windows 直连也正常。
- **Windows 本地跑 FastAPI 连远程 MySQL 的完整可用配方（2026-07-27 实测跑通，三处缺一不可）**：
  1. `config.py` 的 `DATABASE_URL`：Windows(`sys.platform=="win32"`)用 `mysql+aiomysql://`，其余(含 Docker/Linux 部署)用 `mysql+asyncmy://`。原因：`asyncmy` 在 Windows 连远程会 `WinError 87`；`aiomysql` 在 Windows 默认 `ProactorEventLoop` 下表现为 `2003 Can't connect`。
  2. `database.py` 的 `connect_args["ssl"]`：必须传 `ssl.SSLContext` 对象（自 `ssl.create_default_context()` 后 `check_hostname=False; verify_mode=CERT_NONE`），**不能传 dict** —— aiomysql 会把 dict 原样丢给 asyncio 触发 `'dict' object has no attribute 'wrap_bio'`。
  3. `main.py` 顶部：`if sys.platform=="win32": asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())`（必须在创建循环前设）。否则 aiomysql 在 `ProactorEventLoop` 下连不上（2003）。
  - 注：Linux/Docker 部署仍走 asyncmy，不受以上 Windows 分支影响；本机改完用 `uvicorn app.main:app --reload` 会自动重载生效。
- **删被外键复用的唯一索引报 1553**：先建独立索引支撑外键 → 再 drop/recreate 唯一索引 → 删临时索引。
- **MySQL DDL 非事务**：迁移写幂等（`SHOW COLUMNS`/`SHOW INDEX` 先判存在）。改 ORM 字段后必须 `alembic upgrade head`，否则 `Unknown column` 500。
- **venv 是 Python 3.9**：`config.py` 的 pydantic-settings 不能用 `list[dict]`/`dict[str,str]` 订阅注解（会 `TypeError: issubclass() arg 1 must be a class`），改用裸 `list`/`dict`。alembic 跑 `.venv\Scripts\alembic.exe upgrade head`。

## 赔率 / 预测
- 赔率模块：`bookmakers`+`match_odds` 表，按 `snapshot_date`(Date)+`snapshot_hour`(0-23)双字段追加快照；`odds_service.py` 由 scheduler `hour="*/6"` 每 6h 跑一次（即 00/06/12/18 点，`minute=0`），非仅 00:00。`generate_predictions` 每日 01:00，晚于 00:00 那次赔率同步（吃到当日快照）。`snapshot_hour` 做小时桶：同小时多次运行幂等、跨小时追加走势；因每6h跑一次，每日约 4 个赔率点（0/6/12/18 点）。注：`odds_service.py` 与 `admin.py` 的 docstring 仍写"每日 04:00"，已过时，实际是 */6。
- 博彩公司白名单 10 家：Pinnacle(4)+bet365(319)/Marathonbet(11)/1xBet(3)/Betwinner(10)/SBOBET(66)/Unibet(23)/William Hill(55)/Betway(17)/Bwin(9)；增删改 `bookmakers.is_active` 即可。
- 预测由 LangGraph(`prediction_graph.py`)编排；提示词 `prompt_builder.py`：`match_odds` 已接入(最新1X2均值+隐含概率+赔率移动趋势)、`match_time` 已加入、球队名保持英文 `.name`。`OfoxAIClient.predict_match` temp 默认 0.7(kimi-k3 强制 1.0)，`max_tokens=8192`。

## ⚠️ 安全
- `server/app/api/v1/admin.py` 全部路由**无鉴权**（可任意触发 odds 同步/VIP 增删）。公网部署前必加令牌/鉴权，用户已知悉。

## 🚨 合规风险：微信小程序 6.1.5（2026-07-22 通知）
- 命中点：`bets`+`wallets`+VIP(赌博)、`vote-history`(竞猜)、`match_odds`+`bookmakers`(外围)、10 个 AI 模型预测(彩票预测服务)。
- 核心判准：只要前端有"用户投入→押结果→获回报"闭环即违规，与叫"分析"还是"竞猜"无关。
- **「改 web 就脱离腾讯」是误区**：被封的是"内容形态违规+微信生态传播"组合；web 端最自然仍从微信入口来，会触发域名黑名单+主体连坐。**web 化必须以内容合规为前提**。
- 整改：短期下架参与功能+敏感词替换+只读 AI 展示+免责声明；中期挪到"AI 体育数据"赛道。
- **敏感词禁用**：投注/下注/押注/买注/买球/庄家/盘口/必发/Pinnacle/博彩公司/赔率/让球/大小球/单关/串关/竞猜/押胜负/猜比分/猜冠军/中奖/兑奖/彩金/红包/提现/比分预测/比赛预测/结果预测 → 替换为 分析/解读/观点/数据参考/概率分布/模型输出/专家洞察。
- `match_odds` 表可保留(学术合法)，但前端不展示赔率数字和博彩公司 logo。

## 前端 Taro 4 配置（踩坑，2026-07-31 实测）
- **`client/config/index.ts` 之前整个缺失**，导致 `npm run dev:h5` 编译失败、所有 chunk 404 兜底成 HTML（浏览器报 `Unexpected token '<'` 白屏）。补回 Taro 4.1 模板最小配置即可。
- **Taro 4 不会自动读 tsconfig 的 `paths` 做 webpack alias**：须显式在 `config/index.ts` 顶层加 `alias: { '@': path.resolve(process.cwd(), 'src') }`，否则全站 `@/stores`/`@/services/api`/`@/utils/*`/`@/assets/*` 全部 `Can't resolve`。
- **全局 SCSS 变量不自动注入**：各页面 scss 用了 `variables.scss` 的 `$bg-primary`/`$green` 等但没 `@use` 它，必须配 `sass: { resource: ['src/styles/variables.scss'] }`，否则报错 `Undefined variable`。
- 注意：`global.scss` 自己已有 `@use "./variables" as *`；`sass.resource` 用 `@import` 注入同一文件不会与之冲突（实测可过）。
- dev server 端口写死 `h5.devServer.port: 10086`（`dev:h5` 脚本），本机访问 `http://<lan-ip>:10086/`。
- **LeaguePicker 弹窗撑不开（2026-07-31 实测，修复 #2 10:00）**：`client/src/components/LeaguePicker/` 弹窗在 8 个联赛场景下只显示 5 个就被裁。原因不是首次异步问题，是双层裁切：① `.league-modal` `max-height:480` + `overflow:hidden`；② ScrollView `style.height` 上限 420 + 底部 ft ≈70 = 490 > 480 整体被裁。修法：`index.scss` max-height 480→600；`index.tsx` ScrollView `style.height` 上限 420→460（8×56+10=458 直接展开不滚）；**移除** `enhanced` 属性（Taro 4 H5 专属 better-scroll prop，微信原生 scroll-view 不识别）；保留 `key={pickerKey}` + `useEffect([pickerOpen, leagues.length])` 自增 key 重建。详见当日 memory。
- **LeaguePicker 弹窗首次不能滚动（2026-07-31 早期误判，已纠正）**：之前误以为 `Math.min(...,420)` 缺保底导致异步场景下高度=0，实际修 #2 后**首次弹窗不能滚动**的根因是 `max-height:480` 裁掉了 ScrollView 底部 + ft 上沿；`enhanced` 之前被误归为"必须"修复，实测只对 H5 有意义，微信端不识别。修 #2 后 `Math.max(..., 240)` 保底可保留也可删（异步场景已由 `pickerKey` 重建机制兜底）。

## 用户协作偏好
- 中文、简洁直接；先方案→快决策→执行。
- **UI 硬偏好**：① 折叠/收起等交互必须是**明显可见按钮**，不要隐式"点文字链接收起"；② 列表/表格/正文**默认左对齐**；③ 容器过宽必须**横向滚动条**，不可裁切/挤压。
- **cache-busting 约定（2026-07-23 定）**：固定原地改 `odds.v15.js`/`odds.v15.css`，HTML 引用停在 v15 不动，用户自己 Ctrl+Shift+R 强刷（不再复制 v16+）。

## Polymarket 接入（只读，不涉交易）
- 表 `polymarket_events`(按"主 vs 客"分组,`match_id` FK 关联本地 matches,未匹配 NULL)+`polymarket_markets`(各腿 home/draw/away 的 price/volume/liquidity + clob_token_id_yes/no + position_id_yes/no)。
- 客户端 `core/polymarket.py`(httpx 异步版,`proxy=_resolve_proxy()` 优先 `POLYMARKET_PROXY` 否则 HTTPS_PROXY)；同步 `services/polymarket_sync.py`(每日 00:30 upsert 两表,只存未来 7 天 money-line 3-way)；`scheduler`+`admin POST /admin/polymarket/sync`。**直连 gamma-api.polymarket.com 国内被墙(ETIMEDOUT)，必须走本机代理(如 127.0.0.1:10808)**。
- `fetch_upcoming_money_line` 比赛时间用 `markets[].gameStartTime`(勿用 startDate=上架时间)；`closed=false` 会滤空已收盘赛事(世界杯已结束),去掉该参数才返回数据。
- **时区**：Highlightly `match_time`=北京时间(UTC+8,naive)；Polymarket `game_start_time`=UTC(naive)。匹配前归一(北京−8h 或 UTC+8h)，绝不直接比两套时区。
- **匹配方案(16:04 敲定)**：整件事交 DeepSeek。`polymarket_match.py::match_polymarket_events()` 按联赛+时间窗(±3天)捞候选 matches→队名映射→prompt 喂 DeepSeek→校验 `match_id∈候选集`(防幻觉)→UPDATE；null/越界留 NULL。候选查 `config.POLYMARKET_SERIES_LEAGUE`(series_id→highlightly_league_id 静态映射,运行时按 season=2026 解析 leagues.id)。已串联进 sync 末尾 + `admin POST /admin/polymarket/match`。DeepSeek 实时调用需用户本机网络+密钥自测。

## 去微信化 / 独立 APK·Web 迁移（2026-07-26 启动）
- 目标：离开微信小程序生态，做成独立 APK（apk-shell WebView 壳）与网页版；登录/头像昵称/VIP 不再依赖微信。
- 代码现状（已查 2026-07-26）：
  - 后端 `/users/login` 仅用 `wx.login` code→openid 找/建 `User` 并发 JWT；JWT 已只装 `user.id`，其余接口(vote/profile/vip)全靠 user_id，与微信无关。
  - **VIP 判定 `get_vip_status(user_id)` 已与 openid 解耦**；但 `vip_service.add_vip(openid,...)` 仍按 openid 查用户，`VipMember.openid` 为 NOT NULL → 给非微信用户开 VIP 会失败。
  - `User.openid` 为 NOT NULL+unique → 非微信用户无法建号（必须改 nullable）。
  - 前端仅 `client/src/pages/profile/index.tsx` 的 `handleReLogin` 调 `Taro.login()`(wx.login)→`wxLogin`；其余全走 token+user_id。
- 推荐方向（待用户拍板细节）：保留微信登录后端接口做兼容，新增 手机号+短信验证码 / 手机号或邮箱+密码 登录；User 表加 phone/email/password_hash/auth_provider，openid 改 nullable；VipMember.openid 改 nullable，add_vip 支持按 user_id。前端登录页改 phone/code 或 account/password。
- 合规：离微信后内容监管仍在（国内应用商店/付费预测）。VIP 定位"会员增值(去广告/高级数据)"，不展示赔率/博彩 logo/敏感词（沿用 6.1.5 整改结论）。短信网关需企业实名，开发期可 dev 模式返回验证码先跑通。
- **功能恢复（2026-07-26 17:00）**：独立 APK/Web 前提下，应要求加回两项合规安全区功能——① 人机对决排行榜（leaderboard 的 human tab + UserAvatar，整文件从 HEAD 还原）；② AI 预测公开展示 + 原"预测"措辞（match-detail/ai-detail 逐处还原 主胜/客胜/平局、AI 预测对战卡/AI 预测世界杯、AI 预测尚未生成、预测失误 等；vote-history 整页还原；features.ts VOTE 改 true；app.config 加回路由+标题「AI 预测世界杯」）。**边界**：原版带「投注」的免责/提示句未恢复（投注/下注仍在敏感词禁用清单），页脚沿用现行合规免责。真·下注闭环、付费卖"保证命中"仍不恢复。

## APK 图标（2026-07-26，17:36 落地 → 21:00 升级为 adaptive icon）
- 图标源：`client/src/assets/logo.jpg`（1408×768 RGB 宽屏，青绿圆徽标「AI世界杯/预测中」居中、两侧白留白）。脚本自动采样中央 200×200 平均色作为背景色（本次 `#64ACAA`），保证图标整体色调一致。
- 工程现状：`apk-shell/app/src/main/AndroidManifest.xml` 引用 `@mipmap/ic_launcher`（API 26+ 走 `mipmap-anydpi-v26/ic_launcher.xml` adaptive；API < 26 走传统 mipmap PNG）。无 drawable 占位依赖。
- 落地（adaptive icon + 传统兜底，最稳）：
  1. Pillow 裁中央正方形（`min(w,h)`=768）→ 白/近白像素（R/G/B≥240）转透明 → LANCZOS 缩放到 432×432 → `drawable-nodpi/ic_launcher_foreground.png`（adaptive 前景）。
  2. 5 个传统密度 `mipmap-{mdpi,hdpi,xhdpi,xxhdpi,xxxhdpi}/ic_launcher.png`（48~192px）：**不透明青绿底 + logo fit 居中**，彻底避免 launcher 把透明当白填。
  3. `values/colors.xml` 加 `<color name="ic_launcher_background">#采样色</color>`；`drawable/ic_launcher_background.xml` 是引用该 color 的 shape rectangle；`mipmap-anydpi-v26/ic_launcher.xml` + `ic_launcher_round.xml` 是 adaptive-icon spec。
  4. 重新 `gradle assembleDebug`（Android Studio 也行）。
- **白边根因**（21:00 发现）：透明 PNG 在部分 launcher（应用抽屉/设置预览等不套圆遮罩位）会把透明区填成白色方框。根治必须用 adaptive icon 或给传统 PNG 加不透明背景，单靠透明 PNG 无解。
- **圆内白字误删修复（21:13）**：初版用全局 R/G/B≥240 白→透明，误把圆内白色文字也抠掉了（用户要求圆内一切内容原样保留）。改用**按行的圆形弦遮罩**：每行扫描找圆的左右非白边界，只保留该弦范围内像素，圆外才置透明；圆内白字/足球/电路纹理全部原样保留。脚本 `make_icons_v3.py`（已取代 v2）。`masked`=圆外透明版，用于 `drawable-nodpi/ic_launcher_foreground.png`(432×432) 与 mipmap 兜底（alpha_composite 到青绿底，去白环）。
- 备注：占位 `drawable/ic_launcher.xml` 保留无害（不再被引用）；想彻底清理可手动删。
