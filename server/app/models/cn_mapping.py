from __future__ import annotations

from sqlalchemy import String, Integer, Boolean, DateTime, func, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CnMapping(Base):
    """通用中英文映射表（原 round_translations 扩展而来）。

    通过 category 区分不同翻译场景，例如：
    - 'round'    : 轮次，如 Group Stage / Regular Season / Final
    - 'position' : 球员位置，如 Goalkeeper / Defender / Forward

    - category：映射类别（目录）
    - key       ：原始英文 key（如 Group Stage / Forward）
    - cn_value  ：中文值，round 场景支持 {n} 占位符（如「小组赛第{n}轮」）
    - is_series ：仅 round 场景使用，是否为带数字后缀的系列轮次（如 Group Stage - 3）
    """

    __tablename__ = "cn_mapping"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category: Mapped[str] = mapped_column(String(32), nullable=False, default="round")
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    cn_value: Mapped[str] = mapped_column(String(128), nullable=False)
    is_series: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[str] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[str] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        # 同一类别下 key 唯一
        UniqueConstraint("category", "key", name="uk_cn_mapping_category_key"),
    )
