import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

from service.agent_session import MemoryStore, SessionStore
from service.travel_agent import AgentRequest, TravelContext, run_travel_agent
from service.travel_online import OnlineTravel, CN

CAT=[{'poi_id':1,'name':'龙门石窟','district':'洛阳'},{'poi_id':2,'name':'龙门海洋馆','district':'洛阳'}]

_TEMP=None


def setUpModule():
    # 默认会话库写到仓库 var/ 会污染工作区；测试统一指向临时目录。
    global _TEMP
    _TEMP=tempfile.TemporaryDirectory()
    os.environ['TRAVEL_AGENT_DB']=str(Path(_TEMP.name)/'agent.sqlite3')


def tearDownModule():
    os.environ.pop('TRAVEL_AGENT_DB',None)
    if _TEMP:_TEMP.cleanup()


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

    def test_quote_with_non_breaking_space_is_kept_verbatim(self):
        online=Mock();online.comments.return_value=[{'text':'步行较多\xa0建议穿舒适鞋','comment_id':3,'source_url':'https://example.com'}]
        out=run_travel_agent(AgentRequest(question='龙门石窟评论'),catalog=CAT,online=online,model=ScriptModel([
            call('poi_comments',{'poi_id':1}),{'content':'{"citations":[{"source_id":"E1","quote":"步行较多 建议穿舒适鞋"}]}'}]))
        self.assertEqual(out['status'],'evidence_found');self.assertIn('\xa0',out['citations'][0]['quote'])

    def test_facilities_are_routed_to_local_search(self):
        # 真实缺陷：设施/停车问题曾被当成票价问题，只调 ticket_snapshot 而漏掉设施条目。
        from service.travel_agent import PROMPT
        tools=TravelContext(AgentRequest(question='龙门石窟停车费'),CAT,Mock()).tools()
        self.assertIn('停车',tools['local_search'].description)
        self.assertIn('不含停车',tools['ticket_snapshot'].description)
        self.assertIn('设施',PROMPT);self.assertIn('local_search',PROMPT)
        self.assertIn('ticket_snapshot',PROMPT)

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

    def test_online_search_does_not_silently_pick_one_of_many_same_names(self):
        # 真实缺陷：搜索“鸡公山”返回 8 个同名异地景点，其中一个（四川石棉）名字正好是
        # “鸡公山”，于是被静默选中，真正的信阳鸡公山景区被忽略，最后答“无法确认”。
        rows=[{'poi_id':79134,'name':'鸡公山景区','district':'信阳'},
              {'poi_id':131905011,'name':'鸡公山','district':'石棉'},
              {'poi_id':56807352,'name':'鸡公山大峡谷','district':'鲁甸'}]
        online=Mock();online.search.return_value=rows
        ctx=TravelContext(AgentRequest(question='鸡公山有哪些好玩的'),CAT,online)
        tool=ctx.tools()['search_pois']
        result=json.loads(tool.handler({'keyword':'鸡公山'}))
        self.assertEqual(result['state'],'queried_with_evidence')
        self.assertTrue(ctx.pending)
        self.assertEqual(ctx.allowed,{})          # 不得静默替用户选定
        self.assertEqual(len(ctx.candidates),3)

    def test_single_online_candidate_resolves_without_asking(self):
        online=Mock();online.search.return_value=[{'poi_id':79134,'name':'鸡公山景区','district':'信阳'}]
        ctx=TravelContext(AgentRequest(question='鸡公山有哪些好玩的'),CAT,online)
        json.loads(ctx.tools()['search_pois'].handler({'keyword':'鸡公山'}))
        self.assertFalse(ctx.pending);self.assertEqual(ctx.allowed,{79134:'鸡公山景区'})

    def test_ambiguous_candidates_are_answered_with_district(self):
        # 两个“龙门…”必须靠地区区分，否则候选列表无法辨认。
        result=run_travel_agent(AgentRequest(question='龙门有哪些好玩的'),catalog=CAT,online=Mock(),model=ScriptModel([
            call('search_pois',{'keyword':'龙门'}),{'content':'{"citations":[]}'}]))
        self.assertEqual(result['status'],'needs_clarification')
        self.assertIn('龙门石窟（洛阳）',result['answer'])
        self.assertIn('龙门海洋馆（洛阳）',result['answer'])

    def test_model_writes_the_answer_and_citations_are_validated(self):
        # 期望：正文由模型组织成自然语言，而不是把原文一条条列出来。
        online=Mock();online.comments.return_value=[{'text':'步行较多，建议穿舒适鞋。','comment_id':3,'source_url':'https://example.com'}]
        result=run_travel_agent(AgentRequest(question='龙门石窟评论'),catalog=CAT,online=online,sessions=MemoryStore(),model=ScriptModel([
            call('poi_comments',{'poi_id':1}),
            {'content':json.dumps({'answer':'游客普遍建议穿舒适的鞋，因为景区内步行较多。','citations':[{'source_id':'E1','quote':'步行较多，建议穿舒适鞋'}]},ensure_ascii=False)}]))
        self.assertEqual(result['status'],'evidence_found')
        self.assertEqual(result['answer'],'游客普遍建议穿舒适的鞋，因为景区内步行较多。')
        self.assertNotIn('以下是本次取得的相关证据',result['answer'])
        self.assertEqual(len(result['citations']),1)

    def test_unsupported_quote_discards_the_whole_answer(self):
        # 引用对不上原文时，模型写的正文也必须作废，不能漏出去。
        online=Mock();online.comments.return_value=[{'text':'景色很好','comment_id':3,'source_url':'https://example.com'}]
        out=run_travel_agent(AgentRequest(question='龙门石窟评论'),catalog=CAT,online=online,sessions=MemoryStore(),model=ScriptModel([
            call('poi_comments',{'poi_id':1}),
            {'content':json.dumps({'answer':'65岁以上免票。','citations':[{'source_id':'E1','quote':'轮椅免费'}]},ensure_ascii=False)}]))
        self.assertEqual(out['citations'],[])
        self.assertEqual(out['failure'],'evidence_validation_failed')
        self.assertNotIn('65岁',out['answer'])

    def test_missing_answer_field_falls_back_to_quote_list(self):
        online=Mock();online.comments.return_value=[{'text':'步行较多','comment_id':3,'source_url':'https://example.com'}]
        out=run_travel_agent(AgentRequest(question='龙门石窟评论'),catalog=CAT,online=online,sessions=MemoryStore(),model=ScriptModel([
            call('poi_comments',{'poi_id':1}),{'content':'{"citations":[{"source_id":"E1","quote":"步行较多"}]}'}]))
        self.assertEqual(out['status'],'evidence_found')
        self.assertIn('以下是本次取得的相关证据',out['answer'])

    def test_session_remembers_confirmed_poi_and_skips_reasking(self):
        # 真实缺陷：“介绍一下万岁山”连问两次，每次都被重新追问是哪一个。
        store=MemoryStore()
        online=Mock()
        online.search.return_value=[{'poi_id':9,'name':'万岁山武侠城','district':'开封'}]
        # 生产代码会 row.pop('text')，所以每次都要返回新的 dict，否则第二次就 KeyError。
        online.comments.side_effect=lambda pid:[{'text':'实景演出互动性强','comment_id':1,'source_url':'https://example.com'}]
        reply=json.dumps({'answer':'实测回答','citations':[{'source_id':'E1','quote':'实景演出互动性强'}]},ensure_ascii=False)
        first=run_travel_agent(AgentRequest(question='介绍一下万岁山武侠城'),catalog=CAT,online=online,sessions=store,model=ScriptModel([
            call('search_pois',{'keyword':'万岁山'}),call('poi_comments',{'poi_id':9}),{'content':reply}]))
        self.assertTrue(first['session_id'])
        self.assertEqual(first['status'],'evidence_found')
        self.assertEqual(store.load(first['session_id'])['allowed'],{'9':'万岁山武侠城'})

        # 第二轮沿用会话里的确认，直接给答案，不再联网也不再回到候选追问。
        online.search=Mock(side_effect=AssertionError('不应再联网搜索已确认的景点'))
        second=run_travel_agent(AgentRequest(question='介绍一下万岁山',session_id=first['session_id']),catalog=CAT,online=online,sessions=store,model=ScriptModel([
            call('search_pois',{'keyword':'万岁山'}),call('poi_comments',{'poi_id':9}),{'content':reply}]))
        self.assertEqual(second['status'],'evidence_found')
        self.assertEqual(second['answer'],'实测回答')
        self.assertEqual(second['candidates'],[])
        online.search.assert_not_called()

    def test_session_allowed_only_reuses_matching_name(self):
        # 会话确认过“龙门石窟”，问“龙门海洋馆”时必须重新判定，不能张冠李戴。
        ctx=TravelContext(AgentRequest(question='龙门海洋馆评论'),CAT,Mock(),None,{1:'龙门石窟'})
        self.assertEqual(ctx.allowed,{2:'龙门海洋馆'})

    def test_unknown_session_id_starts_fresh_without_error(self):
        result=run_travel_agent(AgentRequest(question='龙门石窟评论',session_id='a'*32),catalog=CAT,
            online=Mock(),sessions=MemoryStore(),model=ScriptModel([call('poi_comments',{'poi_id':1}),{'content':'{"citations":[]}'}]))
        self.assertEqual(result['session_id'],'a'*32)
        self.assertEqual(result['citations'],[])

    def test_sqlite_store_round_trips_and_closes_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'agent.sqlite3'
            store=SessionStore(path)
            store.save('b'*32,{'allowed':{'9':'万岁山武侠城'},'messages':[{'user':'问','answer':'答'}]})
            self.assertEqual(store.load('b'*32)['allowed'],{'9':'万岁山武侠城'})
            self.assertIsNone(store.load('c'*32))
        self.assertFalse(path.exists())  # 连接已关闭，临时目录才能被清掉

    def test_session_resolves_deictic_location_for_weather(self):
        # 真实缺陷：“老君山停车费多少”之后问“后天这里的天气”，模型正确推出洛阳，
        # 却因城市未字面出现在问题里被守卫拒绝。
        store=MemoryStore()
        online=Mock();online.weather.return_value={'state':'queried_with_evidence','city':'洛阳','date':'2026-10-15',
            'fields':{'temperature_2m_max':20},'source_url':'https://open-meteo.com/','provider_updated_at':None}
        first=run_travel_agent(AgentRequest(question='龙门石窟停车费多少'),catalog=CAT,online=online,sessions=store,
            model=ScriptModel([{'content':'{"answer":"10元/次","citations":[]}'}]))
        self.assertEqual(store.load(first['session_id'])['city'],'洛阳')
        session=first['session_id']
        second=run_travel_agent(AgentRequest(question='我想知道后天这里的天气如何',session_id=session),catalog=CAT,
            online=online,sessions=store,model=ScriptModel([
                call('weather_forecast',{'city':'洛阳','date':'2026-10-15'}),
                {'content':json.dumps({'answer':'后天洛阳晴。','citations':[]},ensure_ascii=False)}]))
        self.assertNotEqual(second['tool_trace'][0]['state'],'not_queried')
        online.weather.assert_called_once()

    def test_weather_city_still_must_come_from_session_or_text(self):
        # 守卫不能被放宽成“模型填什么城市都行”。
        ctx=TravelContext(AgentRequest(question='这里的天气怎么样'),CAT,Mock(),None,{},'洛阳',{})
        self.assertTrue(ctx.city_allowed('洛阳'))
        self.assertFalse(ctx.city_allowed('北京'))
        ctx2=TravelContext(AgentRequest(question='北京天气'),CAT,Mock(),None,{},None,{})
        self.assertFalse(ctx2.city_allowed('洛阳'))
        self.assertTrue(ctx2.city_allowed('北京'))

    def test_city_requires_a_deictic_reference_or_poi_name(self):
        # 会话城市存在，但用户没指代也没点名景点时，不能拿它兜底。
        ctx=TravelContext(AgentRequest(question='有什么好吃的'),CAT,Mock(),None,{},'洛阳',{7:{'name':'龙门石窟','district':'洛阳'}})
        self.assertFalse(ctx.city_allowed('洛阳'))
        ctx_named=TravelContext(AgentRequest(question='龙门石窟那边天气'),CAT,Mock(),None,{},'洛阳',{7:{'name':'龙门石窟','district':'洛阳'}})
        self.assertTrue(ctx_named.city_allowed('洛阳'))

    def test_missing_city_gets_an_actionable_warning(self):
        out=run_travel_agent(AgentRequest(question='后天天气怎么样'),catalog=CAT,online=Mock(),sessions=MemoryStore(),
            model=ScriptModel([call('weather_forecast',{'city':'洛阳','date':'2026-10-15'}),{'content':'{"answer":"","citations":[]}'}]))
        self.assertEqual(out['status'],'insufficient_evidence')
        self.assertTrue(any('城市' in w for w in out['warnings']))

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
