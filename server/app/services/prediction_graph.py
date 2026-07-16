"""LangGraph 预测流程 — 用 StateGraph 编排多模型并行预测 + 汇总

流程图:
    [load_match] → [parallel_predict] → [validate_outputs] → [aggregate] → [validate_summary] → END
                                                      ↓ (校验失败)
                                               [retry_failed] ──→ [parallel_predict]

节点说明:
- load_match: 加载比赛数据 + 活跃模型列表 + 已有预测
- parallel_predict: 并行调用所有模型生成预测 (asyncio.gather)
- validate_outputs: 用 Output Parser 解析+校验每个预测，标记失败项
- retry_failed: 对校验失败的预测重试 (最多 MAX_RETRIES 次)
- aggregate: 用汇总模型 (默认 DeepSeek) 综合所有预测
- validate_summary: 解析+校验汇总结果
"""

from __future__ import annotations

import asyncio
import datetime as dt
from datetime import timedelta
from typing import Optional, TypedDict

from langgraph.graph import StateGraph, END
from loguru import logger


# ── State 定义 ──────────────────────────────────────────────────

def _merge_list(existing: list, new: list) -> list:
    """合并列表 (用于 Annotated 状态 reducer)"""
    return existing + new


class PredictionState(TypedDict, total=False):
    """LangGraph 状态 — 在节点间流转的数据

    使用 TypedDict 确保 LangGraph 能正确识别所有字段。
    total=False 表示所有字段都是可选的（初始化时不需要全部提供）。
    """
    # ── 输入 ──
    match_id: Optional[int]                            # None = 批量模式
    match_data_list: list[dict]                        # 序列化的比赛信息列表
    models: list[dict]                                 # 活跃模型列表 [{id, name, model_id}]

    # ── 预测阶段 ──
    predictions: list[dict]                            # 成功的预测 [{model_id, model_name, raw, parsed}]
    failed: list[dict]                                 # 失败的预测 [{model_id, model_name, error, retries}]
    skipped: int                                       # 跳过的已有预测数

    # ── 汇总阶段 ──
    summary_model_id: str                              # 汇总用的模型 ID
    summary_raw: Optional[dict]                        # 汇总原始输出
    summary: Optional[dict]                            # 汇总解析后结果

    # ── 控制流 ──
    retry_count: int
    max_retries: int

    # ── 统计 ──
    total_models: int
    total_matches: int
    completed_matches: int


# ── 节点实现 ──────────────────────────────────────────────────

async def load_match(state: PredictionState) -> PredictionState:
    """加载比赛数据、活跃模型、已有预测"""
    from app.database import async_session_factory
    from app.models.match import Match, MatchStatus
    from app.models.ai_model import AIModel
    from app.models.prediction import Prediction
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    async with async_session_factory() as session:
        # 单场比赛模式
        if state.get("match_id"):
            stmt = (
                select(Match)
                .where(Match.id == state["match_id"])
                .options(
                    selectinload(Match.home_team),
                    selectinload(Match.away_team),
                    selectinload(Match.league),
                )
            )
            result = await session.execute(stmt)
            match = result.scalar_one_or_none()
            if not match:
                raise ValueError(f"Match {state['match_id']} not found")
            matches = [match]
        else:
            # 批量模式：未来 3 天的 upcoming 比赛（覆盖所有联赛）
            now = dt.datetime.now(dt.timezone.utc)
            deadline = now + timedelta(days=3)
            stmt = (
                select(Match)
                .where(Match.status == MatchStatus.upcoming)
                .where(Match.match_time <= deadline)
                .options(
                    selectinload(Match.home_team),
                    selectinload(Match.away_team),
                    selectinload(Match.league),
                )
            )
            result = await session.execute(stmt)
            matches = list(result.scalars().all())

        # 活跃模型
        model_stmt = select(AIModel).where(AIModel.is_active == True)
        model_result = await session.execute(model_stmt)
        models = [
            {"id": m.id, "name": m.name, "model_id": m.model_id}
            for m in model_result.scalars().all()
        ]

        # 汇总模型
        summary_stmt = select(AIModel).where(AIModel.name == "DeepSeek", AIModel.is_active == True).limit(1)
        summary_result = await session.execute(summary_stmt)
        summary_model = summary_result.scalar_one_or_none()
        summary_model_id = summary_model.model_id if summary_model else "deepseek-chat"

        # 查找已有预测
        existing_model_ids_map: dict[int, list[int]] = {}  # match_id → [model_id, ...]
        for m in matches:
            pred_stmt = select(Prediction.model_id).where(Prediction.match_id == m.id)
            pred_result = await session.execute(pred_stmt)
            existing_model_ids_map[m.id] = [row[0] for row in pred_result.all()]

        # 序列化比赛数据
        match_data_list = []
        for m in matches:
            home_name = m.home_team.cn_name or m.home_team.name
            away_name = m.away_team.cn_name or m.away_team.name
            match_data_list.append({
                "id": m.id,
                "home_name": home_name,
                "away_name": away_name,
                "round": m.round,
                "venue": m.venue,
                "match_time": m.match_time.isoformat() if m.match_time else None,
                "home_team_id": m.home_team_id,
                "away_team_id": m.away_team_id,
                "league_name": m.league.cn_name if m.league else None,
                "existing_model_ids": existing_model_ids_map.get(m.id, []),
            })

    state["match_data_list"] = match_data_list
    state["models"] = models
    state["summary_model_id"] = summary_model_id
    state["total_matches"] = len(match_data_list)
    state["total_models"] = len(models)
    state["completed_matches"] = 0

    logger.info(
        f"Loaded {len(match_data_list)} matches, {len(models)} active models, "
        f"summary model: {summary_model_id}"
    )
    return state


