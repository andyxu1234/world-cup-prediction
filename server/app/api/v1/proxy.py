"""图片代理 — 绕过 cdn.sofifa.net 的 Cloudflare 防盗链/UA 拦截

小程序 <image> 直连 cdn.sofifa.net 会被 403（缺 Referer / 非浏览器 UA），
但 highlightly 等其它外链正常。故仅对 sofifa 域名做服务端代理：
后端带浏览器 UA + Referer 拉取，缓存到本地后原样吐给小程序，
小程序侧只连已加白的 API 域名。
"""

from __future__ import annotations

import hashlib
import os
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, HTTPException, Query, Response
from fastapi.responses import FileResponse

router = APIRouter(prefix="/proxy", tags=["proxy"])

# 仅允许代理 sofifa 域名，避免被当作通用 SSRF 代理
ALLOWED_HOSTS = {"cdn.sofifa.net", "sofifa.net"}

# 缓存目录: server/static/proxy_cache
_CACHE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
    "static",
    "proxy_cache",
)

_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


@router.get("/avatar")
async def proxy_avatar(u: str = Query(..., description="原始图片 URL")):
    parsed = urlparse(u)
    if parsed.scheme not in ("http", "https") or parsed.hostname not in ALLOWED_HOSTS:
        raise HTTPException(status_code=400, detail="unsupported image host")

    os.makedirs(_CACHE_DIR, exist_ok=True)
    key = hashlib.md5(u.encode("utf-8")).hexdigest()
    ext = os.path.splitext(parsed.path)[1] or ".png"
    cache_path = os.path.join(_CACHE_DIR, key + ext)

    if os.path.exists(cache_path):
        return FileResponse(cache_path)

    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        try:
            r = await client.get(
                u,
                headers={
                    "User-Agent": _BROWSER_UA,
                    "Referer": "https://cdn.sofifa.net/",
                    "Accept": "image/avif,image/webp,image/png,image/*,*/*;q=0.8",
                },
            )
        except httpx.HTTPError as e:
            raise HTTPException(status_code=502, detail=f"upstream request failed: {e}")

        if r.status_code != 200:
            raise HTTPException(status_code=r.status_code, detail="upstream error")

        content_type = r.headers.get("content-type") or "image/png"
        with open(cache_path, "wb") as f:
            f.write(r.content)
        return Response(
            content=r.content,
            media_type=content_type,
            headers={"Cache-Control": "public, max-age=86400"},
        )
