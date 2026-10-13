"""常驻检索服务：进程启动时加载一次 BGE-M3，之后重复响应查询。

绑定本机 ``127.0.0.1``（默认端口 8100），不对外网暴露。
本机可通过 SSH 转发或 ``run_on_server.ps1`` 调用。

启动（在服务器 travel-planner 目录）::

    bash rag/service/start_retrieval_server.sh

健康检查::

    curl -s http://127.0.0.1:8100/health

检索::

    curl -s http://127.0.0.1:8100/search \\
      -H 'Content-Type: application/json; charset=utf-8' \\
      -d '{"question":"龙门石窟的游览路线是什么？","top_k":3}'
"""

from __future__ import annotations

import time
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from retrieval.search_chunks import load_env_files, load_model, search
from service.answer_service import AnswerUnavailable, answer_question

_MODEL_READY = False
_LOADED_AT: float | None = None


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """应用生命周期：启动时预热模型，关闭时无额外清理。"""
    global _MODEL_READY, _LOADED_AT
    load_env_files()
    t0 = time.time()
    print("Warming up BGE-M3 (once)...", flush=True)
    load_model()
    _LOADED_AT = time.time()
    _MODEL_READY = True
    print(f"BGE-M3 ready in {_LOADED_AT - t0:.1f}s", flush=True)
    yield
    _MODEL_READY = False


app = FastAPI(
    title="Luoyang RAG retrieval",
    description="BGE-M3 + pgvector retrieval and evidence-grounded answers",
    lifespan=lifespan,
)


class SearchRequest(BaseModel):
    """检索请求体。"""

    question: str = Field(..., min_length=1, description="用户问题原文")
    top_k: int = Field(3, ge=1, le=20, description="返回条数")


class SearchHit(BaseModel):
    """单条检索结果（便于 OpenAPI 文档；实际字段与 search() 一致）。"""

    chunk_id: str
    poi_id: int
    name: str
    theme: str
    theme_label: str | None = None
    text: str
    similarity: float


class SearchResponse(BaseModel):
    question: str
    top_k: int
    hits: list[dict[str, Any]]
    elapsed_ms: float


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    top_k: int = Field(5, ge=1, le=10)


class AskResponse(BaseModel):
    question: str
    top_k: int
    status: str
    answer: str
    citations: list[dict[str, Any]]
    warnings: list[str]
    retrieved_sources: list[dict[str, Any]]
    elapsed_ms: float


@app.post("/ask", response_model=AskResponse)
def ask_api(body: AskRequest) -> AskResponse:
    if not _MODEL_READY:
        raise HTTPException(status_code=503, detail="model not ready")
    question = body.question.strip()
    if not question:
        raise HTTPException(status_code=422, detail="question must not be blank")
    t0 = time.time()
    try:
        hits = search(question, top_k=body.top_k)
        result = answer_question(question, hits)
    except AnswerUnavailable as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from None
    except Exception:
        raise HTTPException(status_code=500, detail="回答链路暂不可用。") from None
    return AskResponse(question=question, top_k=body.top_k, **result,
                       elapsed_ms=round((time.time() - t0) * 1000, 1))


@app.get("/health")
def health() -> dict[str, Any]:
    """探活：模型是否已加载。

    Returns:
        dict: ``ok``、``model_ready``、``loaded_at``（unix 时间戳，未加载则为 null）。
    """
    return {
        "ok": True,
        "model_ready": _MODEL_READY,
        "loaded_at": _LOADED_AT,
    }


@app.post("/search", response_model=SearchResponse)
def search_api(body: SearchRequest) -> SearchResponse:
    """对问题做向量检索（复用进程内已加载的 BGE-M3）。

    Args:
        body: 含 ``question``、``top_k`` 的 JSON 请求体。

    Returns:
        SearchResponse: 问题原文、命中列表与耗时（毫秒）。

    Raises:
        HTTPException: 模型尚未就绪（503）或检索失败（500）。
    """
    if not _MODEL_READY:
        raise HTTPException(status_code=503, detail="model not ready")
    t0 = time.time()
    try:
        hits = search(body.question, top_k=body.top_k)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    # Decimal 等类型转成可 JSON 序列化的值
    serializable: list[dict[str, Any]] = []
    for h in hits:
        row = dict(h)
        if "similarity" in row:
            row["similarity"] = float(row["similarity"])
        serializable.append(row)
    return SearchResponse(
        question=body.question,
        top_k=body.top_k,
        hits=serializable,
        elapsed_ms=round((time.time() - t0) * 1000, 1),
    )
