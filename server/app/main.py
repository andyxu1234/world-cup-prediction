"""FastAPI 应用入口"""

from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from loguru import logger

from app.config import get_settings, Settings
from app.core.scheduler import start_scheduler, stop_scheduler
from app.api.router import api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期"""
    settings = get_settings()
    logger.info(f"Starting {settings.APP_NAME}...")

    # 确保头像存储目录存在
    settings.AVATAR_SAVE_PATH.mkdir(parents=True, exist_ok=True)

    start_scheduler()
    yield
    logger.info("Shutting down...")
    stop_scheduler()


settings = get_settings()

# 确保头像存储目录在 mount 前就存在（mount 在模块加载时执行，早于 lifespan）
settings.AVATAR_SAVE_PATH.mkdir(parents=True, exist_ok=True)

app = FastAPI(
    title="World Cup AI Prediction API",
    description="世界杯 AI 预测大赛后端 API",
    version="1.0.0",
    lifespan=lifespan,
)

# 注册路由
app.include_router(api_router)

# CORS 跨域配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载头像静态文件目录
app.mount("/static/avatars", StaticFiles(directory=str(settings.AVATAR_SAVE_PATH)), name="avatars")


@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "ok"}
