"""路由聚合"""

from fastapi import APIRouter

from app.api.v1.matches import router as matches_router
from app.api.v1.predictions import router as predictions_router
from app.api.v1.leaderboard import router as leaderboard_router
from app.api.v1.users import router as users_router
from app.api.v1.admin import router as admin_router
from app.api.v1.long_term import router as long_term_router
from app.api.v1.fun_fact import router as fun_fact_router

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(matches_router)
api_router.include_router(predictions_router)
api_router.include_router(leaderboard_router)
api_router.include_router(users_router)
api_router.include_router(admin_router)
api_router.include_router(long_term_router)
api_router.include_router(fun_fact_router)
