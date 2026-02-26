"""Helpers for coordinating note tool usage instructions."""

from __future__ import annotations

import json

from models import TodoItem


def build_note_guidance(task: TodoItem) -> str:
    """为指定任务生成笔记工具的使用指引，拼接进 LLM 的 Prompt 中。

    研究系统设计了"笔记协作"机制：每个任务有一个对应的笔记（note），
    LLM Agent 在生成摘要前必须先读取笔记获取已有内容，完成后再将新信息写回笔记，
    实现多轮、多任务之间的信息持久化和共享。

    此函数根据任务是否已有笔记，生成两种不同的指引文本：
    - 已有笔记（task.note_id 非空）：指引 Agent 先读取再更新
    - 尚无笔记（task.note_id 为空）：指引 Agent 先创建笔记
    """

    # 为该任务的笔记统一打上标签，方便后续按 task_id 快速检索
    tags_list = ["deep_research", f"task_{task.id}"]
    tags_literal = json.dumps(tags_list, ensure_ascii=False)

    if task.note_id:
        # ── 情况一：任务已有笔记 ──────────────────────────────────
        # 构造「读取笔记」的工具调用指令，让 Agent 在总结前先获取已有内容
        read_payload = json.dumps({"action": "read", "note_id": task.note_id}, ensure_ascii=False)

        # 构造「更新笔记」的工具调用指令，让 Agent 将本轮新信息增量写入
        update_payload = json.dumps(
            {
                "action": "update",
                "note_id": task.note_id,
                "task_id": task.id,
                "title": f"任务 {task.id}: {task.title}",
                "note_type": "task_state",
                "tags": tags_list,
                "content": "请将本轮新增信息补充到任务概览中",
            },
            ensure_ascii=False,
        )

        # 返回完整的指引文本，[TOOL_CALL:note:...] 是系统约定的工具调用格式
        return (
            "笔记协作指引：\n"
            f"- 当前任务笔记 ID：{task.note_id}。\n"
            f"- 在书写总结前必须调用：[TOOL_CALL:note:{read_payload}] 获取最新内容。\n"
            f"- 完成分析后调用：[TOOL_CALL:note:{update_payload}] 同步增量信息。\n"
            "- 更新时保持原有段落结构，新增内容请在对应段落中补充。\n"
            f"- 建议 tags 保持为 {tags_literal}，保证其他 Agent 可快速定位。\n"
            "- 成功同步到笔记后，再输出面向用户的总结。\n"
        )

    # ── 情况二：任务尚未建立笔记 ─────────────────────────────────
    # 构造「创建笔记」的工具调用指令，让 Agent 先建立笔记再进行后续操作
    create_payload = json.dumps(
        {
            "action": "create",
            "task_id": task.id,
            "title": f"任务 {task.id}: {task.title}",
            "note_type": "task_state",
            "tags": tags_list,
            "content": "请记录任务概览、来源概览",
        },
        ensure_ascii=False,
    )

    return (
        "笔记协作指引：\n"
        f"- 当前任务尚未建立笔记，请先调用：[TOOL_CALL:note:{create_payload}]。\n"
        "- 创建成功后记录返回的 note_id，并在后续所有更新中复用。\n"
        "- 同步笔记后，再输出面向用户的总结。\n"
    )

