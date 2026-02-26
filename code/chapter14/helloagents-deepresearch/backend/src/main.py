"""FastAPI entrypoint exposing the DeepResearchAgent via HTTP."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterator, Optional

from dotenv import load_dotenv

# 加载 .env 文件，必须在所有其他 import 之前执行，
# 否则 SearchTool 等模块级对象在 import 时读不到环境变量
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from loguru import logger
from pydantic import BaseModel, Field

from config import Configuration, SearchAPI
from agent import DeepResearchAgent

# 添加控制台日志处理程序
logger.add(
    sys.stderr,
    level="INFO",
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <4}</level> | <cyan>using_function:{function}</cyan> | <cyan>{file}:{line}</cyan> | <level>{message}</level>",
    colorize=True,
)


# 添加错误日志文件处理程序
logger.add(
    sink=sys.stderr,
    level="ERROR",
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <4}</level> | <cyan>using_function:{function}</cyan> | <cyan>{file}:{line}</cyan> | <level>{message}</level>",
    colorize=True,
)


class ResearchRequest(BaseModel):
    """Payload for triggering a research run."""

    topic: str = Field(..., description="Research topic supplied by the user")
    search_api: SearchAPI | None = Field(
        default=None,
        description="Override the default search backend configured via env",
    )


class ResearchResponse(BaseModel):
    """HTTP response containing the generated report and structured tasks."""

    report_markdown: str = Field(
        ..., description="Markdown-formatted research report including sections"
    )
    todo_items: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Structured TODO items with summaries and sources",
    )


def _mask_secret(value: Optional[str], visible: int = 4) -> str:
    """Mask sensitive tokens while keeping leading and trailing characters."""
    if not value:
        return "unset"

    if len(value) <= visible * 2:
        return "*" * len(value)

    return f"{value[:visible]}...{value[-visible:]}"


def _build_config(payload: ResearchRequest) -> Configuration:
    overrides: Dict[str, Any] = {}

    if payload.search_api is not None:
        overrides["search_api"] = payload.search_api

    return Configuration.from_env(overrides=overrides)

#完成了 FastAPI 应用的创建，定义了两个端点：/research 用于同步研究请求，/research/stream 用于流式研究请求。每个端点都使用了一个 Pydantic 模型来验证输入和输出数据结构。应用还添加了 CORS 中间件以允许跨域请求，并在启动时记录当前的配置。
def create_app() -> FastAPI:
    app = FastAPI(title="HelloAgents Deep Researcher")

    # 注册 CORS（跨域资源共享）中间件
    # 前端页面与后端不在同一个域名/端口时，浏览器会拦截请求，CORS 中间件告诉浏览器"允许跨域"
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],       # 允许所有来源域名（生产环境建议改为具体域名）
        allow_credentials=True,    # 允许携带 Cookie / Authorization 请求头
        allow_methods=["*"],       # 允许所有 HTTP 方法（GET、POST、PUT、DELETE 等）
        allow_headers=["*"],       # 允许所有请求头字段
    )

    # 注册启动事件：服务器启动时自动执行一次，用于打印当前生效的配置，方便排查问题
    @app.on_event("startup")
    def log_startup_configuration() -> None:
        # 从环境变量读取当前配置
        config = Configuration.from_env()

        # 不同 LLM 提供商的 base_url 字段名不同，统一提取成 base_url 变量
        if config.llm_provider == "ollama":
            base_url = config.sanitized_ollama_url()   # Ollama 需要脱敏处理 URL
        elif config.llm_provider == "lmstudio":
            base_url = config.lmstudio_base_url
        else:
            base_url = config.llm_base_url or "unset"

        # 将所有关键配置项打印到日志，api_key 脱敏后只显示前后4位
        logger.info(
            "DeepResearch configuration loaded: provider=%s model=%s base_url=%s search_api=%s "
            "max_loops=%s fetch_full_page=%s tool_calling=%s strip_thinking=%s api_key=%s",
            config.llm_provider,
            config.resolved_model() or "unset",
            base_url,
            (config.search_api.value if isinstance(config.search_api, SearchAPI) else config.search_api),
            config.max_web_research_loops,
            config.fetch_full_page,
            config.use_tool_calling,
            config.strip_thinking_tokens,
            _mask_secret(config.llm_api_key),  # 脱敏：abcd...wxyz
        )

    # 健康检查接口：供 Docker/K8s/负载均衡器等外部系统探测服务是否存活
    # 请求：GET /healthz
    # 响应：{"status": "ok"}（HTTP 200）
    # 服务挂掉时无响应，外部系统据此触发重启或流量切换
    @app.get("/healthz")
    def health_check() -> Dict[str, str]:
        return {"status": "ok"}

    @app.post("/research", response_model=ResearchResponse)
    def run_research(payload: ResearchRequest) -> ResearchResponse:
        try:
            config = _build_config(payload)
            agent = DeepResearchAgent(config=config)
            result = agent.run(payload.topic)
        except ValueError as exc:  # Likely due to unsupported configuration
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:  # pragma: no cover - defensive guardrail
            raise HTTPException(status_code=500, detail="Research failed") from exc

        todo_payload = [
            {
                "id": item.id,
                "title": item.title,
                "intent": item.intent,
                "query": item.query,
                "status": item.status,
                "summary": item.summary,
                "sources_summary": item.sources_summary,
                "note_id": item.note_id,
                "note_path": item.note_path,
            }
            for item in result.todo_items
        ]

        return ResearchResponse(
            report_markdown=(result.report_markdown or result.running_summary or ""),
            todo_items=todo_payload,
        )

    @app.post("/research/stream")
    def stream_research(payload: ResearchRequest) -> StreamingResponse:
        try:
            config = _build_config(payload)
            agent = DeepResearchAgent(config=config)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        def event_iterator() -> Iterator[str]:
            try:
                for event in agent.run_stream(payload.topic):
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n" 
            except Exception as exc:  # 把异常对象赋值给变量 exc
                logger.exception("Streaming research failed")
                error_payload = {"type": "error", "detail": str(exc)}
                yield f"data: {json.dumps(error_payload, ensure_ascii=False)}\n\n"

        return StreamingResponse(
            event_iterator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            },
        )

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",    # 去 main.py 文件里找名为 app 的对象
        host="0.0.0.0",  # 监听所有网卡（局域网也能访问），127.0.0.1 只有本机能访问
        port=8000,       # 端口号
        reload=True,     # 开发模式：代码改动后自动重启，生产环境要改成 False
        log_level="info" # 日志级别
    )
