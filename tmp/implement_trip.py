from pathlib import Path
p=Path('rag/service/retrieval_server.py');s=p.read_text(encoding='utf-8');s += '''

from service.trip_service import RepairRequest, TripRequest, repair_route, plan_trip_days

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
''';p.write_text(s,encoding='utf-8')
p=Path('rag/client/run_on_server.ps1');s=p.read_text(encoding='utf-8').replace('(Join-Path $RagRoot "service\\route_plan.py") `','(Join-Path $RagRoot "service\\route_plan.py") `\n      (Join-Path $RagRoot "service\\map_budget.py") `\n      (Join-Path $RagRoot "service\\trip_service.py") `');p.write_text(s,encoding='utf-8')
