"""Task summarization utilities."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Tuple

from hello_agents import ToolAwareSimpleAgent

from models import SummaryState, TodoItem
from config import Configuration
from utils import strip_thinking_tokens
from services.notes import build_note_guidance
from services.text_processing import clean_llm_output


class SummarizationService:
    """负责对单个研究任务生成摘要，支持同步和流式两种模式。

    同步模式（summarize_task）：调用 LLM 生成完整摘要后一次性返回，适用于非流式场景。
    流式模式（stream_task_summary）：逐块 yield LLM 输出，同时在线过滤 <think> 思考标记，
    适用于需要实时向前端推送摘要进度的场景。
    """

    def __init__(
        self,
        summarizer_factory: Callable[[], ToolAwareSimpleAgent],
        config: Configuration,
    ) -> None:
        # 使用工厂函数而非直接传入 agent 实例，保证每次调用都获得干净的新 agent
        self._agent_factory = summarizer_factory
        self._config = config

    def summarize_task(self, state: SummaryState, task: TodoItem, context: str) -> str:
        """同步模式：等 LLM 生成完整摘要后一次性返回字符串。"""

        prompt = self._build_prompt(state, task, context)

        agent = self._agent_factory()
        try:
            response = agent.run(prompt)
        finally:
            # 无论成功还是异常，都清除 agent 对话历史，避免上下文污染下一次调用
            agent.clear_history()

        summary_text = response.strip()
        # 若配置要求，去除 LLM 输出中的 <think>...</think> 推理过程
        if self._config.strip_thinking_tokens:
            summary_text = strip_thinking_tokens(summary_text)

        # 清理格式问题（如多余空行、代码块标记等）
        summary_text = clean_llm_output(summary_text)

        return summary_text or "暂无可用信息"

    def stream_task_summary(
        self, state: SummaryState, task: TodoItem, context: str
    ) -> Tuple[Iterator[str], Callable[[], str]]:
        """流式模式：返回 (生成器, 获取完整摘要的函数) 二元组。

        调用方先迭代生成器实时获取文字片段推送给前端，
        迭代结束后再调用 get_summary() 拿到完整的清洗后摘要存入任务。
        """

        prompt = self._build_prompt(state, task, context)
        remove_thinking = self._config.strip_thinking_tokens

        # raw_buffer：LLM 输出的原始累积文本（含 <think> 标记）
        # visible_output：已推送给前端的可见文本（不含 <think> 标记）
        # emit_index：raw_buffer 中已处理到的位置指针
        raw_buffer = ""
        visible_output = ""
        emit_index = 0
        agent = self._agent_factory()

        def flush_visible() -> Iterator[str]:
            """从 raw_buffer 中提取可见片段（跳过 <think>...</think> 块）。

            每次新 chunk 追加到 raw_buffer 后调用，增量 yield 尚未推送的可见文本。
            若 <think> 块尚未闭合（流还未收到 </think>），则等待下一个 chunk 再处理。
            """
            nonlocal emit_index, raw_buffer
            while True:
                # 从当前位置查找下一个 <think> 标记
                start = raw_buffer.find("<think>", emit_index)
                if start == -1:
                    # 没有 <think>，将剩余内容全部输出
                    if emit_index < len(raw_buffer):
                        segment = raw_buffer[emit_index:]
                        emit_index = len(raw_buffer)
                        if segment:
                            yield segment
                    break

                # <think> 之前的内容是可见文本，先输出
                if start > emit_index:
                    segment = raw_buffer[emit_index:start]
                    emit_index = start
                    if segment:
                        yield segment

                # 查找配对的 </think>
                end = raw_buffer.find("</think>", start)
                if end == -1:
                    # </think> 还未到达，等待更多 chunk，停止本轮处理
                    break
                # 跳过整个 <think>...</think> 块，移动指针到 </think> 之后
                emit_index = end + len("</think>")

        def generator() -> Iterator[str]:
            """实际的流式生成器：逐 chunk 读取 LLM 输出并按需过滤思考标记。"""
            nonlocal raw_buffer, visible_output, emit_index
            try:
                for chunk in agent.stream_run(prompt):
                    raw_buffer += chunk
                    if remove_thinking:
                        # 开启过滤：将新 chunk 加入缓冲后，提取可见片段 yield
                        for segment in flush_visible():
                            visible_output += segment
                            if segment:
                                yield segment
                    else:
                        # 不过滤：直接 yield 原始 chunk
                        visible_output += chunk
                        if chunk:
                            yield chunk
            finally:
                # 流结束后，将缓冲区中最后残留的可见内容一并输出
                if remove_thinking:
                    for segment in flush_visible():
                        visible_output += segment
                        if segment:
                            yield segment
                agent.clear_history()

        def get_summary() -> str:
            """流式迭代结束后调用，返回经过清洗的完整摘要文本。"""
            if remove_thinking:
                cleaned = strip_thinking_tokens(visible_output)
            else:
                cleaned = visible_output

            return clean_llm_output(cleaned)

        return generator(), get_summary

    def _build_prompt(self, state: SummaryState, task: TodoItem, context: str) -> str:
        """拼装摘要 Prompt：将任务元信息与搜索上下文组合成 LLM 输入。"""

        return (
            f"任务主题：{state.research_topic}\n"
            f"任务名称：{task.title}\n"
            f"任务目标：{task.intent}\n"
            f"检索查询：{task.query}\n"
            f"任务上下文：\n{context}\n"
            f"{build_note_guidance(task)}\n"
            "请按照以上协作要求先同步笔记，然后返回一份面向用户的 Markdown 总结（仍遵循任务总结模板）。"
        )
