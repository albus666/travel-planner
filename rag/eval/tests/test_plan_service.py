from datetime import date
import os
import unittest
from unittest.mock import MagicMock,patch
from fastapi.testclient import TestClient
from service.plan_service import PlanRequest,collect,create_plan_graph,read_catalog,CATALOG_SQL,POOL
from service import retrieval_server as server

TODAY=date(2026,10,13)
def request(**kw):
    return PlanRequest(trip_date=date(2026,11,1),departure='洛阳站',companions='两位成人',
        preferences=['历史文化'],pace='适中',transport='公共交通',**kw).model_dump(mode='json')
def catalog():return [{'poi_id':1,'name':'龙门石窟','city':'洛阳'},{'poi_id':2,'name':'天子驾六博物馆','city':'洛阳'},{'poi_id':3,'name':'王城公园','city':'洛阳'}]
def hits(q,**kw):
    name=next(n for n in POOL if n in q);poi=next(p['poi_id'] for p in catalog() if p['name']==name)
    return [{'chunk_id':f'c{poi}','poi_id':poi,'name':name,'theme':'overview','theme_label':'介绍',
             'text':f'【{name}】\n这里有历史文化与古代遗址的介绍。','similarity':.8}]
def sources(rows):return [{**r,'source_id':f'S{i}','source_url':'https://example.com/data',
    'collected_at':'2026-10-11T20:00:00+08:00','verify_status':'unverified'} for i,r in enumerate(rows,1)]