async def parallel_predict(state: PredictionState) -> PredictionState:
    """并行调用所有模型生成预测"""
    from app.core.ofoxai import OfoxAIClient
    from app.config import get_settings
    from app.database import async_session_factory
    from app.models.match import Match
    from app.models.head_to_head import HeadToHead
    from app.utils.prompt_builder import SYSTEM_PROMPT, build_user_prompt
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    settings = get_settings()
    client = OfoxAIClient(api_key=settings.OFOXAI_API_KEY, base_url=settings.OFOXAI_BASE_URL)

    all_predictions = []
    all_failed = []
    total_skipped = 0

    try:
        async with async_session_factory() as session:
            for match_info in state.get("match_data_list", []):
                match_id = match_info["id"]
                existing_model_ids = match_info.get("existing_model_ids", [])

                # 加载完整 Match 对象
                stmt = (
                    select(Match)
                    .where(Match.id == match_id)
                    .options(
                        selectinload(Match.home_team),
                        selectinload(Match.away_team),
                        selectinload(Match.league),
                    )
                )
                result = await session.execute(stmt)
                match = result.scalar_one_or_none()
                if not match:
                    logger.warning(f"Match {match_id} not found, skipping")
                    continue

                # 获取 H2H 数据
                h2h_data = None
                try:
                    t1, t2 = sorted([match.home_team_id, match.away_team_id])
                    h2h_stmt = select(HeadToHead).where(
                        HeadToHead.team_one_id == t1,
                        HeadToHead.team_two_id == t2,
                    )
                    h2h_result = await session.execute(h2h_stmt)
                    h2h_record = h2h_result.scalar_one_or_none()
                    if h2h_record and h2h_record.matches:
                        h2h_data = h2h_record.matches
                except Exception as e:
                    logger.warning(f"Failed to get H2H for match {match_id}: {e}")

                # 构建 prompt (所有模型共享)
                user_prompt = build_user_prompt(
                    home_team=match.home_team,
                    away_team=match.away_team,
                    match=match,
                    head_to_head=h2h_data,
                    league_name=match.league.cn_name if match.league else None,
                )

                # 过滤需要预测的模型
                models_to_predict = []
                skipped = 0
                for model_info in state["models"]:
                    if model_info["id"] in existing_model_ids:
                        skipped += 1
                        logger.debug(f"  [{model_info['name']}] already predicted for match {match_id}, skip")
                        continue
                    models_to_predict.append(model_info)
                total_skipped += skipped

                if not models_to_predict:
                    logger.info(f"Match {match_id}: all models already predicted, skip")
                    continue

                home_name = match_info["home_name"]
                away_name = match_info["away_name"]
                logger.info(
                    f"Match {match_id} ({home_name} vs {away_name}): "
                    f"predicting with {len(models_to_predict)} models, {skipped} skipped"
                )

                # 并行调用所有模型
                async def _call_single_model(m_info: dict) -> dict:
                    m_name = m_info["name"]
                    m_id = m_info["model_id"]
                    try:
                        raw = await client.predict_match(
                            model=m_id,
                            system_prompt=SYSTEM_PROMPT,
                            user_prompt=user_prompt,
                        )
                        logger.info(
                            f"  [{m_name}] OK → result={raw.get('result')}, "
                            f"score={raw.get('score', {}).get('home')}-{raw.get('score', {}).get('away')}, "
                            f"confidence={raw.get('confidence')}"
                        )
                        return {
                            "match_id": match_id,
                            "model_id": m_info["id"],
                            "model_name": m_name,
                            "raw": raw,
                        }
                    except Exception as exc:
                        logger.error(f"  [{m_name}] FAILED: {exc}")
                        return {
                            "match_id": match_id,
                            "model_id": m_info["id"],
                            "model_name": m_name,
                            "error": str(exc),
                            "retries": state.get("retry_count", 0),
                        }

                results = await asyncio.gather(
                    *[_call_single_model(m) for m in models_to_predict],
                    return_exceptions=True,
                )

                for r in results:
                    if isinstance(r, Exception):
                        logger.error(f"  Unexpected error: {r}")
                        continue
                    if "error" in r:
                        all_failed.append(r)
                    else:
                        all_predictions.append(r)

    finally:
        await client.close()

    state["predictions"] = all_predictions
    state["failed"] = all_failed
    state["skipped"] = total_skipped

    logger.info(
        f"Parallel predict done: {len(all_predictions)} success, "
        f"{len(all_failed)} failed, {total_skipped} skipped"
    )
    return state


