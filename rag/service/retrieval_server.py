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
from pydantic import BaseModel, Field, model_serializer

from retrieval.search_chunks import load_env_files, load_model, search
from service.answer_service import AnswerUnavailable, answer_question
from service.ticket_service import try_ticket_answer
from service.semantic_router import semantic_enabled, load_router, classify_for_request
from service.mixed_service import mixed_enabled, build_mixed_plan, execute_mixed
from service.ask_graph import langgraph_enabled
from service.plan_service import PlanRequest, planning_enabled, plan_trip
from service.travel_agent import AgentRequest, enabled as travel_agent_enabled, run_travel_agent
from service.baidu_maps import MapRequest, BaiduMaps, maps_enabled
from service.route_plan import RoutePlanRequest, plan_with_routes
from pydantic import ValidationError

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
    if semantic_enabled():
        load_router()
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
    route: str = "vector"
    structured_data: dict[str, Any] | None = None
    required_stores: list[str] = Field(default_factory=list)
    tasks: list[dict[str, Any]] = Field(default_factory=list)
    entity_resolution: dict[str, Any] | None = None
    workflow: str | None = None
    node_trace: list[str] = Field(default_factory=list)
    tool_results: dict[str, Any] = Field(default_factory=dict)

    @model_serializer(mode='wrap')
    def serialize(self, handler):
        data = handler(self)
        if self.workflow is None:
            for key in ('workflow', 'node_trace', 'tool_results'):
                data.pop(key, None)
        return data


@app.post("/ask", response_model=AskResponse)
def ask_api(body: AskRequest) -> AskResponse:
    if not _MODEL_READY:
        raise HTTPException(status_code=503, detail="model not ready")
    question = body.question.strip()
    if not question:
        raise HTTPException(status_code=422, detail="question must not be blank")
    t0 = time.time()
    try:
        if langgraph_enabled():
            from service.ask_graph import run_graph
            result = run_graph(question, body.top_k, ticket_tool=try_ticket_answer,
                search_tool=search, answer_tool=answer_question)
            return AskResponse(question=question, top_k=body.top_k, **result,
                elapsed_ms=round((time.time()-t0)*1000,1))
        plan = build_mixed_plan(question) if mixed_enabled() else None
        if plan is not None:
            result = execute_mixed(question, plan, body.top_k, ticket_tool=try_ticket_answer,
                search_tool=search, answer_tool=answer_question)
            return AskResponse(question=question, top_k=body.top_k, **result,
                elapsed_ms=round((time.time()-t0)*1000,1))
        query_vector = None
        if semantic_enabled():
            intent, query_vector = classify_for_request(question)
            result = try_ticket_answer(question, intent=intent)
        else:
            result = try_ticket_answer(question)
        if result is None:
            if query_vector is None:
                hits = search(question, top_k=body.top_k)
            else:
                hits = search(question, top_k=body.top_k, query_vector=query_vector)
            result = answer_question(question, hits)
        result['required_stores'] = ['ticket_sql'] if result.get('route')=='sql_ticket' else ['rag']
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


@app.post('/plan')
def plan_api(body: PlanRequest):
    if not planning_enabled():
        raise HTTPException(status_code=404,detail='planning disabled')
    if not _MODEL_READY:
        raise HTTPException(status_code=503,detail='model not ready')
    return plan_trip(body)


@app.post('/agent/ask')
def travel_agent_api(body: AgentRequest):
    if not travel_agent_enabled():
        raise HTTPException(status_code=404, detail='travel agent disabled')
    if not _MODEL_READY:
        raise HTTPException(status_code=503, detail='model not ready')
    try:
        return run_travel_agent(body)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    except Exception:
        raise HTTPException(status_code=502, detail='travel agent temporarily unavailable') from None


@app.post('/maps/query')
def maps_api(body: MapRequest):
    if not maps_enabled():raise HTTPException(status_code=404,detail='maps disabled')
    try:return BaiduMaps().query(body.action,body.arguments)
    except ValidationError as exc:
        raise HTTPException(status_code=422,detail=exc.errors(include_context=False,include_input=False)) from None


@app.post('/plan/with-routes')
def route_plan_api(body: RoutePlanRequest):
    if not maps_enabled():raise HTTPException(status_code=404,detail='maps disabled')
    if not _MODEL_READY:raise HTTPException(status_code=503,detail='model not ready')
    try:return plan_with_routes(body)
    except Exception:raise HTTPException(status_code=502,detail='route planning temporarily unavailable') from None


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


from service.trip_service import RepairRequest, TripRequest, repair_route, plan_trip_days
from service.plan_chat import ChatRequest, chat_enabled, chat

# Local, same-origin test UI; retains the existing private bind and /docs Swagger UI.
from pathlib import Path
from fastapi.staticfiles import StaticFiles
app.mount('/ui', StaticFiles(directory=Path(__file__).parent / 'web', html=True), name='test-ui')

@app.get('/maps/usage')
def map_usage_api():
    if not maps_enabled():raise HTTPException(status_code=404,detail='maps disabled')
    from service.map_budget import MapBudget
    return MapBudget().status()

@app.post('/plan/replan')
def replan_api(body: RepairRequest):
    if not maps_enabled():raise HTTPException(status_code=404,detail='maps disabled')
    if not _MODEL_READY:raise HTTPException(status_code=503,detail='model not ready')
    try:return repair_route(body.route, body.max_replans)
    except Exception:raise HTTPException(status_code=502,detail='replanning temporarily unavailable') from None

@app.post('/plan/multi-day')
def multi_day_api(body: TripRequest):
    if not maps_enabled():raise HTTPException(status_code=404,detail='maps disabled')
    if not _MODEL_READY:raise HTTPException(status_code=503,detail='model not ready')
    try:return plan_trip_days(body)
    except Exception:raise HTTPException(status_code=502,detail='multi-day planning temporarily unavailable') from None

@app.post('/plan/chat')
def plan_chat_api(body: ChatRequest):
    if not chat_enabled():raise HTTPException(status_code=404,detail='plan chat disabled')
    if not maps_enabled():raise HTTPException(status_code=404,detail='maps disabled')
    if not _MODEL_READY:raise HTTPException(status_code=503,detail='model not ready')
    try:return chat(body)
    except Exception:raise HTTPException(status_code=502,detail='plan chat temporarily unavailable') from None
