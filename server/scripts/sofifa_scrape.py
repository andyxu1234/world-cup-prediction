"""
从 sofifa.com 抓取全量球员 URL, 解析出 (sofifa_id, name_slug, name) 写入 CSV。

点击次数(实测结论):
    sofifa 的 Cloudflare 在每次 page.goto 翻页时都会重新弹 Turnstile 验证,
    cf_clearance cookie 不会在翻页之间复用, 因此"逐页 goto"方案必须每页点一次。

    本脚本改用: 第一页用 goto 通过一次验证(你点 1 次), 之后所有页都用
    页面内的 fetch() 请求同一站点。fetch 在已验证的同源页面里发出, 自动携带
    cf_clearance cookie, Cloudflare 不再弹验证。因此整轮(200 页)只需点 1 次。

    - cookie 还有效时第一页也不弹验证 -> 0 次点击;
    - cookie 失效时第一页弹验证 -> 你点 1 次, 之后全自动。

用法(从仓库根目录执行):
    python server/scripts/sofifa_scrape.py --max-pages 200
    python server/scripts/sofifa_scrape.py --max-pages 0          # 全量
    python server/scripts/sofifa_scrape.py --no-resume            # 从头开始
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import re
import time

from playwright.async_api import async_playwright

URL_RE = re.compile(r"/player/(\d+)/([^/]+)/")
PLAYER_LINK_RE = re.compile(r"/player/\d+/")
PAGE_SIZE = 60

PROFILE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".sofifa_profile")
STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".sofifa_state.json")

# 在已验证的同源页面内发起 fetch, 解析球员链接。不触发重新导航, 故不重新弹验证。
FETCH_JS = r"""
async (url) => {
    try {
        const resp = await fetch(url, {
            method: 'GET',
            credentials: 'include',
            headers: {
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
            },
        });
        const status = resp.status;
        if (status !== 200) {
            return { status, urls: [] };
        }
        const html = await resp.text();
        const doc = new DOMParser().parseFromString(html, 'text/html');
        const urls = [];
        doc.querySelectorAll('a[href*="/player/"]').forEach(l => {
            const h = l.href;
            if (h.includes('/player/') && !h.includes('random')) urls.push(h);
        });
        return { status: 200, urls };
    } catch (e) {
        return { status: -1, urls: [], error: String(e) };
    }
}
"""

# 在已加载的页面 DOM 上直接读取球员链接(用于第一页 goto 之后)。
READ_DOM_JS = r"""
() => {
    const urls = [];
    document.querySelectorAll('a[href*="/player/"]').forEach(l => {
        const h = l.href;
        if (h.includes('/player/') && !h.includes('random')) urls.push(h);
    });
    return { urls };
}
"""


def parse_url(url: str):
    m = URL_RE.search(url)
    if not m:
        return None
    pid = m.group(1)
    slug = m.group(2)
    name = slug.replace("-", " ").title()
    return pid, slug, name


def save_csv(rows, out_path):
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["sofifa_id", "name_slug", "name"])
        w.writerows(rows)


def load_state() -> int:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, encoding="utf-8") as f:
                return int(json.load(f).get("next_offset", 0))
        except Exception:
            return 0
    return 0


def save_state(next_offset: int):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump({"next_offset": next_offset}, f)


async def wait_real_players(page, timeout: int = 600) -> bool:
    """在同一页上轮询等待【真实球员】链接出现(不主动 reload)。"""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            cnt = await page.evaluate(
                """() => {
                    let n = 0;
                    document.querySelectorAll('a[href*="/player/"]').forEach(l => {
                        if (/\\/player\\/\\d+\\//.test(l.href)) n++;
                    });
                    return n;
                }"""
            )
            if cnt > 0:
                return True
        except Exception:
            pass
        await asyncio.sleep(1)
    return False


async def has_clearance(context) -> bool:
    try:
        cookies = await context.cookies("https://sofifa.com")
        return any(c.get("name") == "cf_clearance" for c in cookies)
    except Exception:
        return False


async def scrape(max_pages: int, out_path: str = "sofifa_players.csv", resume: bool = True):
    out_rows = []
    seen = set()
    if resume and os.path.exists(out_path):
        try:
            with open(out_path, encoding="utf-8") as f:
                r = csv.reader(f)
                next(r, None)
                for row in r:
                    if len(row) >= 3 and row[0] not in seen:
                        seen.add(row[0])
                        out_rows.append((row[0], row[1], row[2]))
            if out_rows:
                print(f"[resume] 已载入 {len(out_rows)} 名历史球员", flush=True)
        except Exception:
            pass

    base = "https://sofifa.com/players?col=oa&sort=desc"
    step = PAGE_SIZE

    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=PROFILE_DIR,
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-setuid-sandbox",
            ],
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1920, "height": 1080},
            locale="en-US",
            timezone_id="America/New_York",
            extra_http_headers={
                "Accept-Language": "en-US,en;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
        )
        await context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"
        )
        page = await context.new_page()

        if await has_clearance(context):
            print(">>> 检测到 cf_clearance cookie, 第一页预计 0 次点击。", flush=True)
        else:
            print(">>> 未检测到 cf_clearance cookie, 第一页需手动点 1 次验证。", flush=True)

        start_offset = load_state() if resume else 0
        offset = start_offset
        page_num = offset // step + 1
        first_page = True  # 第一页用 goto(可能需点), 之后全部用页面内 fetch

        while True:
            if max_pages and page_num > max_pages:
                print(">>> 已达到 --max-pages 上限, 结束。", flush=True)
                break
            url = f"{base}&offset={offset}"
            print(f"[page {page_num}] offset={offset} {url}", flush=True)

            real_urls = []
            if first_page:
                # 第一页: goto + 等待(若弹验证, 用户点 1 次, 脚本停在本页等)
                for attempt in range(1, 5):
                    try:
                        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    except Exception as e:
                        print(f"  goto 出错: {e}", flush=True)
                    print("  等待球员数据(若弹验证请手动点 1 次, 之后全自动)...", flush=True)
                    if not await wait_real_players(page, timeout=600):
                        print(">>> 10 分钟内仍无真实球员链接, 停止本轮。", flush=True)
                        await context.close()
                        return out_rows
                    data = await page.evaluate(READ_DOM_JS)
                    real_urls = [u for u in data["urls"] if parse_url(u)]
                    if real_urls:
                        break
                    wait_s = 15 * attempt
                    print(f"  本页 0 条真实球员(疑似限流/验证页), {wait_s}s 后重试 {attempt}/4 ...", flush=True)
                    await asyncio.sleep(wait_s)
                first_page = False
            else:
                # 后续页: 页面内 fetch, 不导航, 不重新弹验证
                for attempt in range(1, 5):
                    try:
                        res = await page.evaluate(FETCH_JS, url)
                    except Exception as e:
                        res = {"status": -2, "urls": [], "error": str(e)}
                    status = res.get("status", -1)
                    cand = [u for u in res.get("urls", []) if parse_url(u)]
                    if status == 200 and cand:
                        real_urls = cand
                        break
                    if status in (403, 503, 429) or status == -1:
                        # 偶尔被重新 challenge: 退回 goto 等用户点一次, 之后继续 fetch
                        print(f"  fetch 被拦截(status={status}), 退回 goto 等待点击...", flush=True)
                        try:
                            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                        except Exception as e:
                            print(f"  goto 出错: {e}", flush=True)
                        if not await wait_real_players(page, timeout=600):
                            print(">>> 10 分钟内仍无真实球员链接, 停止本轮。", flush=True)
                            await context.close()
                            return out_rows
                        data = await page.evaluate(READ_DOM_JS)
                        real_urls = [u for u in data["urls"] if parse_url(u)]
                        first_page = False
                        break
                    # 200 但 0 条 -> 限流, 退避重试
                    wait_s = 15 * attempt
                    print(f"  fetch 返回 {status} 但 0 条真实球员, {wait_s}s 后重试 {attempt}/4 ...", flush=True)
                    await asyncio.sleep(wait_s)

            if not real_urls:
                print(f">>> 连续多次 0 条, 疑似被拦截, 在 offset={offset} 处停止。", flush=True)
                break

            for u in real_urls:
                parsed = parse_url(u)
                if parsed and parsed[0] not in seen:
                    seen.add(parsed[0])
                    out_rows.append(parsed)

            if page_num == (start_offset // step + 1) and len(real_urls) > step:
                step = len(real_urls)
                print(f"  本页返回 {len(real_urls)} 条, 已扩大步长到 {step}/页", flush=True)

            has_next = len(real_urls) >= step
            print(f"  ok +{len(real_urls)} (total {len(out_rows)}) next={has_next}", flush=True)
            save_csv(out_rows, out_path)
            save_state(offset + step)

            if not has_next:
                print(">>> 已到末尾(末页不足一页)。", flush=True)
                break

            offset += step
            page_num += 1
            await asyncio.sleep(1.5)

        await context.close()
    return out_rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-pages", type=int, default=0, help="0=全量")
    ap.add_argument("--out", default="sofifa_players.csv")
    ap.add_argument("--no-resume", action="store_true", help="从头开始, 忽略断点")
    args = ap.parse_args()

    rows = asyncio.run(scrape(args.max_pages, args.out, resume=not args.no_resume))
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["sofifa_id", "name_slug", "name"])
        w.writerows(rows)
    print(f"\nDONE: {len(rows)} players -> {args.out}", flush=True)


if __name__ == "__main__":
    main()
