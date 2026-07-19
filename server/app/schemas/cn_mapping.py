"""通用中英文映射 Schema"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class CnMappingOut(BaseModel):
    """通用映射输出"""

    id: int
    category: str
    key: str
    cn_value: str
    is_series: bool

    model_config = {"from_attributes": True}