class PlanningTests(unittest.TestCase):
    def run_plan(self,payload,cat=None,retrieve=None):
        c=MagicMock(side_effect=cat or catalog);r=MagicMock(side_effect=retrieve or hits)
        out=create_plan_graph(c,r,sources,today=TODAY).invoke({'payload':payload})['result']
        return out,c,r

    def test_missing_material_slots_asks_before_query(self):
        out,c,r=self.run_plan(PlanRequest().model_dump(mode='json'))
        self.assertEqual(out['status'],'needs_clarification');self.assertEqual(len(out['questions']),6)
        c.assert_not_called();r.assert_not_called()
        self.assertTrue(all(t['state']=='not_queried' for t in out['tasks']))

    def test_common_natural_slots_without_llm(self):
        p=PlanRequest(request='明天从洛阳站出发，带爸妈，喜欢历史文化，慢节奏，打车去洛阳一日游').model_dump(mode='json')
        slots,questions=collect(p,TODAY)
        self.assertFalse(questions);self.assertEqual(slots['trip_date'],'2026-10-14')
        self.assertEqual(slots['departure'],'洛阳站');self.assertEqual(slots['pace'],'轻松');self.assertEqual(slots['transport'],'出租车')

    def test_draft_has_unique_real_pois_and_literal_citations(self):
        out,_,r=self.run_plan(request())
        self.assertEqual(out['status'],'draft');self.assertEqual(len(out['stops']),3)
        self.assertEqual(len({s['poi_id'] for s in out['stops']}),3)
        for stop in out['stops']:
            self.assertIsNone(stop['arrival_time']);self.assertIsNone(stop['visit_duration_minutes'])
            self.assertIn('历史文化',stop['selection_basis'])
            self.assertTrue(stop['citations'][0]['collected_at'])
        self.assertTrue(all(l['travel_minutes'] is None and l['state']=='not_queried' for l in out['legs']))
        self.assertIn('未核实',''.join(out['warnings']))

    def test_relaxed_and_walking_stop_caps(self):
        for field,value,count in (('pace','轻松',2),('transport','步行',1)):
            p=request();p[field]=value;out,_,_=self.run_plan(p)
            self.assertEqual(len(out['stops']),count)
        p=request();p.update(transport='步行',departure='天子驾六博物馆')
        out,_,_=self.run_plan(p);self.assertEqual(out['stops'][0]['name'],'天子驾六博物馆')

    def test_required_and_avoid_constraints(self):
        out,_,_=self.run_plan(request(must_visit=['天子驾六博物馆'],avoid=['龙门石窟']))
        self.assertEqual(out['stops'][0]['name'],'天子驾六博物馆')
        self.assertNotIn('龙门石窟',[s['name'] for s in out['stops']])

    def test_natural_exact_required_and_avoid(self):
        p=request();p['request']='洛阳一日游，必去天子驾六博物馆，不去龙门石窟'
        out,_,_=self.run_plan(p)
        self.assertEqual(out['stops'][0]['name'],'天子驾六博物馆');self.assertNotIn('龙门石窟',[s['name'] for s in out['stops']])

    def test_conflicting_or_excess_required_pois_ask(self):
        for p in (request(must_visit=['龙门石窟'],avoid=['龙门石窟']),request(must_visit=['龙门石窟','天子驾六博物馆'])):
            p['transport']='步行';out,_,r=self.run_plan(p)
            self.assertEqual(out['status'],'needs_clarification');r.assert_not_called()
            self.assertEqual(out['tasks'][0]['state'],'queried_with_evidence')
            self.assertEqual(out['tasks'][1]['state'],'not_queried')

    def test_unknown_required_no_similar_entity_substitution(self):
        out,_,_=self.run_plan(request(must_visit=['龙门']))
        self.assertEqual(out['status'],'needs_clarification');self.assertEqual(out['stops'],[])
        self.assertIn('不能替换成相似景点',out['questions'][0]['question'])
        out,_,r=self.run_plan(request(avoid=['龙门']))
        self.assertEqual(out['status'],'needs_clarification');r.assert_not_called()
        self.assertIn('不会自动展开简称',out['questions'][0]['question'])

    def test_other_poi_hits_never_support_recommendation(self):
        def bad(q,**kw):return [{**hits(q)[0],'poi_id':99,'name':'外地景点'}]
        out,_,_=self.run_plan(request(),retrieve=bad)
        self.assertEqual(out['status'],'insufficient_evidence');self.assertEqual(out['citations'],[])

    def test_no_preference_evidence_no_invented_recommendation(self):
        def unrelated(q,**kw):return [{**hits(q)[0],'text':'这里有温泉淋浴设施可供使用。'}]
        out,_,_=self.run_plan(request(),retrieve=unrelated)
        self.assertEqual(out['status'],'insufficient_evidence');self.assertEqual(out['stops'],[])

    def test_partial_tool_failure_preserves_other_evidence(self):
        def some(q,**kw):
            if '龙门石窟' in q:raise RuntimeError('secret connection')
            return hits(q,**kw)
        out,_,_=self.run_plan(request(),retrieve=some)
        self.assertEqual(out['status'],'draft');self.assertEqual(len(out['stops']),2)
        self.assertNotIn('secret connection',str(out));self.assertIn('query_failed',[t['state'] for t in out['tasks']])

    def test_missing_required_evidence_prevents_full_constraint_claim(self):
        out,_,_=self.run_plan(request(must_visit=['龙门石窟']),retrieve=lambda q,**kw:[])
        self.assertEqual(out['status'],'insufficient_evidence');self.assertFalse(out['stops'])
        out,_,_=self.run_plan(request(),cat=lambda:[])
        self.assertIn('未返回记录',''.join(out['limitations']))
        out,_,_=self.run_plan(request(avoid=list(POOL)))
        self.assertIn('筛掉',''.join(out['limitations']))

    def test_scope_past_date_and_ambiguous_departure(self):
        for change in ({'city':'北京'},{'days':2},{'trip_date':'2026-10-12'},{'departure':'酒店'},{'departure':'   '},{'companions':'  '},{'request':'洛阳一日游，预算100元以内'},{'companions':'轮椅使用者'}):
            p=request();p.update(change);out,c,r=self.run_plan(p)
            self.assertEqual(out['status'],'needs_clarification');c.assert_not_called();r.assert_not_called()
        with self.assertRaises(ValueError):PlanRequest(budget=100)

    def test_senior_party_no_accessibility_guarantee(self):
        p=request();p['companions']='两位老人';out,_,_=self.run_plan(p)
        self.assertIn('不能保证适合老人',''.join(out['warnings']))

    def test_catalog_uses_fixed_readonly_query(self):
        conn=MagicMock();conn.execute.return_value.fetchall.return_value=[]
        with patch('service.plan_service.require_database_url',return_value='private'),patch('service.plan_service.psycopg.connect') as connect:
            connect.return_value.__enter__.return_value=conn;self.assertEqual(read_catalog(),[])
            self.assertIn('default_transaction_read_only=on',connect.call_args.kwargs['options'])
            conn.execute.assert_called_once_with(CATALOG_SQL,('洛阳',list(POOL)))

    def test_endpoint_independent_flag(self):
        with patch.dict(os.environ,{'RAG_PLANNING_ENABLED':'0'}):
            self.assertEqual(TestClient(server.app).post('/plan',json={}).status_code,404)
        with patch.dict(os.environ,{'RAG_PLANNING_ENABLED':'1'}),patch.object(server,'_MODEL_READY',True),patch.object(server,'plan_trip',return_value={'status':'needs_clarification'}) as plan:
            self.assertEqual(TestClient(server.app).post('/plan',json={}).status_code,200);plan.assert_called_once()


if __name__=='__main__':unittest.main()
