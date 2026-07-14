"""应用配置接口 — 提供前端可动态读取的开关与参数

目前用于「世界杯落幕引导页」：在前端冷启动时判断是否展示引导用户收藏小程序的提示页。
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/app-config", tags=["app-config"])


class WelcomeConfig(BaseModel):
    enabled: bool = True
    max_show_count: int = 5


class AppConfigOut(BaseModel):
    welcome: WelcomeConfig


@router.get("", response_model=AppConfigOut)
async def get_app_config():
    """返回应用级配置

    - welcome.enabled: 是否启用告别引导页
    - welcome.max_show_count: 每个用户最多展示次数（达到后不再弹）

    如需调整，直接修改下面常量即可，无需改库或发版。
    """
    return AppConfigOut(
        welcome=WelcomeConfig(
            enabled=True,
            max_show_count=5,
        )
    )