async def validate_outputs(state: PredictionState) -> PredictionState:
    """用 Output Parser 解析+校验每个预测结果"""
    from app.services.prediction_parsers import get_parser, ParseValidationError

    validated = []
    still_failed = []

    for pred in state.get("predictions", []):
        model_name = pred.get("model_name", "")
        raw = pred.get("raw", {})

        try:
            parser = get_parser(model_name)
            parsed = parser.parse(raw, model_name)
            parsed = parser.validate(parsed, model_name)
            pred["parsed"] = parsed
            validated.append(pred)
        except ParseValidationError as e:
            logger.warning(f"[{model_name}] Validation failed: {e}")
            pred["error"] = str(e)
            still_failed.append(pred)
        except Exception as e:
            logger.error(f"[{model_name}] Parse error: {e}")
            pred["error"] = str(e)
            still_failed.append(pred)

    # 合并之前失败的
    still_failed.extend(state.get("failed", []))

    state["predictions"] = validated
    state["failed"] = still_failed

    logger.info(f"Validation done: {len(validated)} valid, {len(still_failed)} failed")
    return state


def _should_retry(state: PredictionState) -> str:
    """条件边：判断是否需要重试失败的预测"""
    failed = state.get("failed", [])
    retry_count = state.get("retry_count", 0)
    max_retries = state.get("max_retries", 2)

    if failed and retry_count < max_retries:
        logger.info(f"Retrying {len(failed)} failed predictions (attempt {retry_count + 1}/{max_retries})")
        return "retry"
    return "aggregate"


