from __future__ import annotations

import sys
from pathlib import Path
from pydantic_settings import BaseSettings
from functools import lru_cache

# .env 文件绝对路径，确保不受工作目录影响
_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    # 数据库
    DB_PASSWORD: str = ""
    DB_HOST: str = "127.0.0.1"
    DB_PORT: int = 3306
    DB_NAME: str = "worldcup_prediction"
    DB_USER: str = "root"

    @property
    def DATABASE_URL(self) -> str:
        # Windows 下 asyncmy 连远程 MySQL 会报 WinError 87，开发环境改用 aiomysql；
        # Linux/Docker 部署仍走 asyncmy（性能更好且跨平台无此问题）。
        driver = "mysql+aiomysql" if sys.platform == "win32" else "mysql+asyncmy"
        return (
            f"{driver}://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    @property
    def DATABASE_URL_SYNC(self) -> str:
        """Alembic 迁移用的同步连接"""
        return (
            f"mysql+pymysql://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    # OfoxAI 统一 AI 网关
    OFOXAI_API_KEY: str = ""
    OFOXAI_BASE_URL: str = "https://api.ofox.io/v1"

    # DeepSeek 配置保留用于向后兼容，实际调用统一走 OfoxAI 网关
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = ""

    # Highlightly (替换 API-Football)
    HIGHLIGHTLY_API_KEY: str = "bdc14b1e-4982-4bd4-8ec0-aeb38ce0b634"
    # RapidAPI 代理主机；路径需带 /football 前缀
    HIGHLIGHTLY_BASE_URL: str = "https://soccer.highlightly.net"
    # Highlightly 默认联赛 / 赛季
    # 多联赛模式下改由 leagues 表驱动；这两个值仅作为未指定联赛时的回退默认值，不再强制使用
    HIGHLIGHTLY_LEAGUE_ID: int = 1635   # World Cup (default/fallback)
    HIGHLIGHTLY_SEASON: int = 2026

    # ── Polymarket 赛事抓取（只读）──
    # 只拉五大联赛 + 欧冠 + 欧联，未来 POLYMARKET_DAYS_AHEAD 天内的比赛，
    # 且只取"胜负平"（moneyline 3-way）市场，落 polymarket_events / polymarket_markets 表。
    # 每个元素 {"id": Polymarket series_id, "name": 展示名}。
    # 注意：本 venv 为 Python 3.9，pydantic-settings 不支持订阅式注解
    # （list[dict] 在 field_is_complex 里会触发 issubclass() 异常），
    # 故此处用裸 list / dict 注解，内层类型在使用处自行解析。
    POLYMARKET_SERIES: list = [
        {"id": "10188", "name": "English Premier League"},
        {"id": "10193", "name": "La Liga"},
        {"id": "10194", "name": "Bundesliga"},
        {"id": "10203", "name": "Serie A"},
        {"id": "10195", "name": "Ligue 1"},
        {"id": "10204", "name": "UEFA Champions League"},
        {"id": "10209", "name": "UEFA Europa League"},
    ]
    # 只保留未来 N 天内开赛的比赛（按 Polymarket gameStartTime/UTC 过滤）
    POLYMARKET_DAYS_AHEAD: int = 7
    # 单 series 最多翻页数（防御性上限）：Polymarket 某联赛 open 事件可能极多，
    # 若服务端 endDate 过滤失效可防止无限翻页；正常工作时远不会触发。
    POLYMARKET_MAX_PAGES: int = 50
    # 队名别名：Polymarket 队名(小写) -> 本地 teams.name(小写)。
    # 仅覆盖确有可能不一致的少数情况；其余靠大小写不敏感精确匹配。
    # 若某赛事未匹配到本地比赛（match_id 为 NULL），多半是此处需补别名。
    # 裸 dict 注解（Py3.9 兼容，见 POLYMARKET_SERIES 说明）。
    POLYMARKET_TEAM_ALIASES: dict = {
        "usa": "united states",
        "united states": "united states",
        "korea republic": "south korea",
        "holland": "netherlands",
        "czech republic": "czechia",
    }
    # 匹配时开赛时间容差（小时）；Polymarket endDate 与本地 match_time 均按 UTC 比较。
    POLYMARKET_MATCH_WINDOW_HOURS: int = 24
    # 静态映射：Polymarket series_id -> Highlightly highlightly_league_id。
    # 匹配时据此把 Polymarket 联赛锁定到本地 leagues 行（按 season=2026 取活跃行）。
    # 值来自 leagues 表查询（2026 赛季）：
    #   Premier League=33973, La Liga=119924, Bundesliga=67162, Serie A=115669,
    #   Ligue 1=52695, UEFA Champions League=2486, UEFA Europa League=3337。
    # 裸 dict 注解（Py3.9 兼容，见 POLYMARKET_SERIES 说明）。
    POLYMARKET_SERIES_LEAGUE: dict = {
        "10188": 33973,   # English Premier League
        "10193": 119924,  # La Liga
        "10194": 67162,   # Bundesliga
        "10203": 115669,  # Serie A
        "10195": 52695,   # Ligue 1
        "10204": 2486,    # UEFA Champions League
        "10209": 3337,    # UEFA Europa League
    }

    # Polymarket 抓取的 outbound 代理（可选）。
    # 国内网络直连 gamma-api.polymarket.com 会被墙/地域封锁；
    # 设为 http 代理（如 "http://127.0.0.1:10808"）即可走代理拉取。
    # 留空时按 HTTPS_PROXY -> HTTP_PROXY 顺序读取环境变量。
    # 建议写进 .env（而非 export 到全局 shell），避免污染 OfoxAI / Highlightly
    # 等其他 httpx 客户端的出站流量。
    POLYMARKET_PROXY: str = "http://127.0.0.1:10808"

    # ── Polymarket Standalone 市场配置 ──
    # NO farming 最高入场价格（0-1），低于此价格的 NO 市场被认为符合条件
    POLYMARKET_MAX_ENTRY_PRICE: float = 0.65
    # 只保留未来 N 个月内结束的市场
    POLYMARKET_MAX_END_DATE_MONTHS: int = 3

    # 微信小程序
    WECHAT_APP_ID: str = ""
    WECHAT_APP_SECRET: str = ""

    # JWT 认证
    SECRET_KEY: str = "world-cup-prediction-2026-secret-key-change-in-production"
    TOKEN_EXPIRE_HOURS: int = 720  # 30 天

    # 应用
    APP_NAME: str = "World Cup AI Prediction"
    DEBUG: bool = False

    # 私密赔率展示页（/internal/odds）共享访问令牌
    # 本地默认开发令牌；公网部署前务必改为强随机值，并配合 IP 白名单
    ODDS_VIEW_TOKEN: str = "odds-dev-local"

    # Telegram Bot 配置
    TELEGRAM_BOT_TOKEN: str = ""  # Telegram Bot Token（从 @BotFather 获取）
    TELEGRAM_CHAT_IDS: str = ""  # 监控类 Chat ID（如管理员私聊），多个用逗号分隔；公共频道请改用下方专用字段
    # 公共频道（公开引流频道）：自动化发帖的专门目标。
    # 默认填你提供的频道 ID；如需更换，在 .env 覆盖 TELEGRAM_PUBLIC_CHANNEL_ID 即可。
    # 注意：该 bot 必须被添加为该频道的管理员（具备发消息权限），否则发送会报 403。
    TELEGRAM_PUBLIC_CHANNEL_ID: str = "@aifootball123"

    # 头像存储（微信临时 URL 需要下载转存）
    AVATAR_DIR: str = "avatars"  # 相对于项目根目录的子目录
    AVATAR_BASE_URL: str = ""    # 前端访问头像的完整基础路径，如 https://marathoninfo.top/static/avatars/

    @property
    def AVATAR_SAVE_PATH(self) -> Path:
        """头像存储的绝对路径"""
        return Path(__file__).resolve().parent.parent / self.AVATAR_DIR

    @property
    def AVATAR_PUBLIC_URL(self) -> str:
        """前端访问头像的完整基础路径，优先用 AVATAR_BASE_URL 环境变量，否则自动拼接"""
        if self.AVATAR_BASE_URL:
            return self.AVATAR_BASE_URL
        # 默认根据 DEBUG 自动拼接
        return f"/static/{self.AVATAR_DIR}/"

    model_config = {"env_file": str(_ENV_FILE), "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
