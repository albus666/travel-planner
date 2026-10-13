"""Small planning evaluation; checks evidence/constraints, never travel feasibility."""
from datetime import datetime,timedelta,timezone
import argparse,hashlib,json
from pathlib import Path
import urllib.request
import psycopg
from retrieval.search_chunks import require_database_url

ROOT=Path(__file__).resolve().parents[2]


def post(body):
    request=urllib.request.Request('http://127.0.0.1:8100/plan',data=json.dumps(body).encode(),headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(request,timeout=120) as response:return json.load(response)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'rag/eval/reports/luoyang_one_day_v1_run1.json')
    args=parser.parse_args();path=args.output
    if path.exists():raise RuntimeError('Refusing overwrite')
    date=(datetime.now(timezone(timedelta(hours=8)))+timedelta(days=3)).date().isoformat()
    basic={'request':'给我安排洛阳一日游','trip_date':date,'departure':'洛阳站','companions':'两位成人',
        'preferences':['历史文化'],'pace':'适中','transport':'公共交通'}
    cases=[('01_missing',{'request':'给我安排洛阳一日游'},'needs_clarification'),
        ('02_history',basic,'draft'),
        ('03_natural',{'request':'明天从洛阳站出发，带爸妈，喜欢历史文化，慢节奏，打车去洛阳一日游'},'draft'),
        ('04_required_avoid',{**basic,'companions':'两位老人','pace':'轻松','must_visit':['龙门石窟'],'avoid':['洛阳博物馆']},'draft'),
        ('05_walking',{**basic,'departure':'洛阳博物馆','preferences':['博物馆'],'transport':'步行'},'draft'),
        ('06_unknown',{**basic,'must_visit':['龙门']},'needs_clarification'),
        ('07_conflict',{**basic,'must_visit':['龙门石窟'],'avoid':['龙门石窟']},'needs_clarification'),
        ('08_scope',{**basic,'city':'北京'},'needs_clarification'),
        ('09_avoid_alias',{**basic,'avoid':['龙门']},'needs_clarification')]
    report={'origin':'synthetic integration cases','cases':[],'human_review':'pending','run_complete':False}
    def save():
        path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        lines=[f"# 洛阳一日游最小规划：{len(cases)}题待评报告",'',
            '这里只验证采集条件、草案约束与资料引用，不验证地理顺序或一天内可行性。新答案人工评分为空。','']
        for c in report['cases']:
            lines += ['## '+c['id'],'','请求：','```json',json.dumps(c['request'],ensure_ascii=False,indent=2),'```','','响应：','```json',json.dumps(c['response'],ensure_ascii=False,indent=2),'```','','人工检查：条件收集 __；约束 __；引用支持 __；缺资料 __；无虚构耗时 __；备注 __','']
        path.with_suffix('.md').write_text('\n'.join(lines),encoding='utf-8')
    with psycopg.connect(require_database_url(),options='-c default_transaction_read_only=on') as conn:
        for cid,body,expected in cases:
            r=post(body);report['cases'].append({'id':cid,'request':body,'response':r,'human_review':None});save()
            assert r['status']==expected,(cid,r)
            if cid=='01_missing':assert len(r['questions'])==6 and all(t['state']=='not_queried' for t in r['tasks'])
            if r['status']=='draft':
                assert 0<len(r['stops'])<=r['constraints']['max_stops']
                assert len({s['poi_id'] for s in r['stops']})==len(r['stops'])
                assert not set(s['name'] for s in r['stops'])&set(body.get('avoid',[]))
                assert set(body.get('must_visit',[]))<=set(s['name'] for s in r['stops'])
                for stop in r['stops']:
                    assert stop['arrival_time'] is None and stop['visit_duration_minutes'] is None
                    assert stop['citations']
                    for c in stop['citations']:
                        actual=conn.execute('SELECT poi_id,text FROM v2.rag_chunks WHERE chunk_id=%s',(c['chunk_id'],)).fetchone()
                        assert actual[0]==stop['poi_id'] and all(q in actual[1] for q in c['quotes'])
                        assert c['collected_at']
                assert all(l['travel_minutes'] is None and l['state']=='not_queried' for l in r['legs'])
            if cid=='05_walking':assert len(r['stops'])==1 and r['stops'][0]['name']=='洛阳博物馆'
            print(json.dumps({'id':cid,'status':r['status'],'stops':[s['name'] for s in r['stops']]},ensure_ascii=False),flush=True)
    report.update(run_complete=True,summary={'cases_checked':len(cases),'constraints_quotes_and_no_timetable_checks':'passed',
        'human_review':'pending','travel_feasibility':'not_verified','no_map_or_weather_api':True})
    report['source_hashes']={'rag/service/plan_service.py':hashlib.sha256((ROOT/'rag/service/plan_service.py').read_bytes()).hexdigest()}
    save();print(json.dumps(report['summary'],ensure_ascii=False))


if __name__=='__main__':main()
