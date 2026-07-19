"""把本地球员(db_id_name.csv)按名字映射到 sofifa_players.csv, 产出映射 + 写库 SQL。

- 仅按名字匹配, 规范化(去变音/标点)后三级级联: 精确 -> 模糊(分词倒排+difflib) -> 待复核
- 只读两个 CSV, 不改数据库; 产出:
    player_sofifa_map.csv  全部本地球员匹配结果
    update_players_logo.sql 仅高置信匹配的 UPDATE(+ADD COLUMN sofifa_id)
    player_sofifa_review.csv 低置信/未匹配, 供人工复核
"""
from __future__ import annotations

import csv
import sys
import unicodedata
from difflib import SequenceMatcher

DB_CSV = "db_id_name_all.csv"
SOFIFA_CSV = "sofifa_players.csv"
MAP_OUT = "player_sofifa_map.csv"
SQL_OUT = "update_players_logo.sql"
REVIEW_OUT = "player_sofifa_review.csv"

EXACT = "exact"          # 规范化后精确
FUZZY = "fuzzy"          # 相似度达标
REVIEW = "review"        # 低置信/歧义
UNMATCHED = "unmatched"  # 无候选


def norm(s: str) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower()
    for ch in ".'-–’":
        s = s.replace(ch, " ")
    return " ".join(s.split())


def tokens(s: str):
    return [t for t in norm(s).split() if len(t) > 1]  # 丢弃单字母碎片


def load_db(path):
    rows = []
    with open(path, encoding="utf-8") as f:
        sample = f.read(4096)
        f.seek(0)
        delim = "\t" if "\t" in sample else ","
        r = csv.reader(f, delimiter=delim)
        for row in r:
            if not row:
                continue
            lid = row[0].strip()
            name = row[1].strip() if len(row) > 1 else ""
            if not lid.isdigit():
                continue  # 跳过表头
            rows.append((int(lid), name))
    return rows


def load_sofifa(path):
    idx = []
    norm_map = {}        # norm_name -> [idx,...]
    token_index = {}     # token -> set(idx)
    with open(path, encoding="utf-8") as f:
        r = csv.DictReader(f)
        for i, row in enumerate(r):
            sid = row["sofifa_id"].strip()
            name = row["name"].strip()
            idx.append((sid, name, norm(name)))
            norm_map.setdefault(idx[i][2], []).append(i)
            for t in set(tokens(name)):
                token_index.setdefault(t, set()).add(i)
    return idx, norm_map, token_index


def best_match(local_name, sofifa_idx, norm_map, token_index):
    key = norm(local_name)
    if not key:
        return None, UNMATCHED, 0.0
    # 1) 精确
    if key in norm_map:
        cands = norm_map[key]
        if len(cands) == 1:
            return sofifa_idx[cands[0]][0], EXACT, 1.0
        # 多个同名 -> 选原始名最像的, 但仍标 review 让人工确认
        scored = []
        for ci in cands:
            ratio = SequenceMatcher(None, local_name.lower(), sofifa_idx[ci][1].lower()).ratio()
            scored.append((ratio, ci))
        scored.sort(reverse=True)
        return sofifa_idx[scored[0][1]][0], REVIEW, scored[0][0]
    # 2) 模糊: 仅比对共享词条的候选
    cand_set = set()
    for t in tokens(local_name):
        cand_set |= token_index.get(t, set())
    if not cand_set:
        return None, UNMATCHED, 0.0
    scored = []
    for ci in cand_set:
        sname_norm = sofifa_idx[ci][2]
        ratio = SequenceMatcher(None, key, sname_norm).ratio()
        # 词条包含度(短名被长名完整包含)
        lt = set(tokens(local_name))
        st = set(tokens(sofifa_idx[ci][1]))
        cont = len(lt & st) / max(1, min(len(lt), len(st)))
        score = max(ratio, cont)
        scored.append((score, ci))
    scored.sort(reverse=True)
    best_score, best_ci = scored[0]
    second = scored[1][0] if len(scored) > 1 else 0.0
    if best_score >= 0.85 and (best_score - second) >= 0.05:
        return sofifa_idx[best_ci][0], FUZZY, best_score
    return sofifa_idx[best_ci][0], REVIEW, best_score


