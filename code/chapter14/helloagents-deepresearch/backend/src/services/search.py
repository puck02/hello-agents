"""Search dispatch helpers leveraging HelloAgents SearchTool."""

from __future__ import annotations

import logging
from typing import Any, Optional, Tuple

from hello_agents.tools import SearchTool

from config import Configuration
from utils import (
    deduplicate_and_format_sources,
    format_sources,
    get_config_value,
)

logger = logging.getLogger(__name__)

# 每个搜索结果来源允许的最大 token 数，防止单条结果撑爆 LLM 上下文窗口
MAX_TOKENS_PER_SOURCE = 2000

# 全局共享的搜索工具实例（hybrid 模式：优先调用精确后端，失败时自动回退）
# 使用全局单例避免每次搜索都重新初始化，减少开销
_GLOBAL_SEARCH_TOOL = SearchTool(backend="hybrid")


def dispatch_search(
    query: str,
    config: Configuration,
    loop_count: int,
) -> Tuple[dict[str, Any] | None, list[str], Optional[str], str]:
    """调用配置的搜索后端执行搜索，并将响应标准化为统一格式。

    Returns:
        payload:      标准化后的搜索结果字典，含 results / backend / answer / notices
        notices:      后端返回的提示信息列表（如"结果有限"等警告）
        answer_text:  部分搜索后端（如 Perplexity）会直接返回 AI 答案，没有则为 None
        backend_label: 实际使用的后端名称（可能与配置不同，如 hybrid 回退后）
    """

    # 从配置中读取搜索后端名称（如 "tavily"、"duckduckgo"、"hybrid" 等）
    search_api = get_config_value(config.search_api)

    try:
        # 调用搜索工具，structured 模式返回结构化字典而非纯文本
        raw_response = _GLOBAL_SEARCH_TOOL.run(
            {
                "input": query,
                "backend": search_api,
                "mode": "structured",
                "fetch_full_page": config.fetch_full_page,   # 是否抓取完整网页内容
                "max_results": 5,                            # 最多返回 5 条结果
                "max_tokens_per_source": MAX_TOKENS_PER_SOURCE,
                "loop_count": loop_count,                    # 已执行的搜索轮次，供后端做去重
            }
        )
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.exception("Search backend %s failed: %s", search_api, exc)
        raise

    # 部分后端异常时会直接返回字符串错误信息而非字典
    # 此时构造一个空结果的标准字典，保证后续逻辑不崩溃
    if isinstance(raw_response, str):
        notices = [raw_response]
        logger.warning("Search backend %s returned text notice: %s", search_api, raw_response)
        payload: dict[str, Any] = {
            "results": [],
            "backend": search_api,
            "answer": None,
            "notices": notices,
        }
    else:
        payload = raw_response
        notices = list(payload.get("notices") or [])

    backend_label = str(payload.get("backend") or search_api)
    answer_text = payload.get("answer")   # AI 直接答案（Perplexity 等后端特有）
    results = payload.get("results", [])

    if notices:
        for notice in notices:
            logger.info("Search notice (%s): %s", backend_label, notice)

    logger.info(
        "Search backend=%s resolved_backend=%s answer=%s results=%s",
        search_api,
        backend_label,
        bool(answer_text),
        len(results),
    )

    return payload, notices, answer_text, backend_label


def prepare_research_context(
    search_result: dict[str, Any] | None,
    answer_text: Optional[str],
    config: Configuration,
) -> tuple[str, str]:
    """将搜索结果整理成供下游 LLM Agent 使用的两种格式。

    Returns:
        sources_summary: 简洁的来源列表字符串，用于展示给用户看（标题 + URL）
        context:         详细的研究上下文字符串，用于喂给摘要 Agent 做总结
                         若搜索后端有直接 AI 答案，会拼接在上下文开头作为补充
    """

    # 格式化来源摘要：提取每条结果的标题和 URL，供前端展示参考文献列表
    sources_summary = format_sources(search_result)

    # 格式化详细上下文：去重、截断过长内容，拼装成 LLM 可直接阅读的文本块
    context = deduplicate_and_format_sources(
        search_result or {"results": []},
        max_tokens_per_source=MAX_TOKENS_PER_SOURCE,
        fetch_full_page=config.fetch_full_page,
    )

    # 若后端提供了 AI 直接答案（如 Perplexity），将其置于上下文开头作为高质量参考
    if answer_text:
        context = f"AI直接答案：\n{answer_text}\n\n{context}"

    return sources_summary, context
