import json
import os
import unittest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from service.travel_agent import AgentRequest, TravelContext, run_travel_agent
from service.travel_online import OnlineTravel, CN

CAT=[{'poi_id':1,'name':'龙门石窟','district':'洛阳'},{'poi_id':2,'name':'龙门海洋馆','district':'洛阳'}]


class ScriptModel:
    def __init__(self, replies):self.replies=iter(replies)
    def query(self,messages,tools=None):return next(self.replies)


def call(name,args):
    return {'tool_calls':[{'id':'c1','name':name,'arguments':args}]}


class TravelTests(unittest.TestCase):
    def test_alias_clarification_never_calls_comments(self):
        online=Mock()
        result=run_travel_agent(AgentRequest(question='龙门的评价怎么样'),catalog=CAT,online=online,model=ScriptModel([
            call('search_pois',{'keyword':'龙门'}),call('poi_comments',{'poi_id':1}),{'content':'{"citations":[]}'}]))
        self.assertEqual(result['status'],'needs_clarification');online.comments.assert_not_called()
        self.assertEqual(len(result['candidates']),2)

    def test_grounded_comment_and_timestamp(self):
        online=Mock();online.comments.return_value=[{'text':'步行较多，建议穿舒适鞋。','comment_id':3,'score':4,'published_at':'2026-10-12','source_url':'https://example.com'}]
        result=run_travel_agent(AgentRequest(question='龙门石窟评论'),catalog=CAT,online=online,model=ScriptModel([
            call('poi_comments',{'poi_id':1}),{'content':json.dumps({'citations':[{'source_id':'E1','quote':'步行较多'}]})}]))
        self.assertEqual(result['status'],'evidence_found');self.assertEqual(result['citations'][0]['published_at'],'2026-10-12')

    def test_fabricated_quote_is_rejected(self):
        online=Mock();online.comments.return_value=[{'text':'景色很好','comment_id':3,'source_url':'https://example.com'}]
        out=run_travel_agent(AgentRequest(question='龙门石窟评论'),catalog=CAT,online=online,model=ScriptModel([
            call('poi_comments',{'poi_id':1}),{'content':'{"citations":[{"source_id":"E1","quote":"轮椅免费"}]}'}]))
        self.assertEqual(out['citations'],[]);self.assertEqual(out['failure'],'evidence_validation_failed')

    def test_cache_budget_and_no_coding_tools(self):
        online=Mock();online.comments.return_value=[]
        ctx=TravelContext(AgentRequest(question='龙门石窟评论'),CAT,online)
        for _ in range(7):result=json.loads(ctx.execute('poi_comments',{'poi_id':1}))
        self.assertEqual(online.comments.call_count,1);self.assertEqual(result['reason'],'tool_budget_exhausted')
        self.assertNotIn('run_tests',ctx.tools());self.assertNotIn('read_file',ctx.tools())

    def test_unconfirmed_id_and_model_expansion_blocked(self):
        ctx=TravelContext(AgentRequest(question='龙门评论'),CAT,Mock())
        self.assertEqual(ctx.dispatch('poi_comments',{'poi_id':1})['state'],'not_queried')
        self.assertEqual(ctx.dispatch('search_pois',{'keyword':'龙门石窟'})['state'],'not_queried')

    def test_exact_name_does_not_select_other_longmen(self):
        ctx=TravelContext(AgentRequest(question='龙门海洋馆评论'),CAT,Mock())
        self.assertEqual(ctx.allowed,{2:'龙门海洋馆'})

    def test_search_ignores_hotel_ids(self):
        tool=OnlineTravel();tool.json=Mock(return_value={'data':[{'type':'poihotel','poiId':9,'word':'附近酒店'}, {'type':'sight','poiId':8,'word':'真实景点'}]})
        self.assertEqual(tool.search('真实')[0]['poi_id'],8);self.assertEqual(len(tool.search('真实')),1)

    def test_empty_schema_not_no_evidence(self):
        tool=OnlineTravel();tool.json=Mock(return_value={})
        with self.assertRaises(ValueError):tool.search('未知')
        with self.assertRaises(ValueError):tool.comments(1)

    def test_comment_minimizes_personal_fields(self):
        tool=OnlineTravel();tool.json=Mock(return_value={'result':{'items':[{'commentId':1,'content':'很好','publishTime':'/Date(1791862946000+0800)/','userInfo':{'userNick':'private'},'ipLocatedName':'private'}]}})
        row=tool.comments(1)[0]
        self.assertTrue(row['published_at']);self.assertNotIn('userInfo',row);self.assertNotIn('ipLocatedName',row)

    def test_detail_identity_and_no_modules(self):
        tool=OnlineTravel();tool.json=Mock(return_value={'templateList':[{'moduleList':[{'moduleType':'basicInfo','poiBasicModule':{'poiId':2,'poiName':'错误'}}]}]})
        with self.assertRaises(ValueError):tool.detail(1,'龙门石窟')

    def test_weather_out_of_range_no_network(self):
        tool=OnlineTravel();tool.json=Mock()
        day=(datetime.now(CN).date()+timedelta(days=20)).isoformat()
        self.assertEqual(tool.weather('洛阳',day)['state'],'not_queried');tool.json.assert_not_called()

    def test_weather_same_name_ambiguity(self):
        tool=OnlineTravel();tool.json=Mock(return_value={'results':[{'name':'朝阳','country_code':'CN'},{'name':'朝阳','country_code':'CN'}]})
        self.assertEqual(tool.weather('朝阳',datetime.now(CN).date().isoformat())['reason'],'weather_location_requires_clarification')

    def test_luoyang_requires_henan(self):
        tool=OnlineTravel();tool.json=Mock(return_value={'results':[{'name':'洛阳市','country_code':'CN','admin1':'福建省'}]})
        self.assertEqual(tool.weather('洛阳',datetime.now(CN).date().isoformat())['state'],'queried_no_evidence')
        self.assertEqual(tool.json.call_args.kwargs['params']['name'],'洛阳市')

    def test_confirmation_name_mismatch(self):
        with self.assertRaises(ValueError):TravelContext(AgentRequest(question='评论',confirmed_poi_id=1,confirmed_poi_name='错误名称'),CAT)

    def test_partial_preserves_comment_when_weather_fails(self):
        online=Mock();online.comments.return_value=[{'text':'步行较多','comment_id':1}];online.weather.side_effect=TimeoutError()
        r=run_travel_agent(AgentRequest(question='龙门石窟评论和洛阳天气'),catalog=CAT,online=online,model=ScriptModel([
            call('poi_comments',{'poi_id':1}),call('weather_forecast',{'city':'洛阳','date':'2026-10-13'}),{'content':'{"citations":[{"source_id":"E1","quote":"步行较多"}]}'}]))
        self.assertEqual(r['status'],'partial');self.assertTrue(r['citations'])

    def test_endpoint_switch(self):
        from fastapi.testclient import TestClient
        from service.retrieval_server import app
        with patch.dict(os.environ,{'RAG_TRAVEL_AGENT_ENABLED':'0'}):
            self.assertEqual(TestClient(app).post('/agent/ask',json={'question':'测试'}).status_code,404)


if __name__=='__main__':unittest.main()
