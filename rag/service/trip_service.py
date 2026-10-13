"""Bounded constraint repair and consecutive multi-day evidence itineraries."""
from datetime import timedelta
from pydantic import Field, model_validator
from service.baidu_maps import Strict, BaiduMaps
from service.route_plan import RoutePlanRequest, plan_with_routes, poi_points
from service.plan_service import plan_trip


class RepairRequest(Strict):
    route: RoutePlanRequest
    max_replans: int = Field(3,ge=0,le=3)


class TripRequest(Strict):
    days: list[RoutePlanRequest] = Field(min_length=1,max_length=7)
    max_replans_per_day: int = Field(3,ge=0,le=3)

    @model_validator(mode='after')
    def dates(self):
        dates=[d.plan.trip_date for d in self.days]
        if any(d is None for d in dates):raise ValueError('each day requires an explicit trip_date')
        if any(b!=a+timedelta(days=1) for a,b in zip(dates,dates[1:])):raise ValueError('dates must be consecutive and increasing')
        if any(d.plan.days!=1 or d.plan.city!='洛阳' for d in self.days):raise ValueError('each daily plan must be Luoyang one day')
        required=[name for d in self.days for name in d.plan.must_visit]
        if len(required)!=len(set(required)):raise ValueError('a required POI cannot be assigned to multiple days')
        for a,b in zip(self.days,self.days[1:]):
            if (a.end_point.lat,a.end_point.lng,a.end_point.coord_type)!=(b.departure_point.lat,b.departure_point.lng,b.departure_point.coord_type):
                raise ValueError('overnight endpoint must match next departure; unplanned overnight transfers are unsupported')
        return self


def repair_route(body, max_replans=3, *, draft_tool=plan_trip, points_tool=poi_points, maps=None):
    maps=maps or BaiduMaps()
    draft=draft_tool(body.plan)
    # Freeze the selected evidence. Do not let a fresh recommendation refill removed stops.
    required=set(body.plan.must_visit)|set((draft.get('constraints') or {}).get('must_visit',[]))
    history=[]; removed=[]
    for attempt in range(max_replans+1):
        result=plan_with_routes(body,draft_tool=lambda _:draft,points_tool=points_tool,maps=maps)
        history.append({'attempt':attempt,'action':'initial' if attempt==0 else 'remove_optional_and_recheck',
                        'removed':list(removed),'status':result['status'],'time_check':result['time_check'],
                        'excess_minutes':result.get('excess_minutes'),'legs':result['legs']})
        if result['status']!='constraint_conflict' or attempt==max_replans:break
        optional=[s for s in draft['stops'] if s['name'] not in required]
        if not optional or len(draft['stops'])<=1:break
        name=optional[-1]['name'];removed.append(name)
        kept=[s for s in draft['stops'] if s['name']!=name]
        draft={**draft,'stops':kept,'legs':[],
               'citations':[c for s in kept for c in s.get('citations',[])]}
    result.update(workflow='bounded_replan_v1',replan_trace=history,removed_optional=removed,
                  replan_count=len(history)-1,repair_scope='remove optional stops only; required stops, visit durations and deadline preserved')
    return result


def plan_trip_days(body, *, draft_tool=plan_trip, points_tool=poi_points, maps=None):
    maps=maps or BaiduMaps();days=[];visited=set()
    for index,day in enumerate(body.days):
        future={n for d in body.days[index+1:] for n in d.plan.must_visit}
        avoid=set(day.plan.avoid)|visited|future
        daily=day.model_copy(update={'plan':day.plan.model_copy(update={'avoid':sorted(avoid)})})
        result=repair_route(daily,body.max_replans_per_day,draft_tool=draft_tool,points_tool=points_tool,maps=maps)
        days.append({'day':index+1,'date':day.plan.trip_date.isoformat(),'result':result})
        visited.update(s['name'] for s in result.get('schedule',[]))
        if result['status']!='time_checked_draft':break
    complete=len(days)==len(body.days) and all(d['result']['status']=='time_checked_draft' for d in days)
    return {'workflow':'multi_day_v1','status':'time_checked_draft' if complete else days[-1]['result']['status'],
            'days':days,'requested_days':len(body.days),'unplanned_days':list(range(len(days)+1,len(body.days)+1)),
            'warnings':['仅验证各日时间预算；开放、预约、酒店、预算、体力和未来交通仍未核实。',
                        '沿用七景点候选池；后续日期必去景点预留，已安排景点不重复。失败后停止后续日程。']}