async def retry_failed(state: PredictionState) -> PredictionState:
    """重试校验失败的预测"""
    import time as _time
    from app.core.ofoxai import OfoxAIClient
    from app.config import get_settings
    from app.database import async_session_factory
    from app.models.match import Match
    from app.models.head_to_head import HeadToHead
    from app.utils.prompt_builder import SYSTEM_PROMPT, build_user_prompt
    from app.services.prediction_parsers import get_parser
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    settings = get_settings()
    client = OfoxAIClient(api_key=settings.OFOXAI_API_KEY, base_url=settings.OFOXAI_BASE_URL)

    retry_count = state.get("retry_count", 0) + 1
    succeeded = []
    still_failed = []
    _failed_list = state.get("failed", [])

    logger.info(f"[Retry] ====== START (attempt {retry_count}/2) ====== | "
                f"total_failed={len(_failed_list)} | base_url={settings.OFOXAI_BASE_URL}")

    _retry_start = _time.monotonic()

    try:
        async with async_session_factory() as session:
            for idx, failed_pred in enumerate(_failed_list):
                match_id = failed_pred.get("match_id")
                model_name = failed_pred.get("model_name", "")
                _model_start = _time.monotonic()

                logger.info(f"[Retry] --- [{idx+1}/{len(_failed_list)}] START | "
                            f"model={model_name} | match_id={match_id} | "
                            f"prev_error={failed_pred.get('error', 'N/A')!r}")

                # 找到模型信息
                model_info = None
                for m in state["models"]:
                    if m["id"] == failed_pred.get("model_id"):
                        model_info = m
                        break
                if not model_info:
                    logger.warning(f"[Retry] [{model_name}] SKIP: model_info not found")
                    still_failed.append(failed_pred)
                    continue

                # 加载比赛 + H2H
                _db_start = _time.monotonic()
                stmt = (
                    select(Match)
                    .where(Match.id == match_id)
                    .options(
                        selectinload(Match.home_team),
                        selectinload(Match.away_team),
                        selectinload(Match.league),
                    )
                )
                result = await session.execute(stmt)
                match = result.scalar_one_or_none()
                if not match:
                    logger.warning(f"[Retry] [{model_name}] SKIP: match {match_id} not found")
                    still_failed.append(failed_pred)
                    continue

                h2h_data = None
                try:
                    t1, t2 = sorted([match.home_team_id, match.away_team_id])
                    h2h_stmt = select(HeadToHead).where(
                        HeadToHead.team_one_id == t1,
                        HeadToHead.team_two_id == t2,
                    )
                    h2h_result = await session.execute(h2h_stmt)
                    h2h_record = h2h_result.scalar_one_or_none()
                    if h2h_record and h2h_record.matches:
                        h2h_data = h2h_record.matches
                except Exception:
                    pass

                _db_elapsed = _time.monotonic() - _db_start
                user_prompt = build_user_prompt(
                    home_team=match.home_team,
                    away_team=match.away_team,
                    match=match,
                    head_to_head=h2h_data,
                    league_name=match.league.cn_name if match.league else None,
                )

                try:
                    _ai_start = _time.monotonic()
                    raw = await client.predict_match(
                        model=model_info["model_id"],
                        system_prompt=SYSTEM_PROMPT,
                        user_prompt=user_prompt,
                    )
                    _ai_elapsed = _time.monotonic() - _ai_start
                    parser = get_parser(model_name)
                    parsed = parser.parse(raw, model_name)
                    parsed = parser.validate(parsed, model_name)

                    _total_elapsed = _time.monotonic() - _model_start
                    succeeded.append({
                        "match_id": match_id,
                        "model_id": model_info["id"],
                        "model_name": model_name,
                        "raw": raw,
                        "parsed": parsed,
                    })
                    logger.info(
                        f"  [{model_name}] Retry OK | "
                        f"db_cost={_db_elapsed:.2f}s | ai_cost={_ai_elapsed:.2f}s | total={_total_elapsed:.2f}s"
                    )
                except Exception as exc:
                    _total_elapsed = _time.monotonic() - _model_start
                    _exc_type = type(exc).__name__
                    _exc_msg = str(exc)[:300]
                    logger.error(
                        f"  [{model_name}] Retry FAILED: {_exc_type}: {_exc_msg} | "
                        f"db_cost={_db_elapsed:.2f}s | total={_total_elapsed:.2f}s"
                    )
                    failed_pred["retries"] = retry_count
                    still_failed.append(failed_pred)

    finally:
        await client.close()

    _retry_total = _time.monotonic() - _retry_start

    # 合并成功重试的到 predictions
    state["predictions"] = state.get("predictions", []) + succeeded
    state["failed"] = still_failed
    state["retry_count"] = retry_count

    logger.info(f"[Retry] ====== DONE ====== | recovered={len(succeeded)} | still_failed={len(still_failed)} | "
                f"total_time={_retry_total:.2f}s | avg_per_model={(_retry_total/max(len(_failed_list),1)):.2f}s")
    return state


