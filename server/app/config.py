from __future__ import annotations

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
        return (
            f"mysql+asyncmy://{self.DB_USER}:{self.DB_PASSWORD}"
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
    OFOXAI_BASE_URL: str = "https://api.ofox.ai/v1"

    # DeepSeek 配置保留用于向后兼容，实际调用统一走 OfoxAI 网关
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = ""

    # Highlightly (替换 API-Football)
    HIGHLIGHTLY_API_KEY: str = ""
    HIGHLIGHTLY_BASE_URL: str = "https://soccer.highlightly.net"
    HIGHLIGHTLY_LEAGUE_ID: int = 1635   # World Cup
    HIGHLIGHTLY_SEASON: int = 2026

    # 微信小程序
    WECHAT_APP_ID: str = ""
    WECHAT_APP_SECRET: str = ""

    # JWT 认证
    SECRET_KEY: str = "world-cup-prediction-2026-secret-key-change-in-production"
    TOKEN_EXPIRE_HOURS: int = 720  # 30 天

    # 应用
    APP_NAME: str = "World Cup AI Prediction"
    DEBUG: bool = False

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
