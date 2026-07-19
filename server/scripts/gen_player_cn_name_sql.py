#!/usr/bin/env python
"""生成 players.cn_name 的批量更新 SQL（基于 db_id_name_all.csv）。

读取 db_id_name_all.csv（格式：<id>\t<英文名>，无表头，id 即 players.id），
调用翻译接口把英文名转成中文，输出可直接在数据库执行的 SQL 脚本。

用法：
    pip install deep-translator
    python server/scripts/gen_player_cn_name_sql.py                  # 默认 mymemory 引擎（国内通常可达）
    python server/scripts/gen_player_cn_name_sql.py --engine google  # 有代理/能连 Google 时用（质量更好）
    python server/scripts/gen_player_cn_name_sql.py --engine bing

可选参数：
    --csv   CSV 路径（默认 server/db_id_name_all.csv）
    --out   输出 SQL 路径（默认 server/scripts/update_players_cn_name.sql）
    --limit 只处理前 N 个（便于分批 / 避免翻译接口限流）
    --offset 跳过前 N 个
    --delay 每次翻译之间的间隔秒数（默认 0.05，防限流）
    --engine 翻译引擎：google / mymemory / bing（默认 mymemory）

说明：
    - 仅翻译成功才写 UPDATE；失败的行打印警告并跳过（保留原英文回退）。
    - 生成的 SQL 含 `SET NAMES utf8mb4;`，执行前建议人工抽查若干条。
    - 中文名中的单引号已转义。
    - MyMemory 免费额度约 5000 词/天，5632 条可能超额被拒；可分两天或换 bing/google。
"""
from __future__ import annotations

import argparse
import sys
import time

try:
    from deep_translator import GoogleTranslator, MyMemoryTranslator, BingTranslator
except ImportError:
    sys.exit("请先安装依赖：pip install deep-translator")


def esc(s: str) -> str:
    """转义 SQL 字符串中的单引号。"""
    return s.replace("'", "''")


def read_rows(csv_path: str, limit: int | None, offset: int) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    with open(csv_path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line.strip():
                continue
            parts = line.split("\t")
            if len(parts) < 2:
                continue
            pid, name = parts[0].strip(), parts[1].strip()
            if not pid or not name:
                continue
            rows.append((pid, name))
    return rows[offset : offset + limit] if limit is not None else rows[offset:]


def build_translator(engine: str):
    if engine == "google":
        return GoogleTranslator(source="en", target="zh-CN")
    if engine == "bing":
        return BingTranslator(source="en", target="zh-CN")
    return MyMemoryTranslator(source="en", target="zh-CN")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default="server/db_id_name_all.csv")
    ap.add_argument("--out", default="server/scripts/update_players_cn_name.sql")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--offset", type=int, default=0)
    ap.add_argument("--delay", type=float, default=0.05)
    ap.add_argument("--engine", choices=["google", "mymemory", "bing"], default="mymemory")
    args = ap.parse_args()

    translator = build_translator(args.engine)
    rows = read_rows(args.csv, args.limit, args.offset)
    print(f"待处理球员数：{len(rows)}（引擎：{args.engine}）")

    sql_lines = [
        "-- 自动生成：players.cn_name 批量更新",
        f"-- 数据源：db_id_name_all.csv + {args.engine} 翻译；执行前请人工抽查若干条",
        "SET NAMES utf8mb4;",
        "",
    ]

    ok = 0
    fail = 0
    for idx, (pid, name) in enumerate(rows, start=1):
        try:
            cn = translator.translate(name)
        except Exception as e:  # noqa: BLE001
            print(f"[跳过] id={pid} name={name}: {e}")
            fail += 1
            continue
        if not cn or cn.strip() == name:
            # 翻译失败或原样返回，跳过（保留英文回退）
            fail += 1
            continue
        cn = cn.strip()
        sql_lines.append(f"UPDATE players SET cn_name = '{esc(cn)}' WHERE id = {pid};")
        ok += 1
        if args.delay:
            time.sleep(args.delay)
        if idx % 200 == 0:
            print(f"  进度 {idx}/{len(rows)} ...")

    with open(args.out, "w", encoding="utf-8") as f:
        f.write("\n".join(sql_lines) + "\n")

    print(f"完成：成功 {ok}，跳过/失败 {fail}")
    print(f"SQL 已写入：{args.out}")


if __name__ == "__main__":
    main()
