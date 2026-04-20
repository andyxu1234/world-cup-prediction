from __future__ import annotations

from sqlalchemy import String, Integer, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    openid: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    nickname: Mapped[Optional[str]] = mapped_column(String(100))
    avatar_url: Mapped[Optional[str]] = mapped_column(String(500))
    created_at: Mapped[str] = mapped_column(DateTime, server_default=func.now())

    # relationships
    votes: Mapped[list["UserVote"]] = relationship("UserVote", back_populates="user")
