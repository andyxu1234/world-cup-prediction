from __future__ import annotations

from sqlalchemy import String, Integer, DateTime, ForeignKey, func, Enum
from sqlalchemy.orm import Mapped, mapped_column
from typing import Optional
from app.database import Base


class VipMember(Base):
    __tablename__ = "vip_members"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    openid: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    plan_type: Mapped[str] = mapped_column(
        Enum("monthly", "quarterly", "yearly", "permanent", name="plan_type"),
        nullable=False
    )
    start_at: Mapped[str] = mapped_column(DateTime, nullable=False)
    expire_at: Mapped[Optional[str]] = mapped_column(DateTime, nullable=True)  # 永久会员为 NULL
    remark: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    created_at: Mapped[str] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[str] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
