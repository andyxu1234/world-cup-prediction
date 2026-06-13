"""VIP 会员服务"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional, List
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.models.vip_member import VipMember
from app.models.user import User


# 套餐时长配置（天数）
PLAN_DURATION = {
    "monthly": 30,
    "quarterly": 90,
    "yearly": 365,
    "permanent": None,  # 永久会员
}

# 套餐标签
PLAN_LABEL = {
    "monthly": "月卡",
    "quarterly": "季卡",
    "yearly": "年卡",
    "permanent": "永久卡",
}


async def get_vip_status(db: AsyncSession, user_id: int) -> dict:
    """获取用户 VIP 状态"""
    try:
        result = await db.execute(
            select(VipMember).where(VipMember.user_id == user_id)
        )
        member = result.scalar_one_or_none()

        if not member:
            return {
                "is_vip": False,
                "plan_type": None,
                "expire_at": None,
                "days_remaining": 0,
            }

        # 检查是否过期
        if member.plan_type == "permanent":
            is_vip = True
            days_remaining = -1  # 永久会员
        else:
            expire_at = member.expire_at
            if expire_at:
                is_vip = datetime.now() < expire_at
                days_remaining = max(0, (expire_at - datetime.now()).days)
            else:
                is_vip = False
                days_remaining = 0

        return {
            "is_vip": is_vip,
            "plan_type": member.plan_type,
            "expire_at": member.expire_at.isoformat() if member.expire_at else None,
            "days_remaining": days_remaining,
        }
    except Exception as e:
        logger.error(f"获取 VIP 状态失败: {e}")
        return {
            "is_vip": False,
            "plan_type": None,
            "expire_at": None,
            "days_remaining": 0,
        }


async def add_vip(
    db: AsyncSession,
    openid: str,
    plan_type: str,
    remark: Optional[str] = None
) -> dict:
    """添加 VIP 会员（已存在则续费/升级）"""
    try:
        # 查找用户
        user_result = await db.execute(
            select(User).where(User.openid == openid)
        )
        user = user_result.scalar_one_or_none()

        if not user:
            raise ValueError(f"用户不存在: {openid}")

        # 检查是否已经是会员
        existing_result = await db.execute(
            select(VipMember).where(VipMember.user_id == user.id)
        )
        existing = existing_result.scalar_one_or_none()

        if existing:
            # 已经是会员，执行续费/升级逻辑
            return await _renew_or_upgrade(db, existing, plan_type, remark)

        # 新用户，创建会员记录
        start_at = datetime.now()
        if plan_type == "permanent":
            expire_at = None
        else:
            duration = PLAN_DURATION.get(plan_type)
            if not duration:
                raise ValueError(f"无效的套餐类型: {plan_type}")
            expire_at = start_at + timedelta(days=duration)

        member = VipMember(
            user_id=user.id,
            openid=openid,
            plan_type=plan_type,
            start_at=start_at,
            expire_at=expire_at,
            remark=remark,
        )
        db.add(member)
        await db.commit()

        logger.info(f"添加 VIP 会员成功: {openid}, 套餐: {plan_type}")
        return {
            "success": True,
            "message": "添加成功",
            "member_id": member.id,
        }
    except Exception as e:
        await db.rollback()
        logger.error(f"添加 VIP 会员失败: {e}")
        raise


async def _renew_or_upgrade(
    db: AsyncSession,
    member: VipMember,
    new_plan_type: str,
    remark: Optional[str] = None
) -> dict:
    """续费、升级或降级 VIP 会员"""
    now = datetime.now()

    # 当前是永久会员，不允许再添加非永久套餐
    if member.plan_type == "permanent":
        if new_plan_type == "permanent":
            return {"success": True, "message": "用户已是永久会员，无需操作"}
        raise ValueError("已经是永久会员")

    # 新套餐是永久卡，直接升级
    if new_plan_type == "permanent":
        member.plan_type = "permanent"
        member.expire_at = None
        if remark:
            member.remark = remark
        await db.commit()
        logger.info(f"升级为永久会员: {member.user_id}")
        return {"success": True, "message": "已升级为永久会员"}

    # 计算新的过期时间
    duration = PLAN_DURATION.get(new_plan_type)
    if not duration:
        raise ValueError(f"无效的套餐类型: {new_plan_type}")

    # 如果当前会员未过期，在原过期时间基础上续费
    if member.expire_at and member.expire_at > now:
        member.expire_at = member.expire_at + timedelta(days=duration)
    else:
        # 已过期，从现在开始计算
        member.expire_at = now + timedelta(days=duration)

    member.plan_type = new_plan_type
    if remark:
        member.remark = remark

    await db.commit()

    logger.info(f"续费 VIP 会员成功: {member.user_id}, 新套餐: {new_plan_type}")
    return {
        "success": True,
        "message": f"续费成功，新到期时间: {member.expire_at.strftime('%Y-%m-%d')}",
    }


async def renew_vip(
    db: AsyncSession,
    user_id: int,
    plan_type: str
) -> dict:
    """续费 VIP 会员"""
    try:
        result = await db.execute(
            select(VipMember).where(VipMember.user_id == user_id)
        )
        member = result.scalar_one_or_none()

        if not member:
            raise ValueError(f"用户不是 VIP 会员")

        # 计算新的过期时间
        if plan_type == "permanent":
            member.plan_type = "permanent"
            member.expire_at = None
        else:
            duration = PLAN_DURATION.get(plan_type)
            if not duration:
                raise ValueError(f"无效的套餐类型: {plan_type}")

            # 如果是永久会员，不允许续费
            if member.plan_type == "permanent":
                raise ValueError(f"永久会员无需续费")

            # 从当前过期时间开始续费，如果已过期则从现在开始
            now = datetime.now()
            if member.expire_at and member.expire_at > now:
                member.expire_at = member.expire_at + timedelta(days=duration)
            else:
                member.expire_at = now + timedelta(days=duration)

            member.plan_type = plan_type

        await db.commit()

        logger.info(f"续费 VIP 会员成功: {user_id}, 套餐: {plan_type}")
        return {
            "success": True,
            "message": "续费成功",
        }
    except Exception as e:
        await db.rollback()
        logger.error(f"续费 VIP 会员失败: {e}")
        raise


async def delete_vip(db: AsyncSession, member_id: int) -> dict:
    """删除 VIP 会员"""
    try:
        result = await db.execute(
            select(VipMember).where(VipMember.id == member_id)
        )
        member = result.scalar_one_or_none()

        if not member:
            raise ValueError(f"会员不存在")

        await db.delete(member)
        await db.commit()

        logger.info(f"删除 VIP 会员成功: {member_id}")
        return {
            "success": True,
            "message": "删除成功",
        }
    except Exception as e:
        await db.rollback()
        logger.error(f"删除 VIP 会员失败: {e}")
        raise


async def get_vip_list(db: AsyncSession) -> List[dict]:
    """获取所有 VIP 会员列表（包含用户昵称和头像）"""
    try:
        # 联表查询，获取用户信息
        stmt = (
            select(VipMember, User.nickname, User.avatar_url)
            .join(User, VipMember.user_id == User.id)
            .order_by(VipMember.created_at.desc())
        )
        result = await db.execute(stmt)
        rows = result.all()

        return [
            {
                "id": m.id,
                "user_id": m.user_id,
                "openid": m.openid,
                "nickname": nickname,
                "avatar_url": avatar_url,
                "plan_type": m.plan_type,
                "start_at": m.start_at.isoformat() if m.start_at else None,
                "expire_at": m.expire_at.isoformat() if m.expire_at else None,
                "remark": m.remark,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m, nickname, avatar_url in rows
        ]
    except Exception as e:
        logger.error(f"获取 VIP 列表失败: {e}")
        return []


async def get_vip_stats(db: AsyncSession) -> dict:
    """获取 VIP 统计信息"""
    try:
        # 总数
        total_result = await db.execute(select(func.count(VipMember.id)))
        total = total_result.scalar() or 0

        # 按套餐类型统计
        stats = {}
        for plan_type in ["monthly", "quarterly", "yearly", "permanent"]:
            result = await db.execute(
                select(func.count(VipMember.id)).where(
                    VipMember.plan_type == plan_type
                )
            )
            stats[plan_type] = result.scalar() or 0

        return {
            "total": total,
            "monthly": stats["monthly"],
            "quarterly": stats["quarterly"],
            "yearly": stats["yearly"],
            "permanent": stats["permanent"],
        }
    except Exception as e:
        logger.error(f"获取 VIP 统计失败: {e}")
        return {
            "total": 0,
            "monthly": 0,
            "quarterly": 0,
            "yearly": 0,
            "permanent": 0,
        }