def avatar_url(sid: str) -> str:
    s = sid
    return f"https://cdn.sofifa.net/players/{s[:3]}/{s[3:]}/26_120.png"


def main():
    db = load_db(DB_CSV)
    sofifa_idx, norm_map, token_index = load_sofifa(SOFIFA_CSV)
    sid_to_name = {s[0]: s[1] for s in sofifa_idx}  # sofifa_id -> 原始名
    print(f"[load] 本地球员 {len(db)} 个, sofifa {len(sofifa_idx)} 个", flush=True)

    stats = {EXACT: 0, FUZZY: 0, REVIEW: 0, UNMATCHED: 0}
    map_rows = []
    review_rows = []
    used_sid = set()  # 贪心去重: 每个 sofifa_id 只分配给一个本地球员
    sql_lines = [
        "-- 仅高置信(exact/fuzzy, 相似度>=0.85)匹配: 用 sofifa 名字写 full_name, 拼接头像写 logo",
        "-- 生成自 map_players.py; 每个 sofifa_id 已去重, 只分配给一个本地球员",
        "START TRANSACTION;",
    ]
    for lid, name in db:
        sid, dec, score = best_match(name, sofifa_idx, norm_map, token_index)
        if dec in (EXACT, FUZZY):
            if sid in used_sid:  # 已被其他本地球员占用 -> 降级进 review
                dec = REVIEW
                stats[REVIEW] += 1
                sname = next((s[1] for s in sofifa_idx if s[0] == sid), "")
                map_rows.append((lid, name, sid, dec, f"{score:.3f}", avatar_url(sid) if sid else ""))
                review_rows.append((lid, name, sid, sname, f"{score:.3f} (sofifa_id 已被占用)"))
                continue
            used_sid.add(sid)
            stats[dec] += 1
            url = avatar_url(sid) if sid else ""
            sofifa_name = sid_to_name.get(sid, "").replace("'", "''")  # 转义单引号
            map_rows.append((lid, name, sid, dec, f"{score:.3f}", url))
            sql_lines.append(
                f"UPDATE players SET full_name='{sofifa_name}', logo='{url}' WHERE id={lid};"
            )
        elif dec == REVIEW:
            stats[REVIEW] += 1
            sname = next((s[1] for s in sofifa_idx if s[0] == sid), "")
            map_rows.append((lid, name, sid, dec, f"{score:.3f}", avatar_url(sid) if sid else ""))
            review_rows.append((lid, name, sid, sname, f"{score:.3f}"))
        else:
            stats[UNMATCHED] += 1
            map_rows.append((lid, name, "", dec, "0.000", ""))
            review_rows.append((lid, name, "", "", "0.000"))

    with open(MAP_OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["local_id", "local_name", "sofifa_id", "decision", "score", "logo_url"])
        w.writerows(map_rows)
    with open(REVIEW_OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["local_id", "local_name", "sofifa_id", "sofifa_name", "score"])
        w.writerows(review_rows)
    sql_lines.append("COMMIT;")
    with open(SQL_OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(sql_lines) + "\n")

    total = len(db)
    print("\n=== 匹配统计 ===", flush=True)
    print(f"  精确(exact) : {stats[EXACT]}", flush=True)
    print(f"  模糊(fuzzy) : {stats[FUZZY]}", flush=True)
    print(f"  待复核      : {stats[REVIEW]}", flush=True)
    print(f"  未匹配      : {stats[UNMATCHED]}", flush=True)
    print(f"  高置信可写回: {stats[EXACT]+stats[FUZZY]} ({ (stats[EXACT]+stats[FUZZY])/total*100:.1f}%)", flush=True)
    print(f"\n产出: {MAP_OUT} | {SQL_OUT} | {REVIEW_OUT}", flush=True)


if __name__ == "__main__":
    main()