async def aggregate(state: PredictionState) -> PredictionState:
    """综合所有模型的预测，生成汇总结论"""
    from app.core.ofoxai import OfoxAIClient
    from app.config import get_settings
    from app.database import async_session_factory
    from app.models.prediction import Prediction
    from app.models.prediction_summary import PredictionSummary
    from app.utils.prompt_builder import build_summary_prompt
    from app.services.prediction_parsers import SummaryParser
    from sqlalchemy import select

    predictions = state.get("predictions", [])
    if not predictions:
        logger.warning("No valid predictions to aggregate")
        return state

    settings = get_settings()
    client = OfoxAIClient(api_key=settings.OFOXAI_API_KEY, base_url=settings.OFOXAI_BASE_URL)
    summary_parser = SummaryParser()

    try:
        async with async_session_factory() as session:
            # 按 match_id 分组
            from collections import defaultdict
            by_match: dict[int, list[dict]] = defaultdict(list)
            for pred in predictions:
                by_match[pred["match_id"]].append(pred)

            for match_id, match_preds in by_match.items():
                # 获取比赛信息
                match_info = None
                for md in state.get("match_data_list", []):
                    if md["id"] == match_id:
                        match_info = md
                        break
                if not match_info:
                    continue

                # ── 加载历史预测（补充被跳过的模型）─────────────
                existing_model_ids_from_new = {p["model_id"] for p in match_preds}
                
                # 从数据库查询该比赛的所有历史预测（预加载 ai_model 关系避免异步懒加载错误）
                from sqlalchemy.orm import selectinload
                hist_stmt = (
                    select(Prediction)
                    .options(selectinload(Prediction.ai_model))  # 预加载模型关系
                    .where(Prediction.match_id == match_id)
                    .where(Prediction.model_id.notin_(existing_model_ids_from_new))
                )
                hist_result = await session.execute(hist_stmt)
                historical_predictions = list(hist_result.scalars().all())

                # 转换历史预测为统一格式
                for hp in historical_predictions:
                    try:
                        # 尝试解析 raw_response 为 JSON
                        import json as _json
                        raw_parsed = _json.loads(hp.raw_response) if hp.raw_response else {}
                    except (TypeError, ValueError):
                        raw_parsed = {}

                    match_preds.append({
                        "match_id": match_id,
                        "model_id": hp.model_id,
                        "model_name": getattr(hp.ai_model, 'name', f'Model_{hp.model_id}'),
                        "raw": raw_parsed,
                        "parsed": {
                            "result": hp.result.value if hasattr(hp.result, 'value') else str(hp.result),
                            "score": {
                                "home": hp.score_home,
                                "away": hp.score_away,
                            },
                            "confidence": hp.confidence,
                            "analysis": hp.analysis or "",
                        },
                        "_is_historical": True,  # 标记为历史数据
                    })

                logger.info(
                    f"Aggregate match {match_id}: "
                    f"{len(match_preds) - len(historical_predictions)} new + "
                    f"{len(historical_predictions)} historical = "
                    f"{len(match_preds)} total predictions"
                )

                # 构建汇总 prompt（使用合并后的完整数据）
                pred_data = []
                for p in match_preds:
                    parsed = p.get("parsed", p.get("raw", {}))
                    pred_data.append({
                        "model_name": p.get("model_name", ""),
                        "result": parsed.get("result", ""),
                        "score_home": parsed.get("score", {}).get("home"),
                        "score_away": parsed.get("score", {}).get("away"),
                        "confidence": parsed.get("confidence", 5),
                        "analysis": parsed.get("analysis", ""),
                    })

                summary_prompt = build_summary_prompt(
                    home_team=match_info["home_name"],
                    away_team=match_info["away_name"],
                    predictions=pred_data,
                    league_name=match_info.get("league_name"),
                )

                # 调用汇总模型
                try:
                    summary_raw = await client.predict_match(
                        model=state["summary_model_id"],
                        system_prompt="你是一位足球分析总编辑，请综合多个AI模型的预测结果，生成统一的综合预测结论。严格按照JSON格式输出，不要输出其他任何内容。",
                        user_prompt=summary_prompt,
                    )

                    # 解析汇总
                    parsed_summary = summary_parser.parse(summary_raw)
                    parsed_summary = summary_parser.validate(parsed_summary)

                    logger.info(
                        f"Summary for match {match_id}: "
                        f"score={parsed_summary.get('score', {}).get('home')}-"
                        f"{parsed_summary.get('score', {}).get('away')}, "
                        f"short={parsed_summary.get('short_summary')}"
                    )

                    # 存入 state
                    state["summary_raw"] = summary_raw
                    state["summary"] = parsed_summary

                    # 写入数据库 — 仅保存本次新生成的预测（跳过历史数据避免重复）
                    new_predictions = [p for p in match_preds if not p.get("_is_historical")]
                    for p in new_predictions:
                        parsed = p.get("parsed", p.get("raw", {}))
                        score = parsed.get("score", {})
                        score_alt = parsed.get("score_alt", {})

                        prediction = Prediction(
                            match_id=match_id,
                            model_id=p["model_id"],
                            result=parsed["result"],
                            score_home=score.get("home"),
                            score_away=score.get("away"),
                            score_alt_home=score_alt.get("home"),
                            score_alt_away=score_alt.get("away"),
                            score_alt_prob=score_alt.get("probability"),
                            confidence=parsed.get("confidence"),
                            analysis=parsed.get("analysis"),
                            raw_response=p.get("raw"),
                        )
                        session.add(prediction)

                    # 保存/更新汇总
                    score = parsed_summary.get("score", {})
                    score_alt = parsed_summary.get("score_alt", {})
                    sum_stmt = select(PredictionSummary).where(PredictionSummary.match_id == match_id)
                    sum_result = await session.execute(sum_stmt)
                    existing = sum_result.scalar_one_or_none()

                    if existing:
                        existing.score_home = score.get("home")
                        existing.score_away = score.get("away")
                        existing.score_alt_home = score_alt.get("home")
                        existing.score_alt_away = score_alt.get("away")
                        existing.short_summary = parsed_summary.get("short_summary")
                        existing.summary = parsed_summary.get("summary")
                        existing.confidence = parsed_summary.get("confidence")
                        logger.info(f"Summary updated for match {match_id}")
                    else:
                        summary = PredictionSummary(
                            match_id=match_id,
                            score_home=score.get("home"),
                            score_away=score.get("away"),
                            score_alt_home=score_alt.get("home"),
                            score_alt_away=score_alt.get("away"),
                            short_summary=parsed_summary.get("short_summary"),
                            summary=parsed_summary.get("summary"),
                            confidence=parsed_summary.get("confidence"),
                        )
                        session.add(summary)
                        logger.info(f"Summary created for match {match_id}")

                except Exception as e:
                    logger.error(f"Summary generation failed for match {match_id}: {e}")

            await session.commit()

    finally:
        await client.close()

    state["completed_matches"] = state.get("completed_matches", 0) + len(by_match)
    return state


# ── Graph 构建 ──────────────────────────────────────────────────

def build_prediction_graph() -> StateGraph:
    """构建预测流程的 LangGraph StateGraph"""
    graph = StateGraph(PredictionState)

    # 添加节点
    graph.add_node("load_match", load_match)
    graph.add_node("parallel_predict", parallel_predict)
    graph.add_node("validate_outputs", validate_outputs)
    graph.add_node("retry_failed", retry_failed)
    graph.add_node("aggregate", aggregate)

    # 设置入口
    graph.set_entry_point("load_match")

    # 定义边
    graph.add_edge("load_match", "parallel_predict")
    graph.add_edge("parallel_predict", "validate_outputs")

    # 条件边：校验后决定重试还是汇总
    graph.add_conditional_edges(
        "validate_outputs",
        _should_retry,
        {
            "retry": "retry_failed",
            "aggregate": "aggregate",
        },
    )

    # 重试后回到校验
    graph.add_edge("retry_failed", "validate_outputs")

    # 汇总后结束
    graph.add_edge("aggregate", END)

    return graph


def get_prediction_app():
    """获取编译后的预测流程 app"""
    graph = build_prediction_graph()
    return graph.compile()
