"""Add queried travel estimates to existing evidence drafts without changing plan_v1."""
from datetime import datetime, time, timedelta
from itertools import permutations
from typing import Literal

from pydantic import Field, field_validator, model_validator
from service.baidu_maps import Strict, Point, BaiduMaps, CN
from service.plan_service import PlanRequest, plan_trip


class RoutePlanRequest(Strict):
    plan: PlanRequest
    departure_point: Point
    end_point: Point
    start_time: str=Field(pattern=r'^([01]\d|2[0-3]):[0-5]\d$')
    end_time: str=Field(pattern=r'^([01]\d|2[0-3]):[0-5]\d$')
    mode: Literal['driving','walking','riding','transit']='driving'
    visit_minutes: dict[str,int]
    buffer_minutes_per_leg: int=Field(10,ge=0,le=120)
    optimize_order: bool=False

    @field_validator('visit_minutes')
    @classmethod
    def durations(cls,v):
        if any(isinstance(n,bool) or not 1<=n<=720 for n in v.values()):raise ValueError('visit_minutes must be 1..720')
        return v

    @model_validator(mode='after')
    def validate_window(self):
        if self.end_time<=self.start_time:raise ValueError('same-day end_time must be after start_time')
        if self.departure_point.coord_type!='bd09ll' or self.end_point.coord_type!='bd09ll':raise ValueError('planning points must explicitly use bd09ll')
        expected={'自驾':'driving','出租车':'driving','步行':'walking','公共交通':'transit'}
        if self.plan.transport not in expected or expected[self.plan.transport]!=self.mode:
            raise ValueError('mode must match the explicit plan.transport; riding is available in /maps/query only')
        return self


def poi_points(ids):
    import psycopg
    from retrieval.search_chunks import require_database_url
    with psycopg.connect(require_database_url(),options='-c default_transaction_read_only=on -c statement_timeout=5000') as conn:
        rows=conn.execute('SELECT poi_id,name,latitude,longitude,coordinate_type FROM v2.attractions WHERE poi_id=ANY(%s)',(ids,)).fetchall()
    result={}
    for pid,name,lat,lng,kind in rows:
        if lat is not None and lng is not None and str(kind).lower() in ('bd09','bd09ll'):
            result[pid]=Point(lat=float(lat),lng=float(lng),name=name)
    return result


def plan_with_routes(body, *, draft_tool=plan_trip, points_tool=poi_points, maps=None):
    draft=draft_tool(body.plan)
    result={'workflow':'route_plan_v1','draft':draft,'status':draft['status'],'schedule':[],
        'legs':[],'time_check':'not_checked','issues':[], 'warnings':[
            '仅校验交通估算、用户游览时长和缓冲是否落在时间窗口内，不保证开放、预约、体力或预算满足。',
            '当前查询的路况估算不是未来日期的交通预测；景点坐标可能是中心点，出入口待核实。']}
    if draft['status']!='draft':return result
    stops=draft['stops']
    missing=[s['name'] for s in stops if s['name'] not in body.visit_minutes]
    if missing:
        result.update(status='needs_clarification',issues=['请提供各站游览分钟数：'+'、'.join(missing)])
        return result
    try:points=points_tool([s['poi_id'] for s in stops])
    except Exception:
        result.update(status='partial',issues=['景点坐标查询失败'],time_check='unknown');return result
    missing=[s['name'] for s in stops if s['poi_id'] not in points]
    if missing:
        result.update(status='needs_clarification',issues=['缺少已标注BD09坐标：'+'、'.join(missing)]);return result
    maps=maps or BaiduMaps();ordered=list(stops)
    if body.optimize_order:
        if body.mode=='transit':
            result.update(status='needs_clarification',issues=['公交矩阵未接入，请关闭 optimize_order。']);return result
        all_points=[body.departure_point]+[points[s['poi_id']] for s in stops]+[body.end_point]
        matrix=maps.query('matrix',{'origins':[p.model_dump() for p in all_points],
            'destinations':[p.model_dump() for p in all_points],'mode':body.mode})
        result['matrix']=matrix
        pairs={(p['origin_index'],p['destination_index']):p['duration_seconds'] for p in matrix.get('pairs',[]) if p['state']=='queried_with_evidence'}
        choices=[]
        for order in permutations(range(1,len(stops)+1)):
            path=(0,)+order+(len(all_points)-1,)
            if all((a,b) in pairs for a,b in zip(path,path[1:])):
                choices.append((sum(pairs[a,b] for a,b in zip(path,path[1:])),order))
        if not choices:
            result.update(status='partial',time_check='unknown',issues=['矩阵未提供完整可用路线，未猜测顺序或耗时。']);return result
        _,order=min(choices);ordered=[stops[i-1] for i in order]
        result['order_scope']='best complete order among selected stops under this sampled matrix; not global optimal itinerary'
    endpoints=[body.departure_point]+[points[s['poi_id']] for s in ordered]+[body.end_point]
    trip_date=draft['slots']['trip_date']
    cursor=datetime.combine(datetime.fromisoformat(str(trip_date)).date(),time.fromisoformat(body.start_time),tzinfo=CN)
    deadline=datetime.combine(cursor.date(),time.fromisoformat(body.end_time),tzinfo=CN)
    complete=True
    for i,(origin,destination) in enumerate(zip(endpoints,endpoints[1:])):
        route=maps.query('route',{'origin':origin.model_dump(),'destination':destination.model_dump(),'mode':body.mode})
        leg={'from':origin.name,'to':destination.name,'route':route,'travel_minutes':None,'arrival_time':None}
        if route['state']=='queried_with_evidence' and route.get('routes'):
            seconds=route['routes'][0]['duration_seconds'];leg['travel_minutes']=round(seconds/60,2)
            if complete:
                cursor+=timedelta(seconds=seconds,minutes=body.buffer_minutes_per_leg);leg['arrival_time']=cursor.isoformat()
        else:complete=False
        result['legs'].append(leg)
        if i<len(ordered):
            stop=ordered[i];minutes=body.visit_minutes[stop['name']]
            result['schedule'].append({**stop,'order':i+1,'arrival_time':cursor.isoformat() if complete else None,
                'visit_duration_minutes':minutes,'duration_source':'user_input',
                'departure_time':(cursor+timedelta(minutes=minutes)).isoformat() if complete else None,
                'sequence_status':'map_estimate_unverified_opening'})
            if complete:cursor+=timedelta(minutes=minutes)
    result['estimated_finish_time']=cursor.isoformat() if complete else None
    result['time_check']='unknown' if not complete else 'within_window' if cursor<=deadline else 'exceeds_window'
    result['status']='partial' if not complete else 'time_checked_draft' if cursor<=deadline else 'constraint_conflict'
    result['buffer_minutes_per_leg']=body.buffer_minutes_per_leg
    if complete and cursor>deadline:
        result['excess_minutes']=round((cursor-deadline).total_seconds()/60,2)
        result['issues'].append('按本次交通估算超出结束时间；请缩短游览、减少非必去景点或延后结束，不自动删除必去。')
    return result
