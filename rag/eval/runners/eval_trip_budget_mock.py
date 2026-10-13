"""Deterministic integration evidence; no provider or LLM network calls."""
import json
from pathlib import Path
from datetime import timedelta
from eval.tests.test_baidu_maps import body,draft,points,P
from eval.tests.test_trip_budget import fake_maps
from service.trip_service import repair_route,plan_trip_days,TripRequest


def main():
    cases=[]
    for name,required,route in [('optional_repair',['景点A'],body(end_time='10:40')),
                                ('required_conflict',['景点A','景点B'],body(end_time='09:30'))]:
        route.plan.must_visit=required
        cases.append({'id':name,'result':repair_route(route,draft_tool=draft,points_tool=points,maps=fake_maps())})
    api=fake_maps();api.query.return_value={'state':'not_queried','reason':'daily_budget_exhausted'}
    cases.append({'id':'budget_exhausted','result':repair_route(body(),draft_tool=draft,points_tool=points,maps=api)})
    a=body(end_point=P);b=body(end_point=P);b.plan.trip_date=a.plan.trip_date+timedelta(days=1);b.plan.must_visit=['景点B']
    def choose(p):
        d=draft(p);d['slots']['trip_date']=p.trip_date.isoformat()
        d['stops']=[s for s in d['stops'] if s['name'] not in p.avoid];return d
    cases.append({'id':'two_days','result':plan_trip_days(TripRequest(days=[a,b]),draft_tool=choose,points_tool=points,maps=fake_maps())})
    out={'dataset_origin':'synthetic_mock_not_live_or_human_review','new_baidu_calls':0,'human_review':None,'cases':cases}
    path=Path(__file__).resolve().parents[1]/'reports/trip_budget_v1_mock.json'
    path.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({c['id']:c['result']['status'] for c in cases}))


if __name__=='__main__':main()
