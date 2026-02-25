"""Utility helpers for normalizing agent generated text."""

from __future__ import annotations

import re


def strip_tool_calls(text: str) -> str:
    """移除文本中的工具调用标记。"""

    if not text:
        return text

    pattern = re.compile(r"\[TOOL_CALL:[^\]]+\]")
    return pattern.sub("", text)


def strip_markdown_fences(text: str) -> str:
    """剥除 LLM 返回内容外层多余的 ```markdown ... ``` 代码围栏。"""

    if not text:
        return text

    # 匹配以可选语言标识开头的代码围栏块（如 ```markdown、``` 等）
    pattern = re.compile(r"^```[a-zA-Z]*\n?(.*?)\n?```\s*$", re.DOTALL)
    m = pattern.match(text.strip())
    if m:
        return m.group(1).strip()
    return text


# GLM 系列模型可能在输出中残留的 chat-template 特殊 token
_MODEL_ARTIFACTS = re.compile(
    r"<\|(?:observation|assistant|user|system|endoftext)\|>",
    re.IGNORECASE,
)


def strip_model_artifacts(text: str) -> str:
    """移除模型输出中残留的 chat-template 特殊 token（如 <|observation|>）。"""

    if not text:
        return text
    return _MODEL_ARTIFACTS.sub("", text)


def clean_llm_output(text: str) -> str:
    """一站式清理 LLM 输出：去除工具调用、代码围栏、模型特殊 token。"""

    text = strip_tool_calls(text)
    text = strip_model_artifacts(text)
    text = strip_markdown_fences(text)
    return text.strip()

