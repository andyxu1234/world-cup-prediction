"""路由聚合"""

from fastapi import APIRouter

from app.api.v1.matches import router as matches_router
from app.api.v1.leagues import router as leagues_router
from app.api.v1.predictions import router as predictions_router
from app.api.v1.leaderboard import router as leaderboard_router
from app.api.v1.standings import router as standings_router
from app.api.v1.users import router as users_router
from app.api.v1.admin import router as admin_router
from app.api.v1.cn_mapping import router as cn_mapping_router

from app.api.v1.data import router as data_router
from app.api.v1.teams import router as teams_router
from app.api.v1.players import router as players_router
from app.api.v1.proxy import router as proxy_router
from app.api.v1.odds import router as odds_router
from app.api.v1.polymarket_standalone import router as polymarket_standalone_router

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(matches_router)
api_router.include_router(leagues_router)
api_router.include_router(predictions_router)
api_router.include_router(leaderboard_router)
api_router.include_router(standings_router)
api_router.include_router(users_router)
api_router.include_router(admin_router)
api_router.include_router(cn_mapping_router)

api_router.include_router(data_router)
api_router.include_router(teams_router)
api_router.include_router(players_router)
api_router.include_router(proxy_router)
api_router.include_router(odds_router)
api_router.include_router(polymarket_standalone_router)
