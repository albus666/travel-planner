"""Plan chat intake: auto-filled slots, only the departure point is asked."""
from datetime import date
import os
import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from functools import partial
from service.plan_chat import Slots, advance as actual_advance, autofill, blocking_issues, compile_trip, chat_enabled, guide_trip
# Existing route-mode component cases explicitly select route planning.
advance=partial(actual_advance, planning_mode='route')
from service.plan_service import POOL
from service import retrieval_server as server

TODAY = date(2026, 10, 13)
TOMORROW = '2026-10-14'
POINT = {'lat': 34.692327, 'lng': 112.442317, 'coord_type': 'bd09ll', 'name': '洛阳站', 'uid': 'u1'}
OTHER = {'lat': 34.6, 'lng': 112.4, 'coord_type': 'bd09ll', 'name': '洛阳站', 'uid': 'u2'}


def slots(**kw):
    """One extracted slot set, starting from the model defaults."""
    return {**Slots().model_dump(mode='json'), **kw}


def extractor(**kw):
    return lambda messages: slots(**kw)


def maps(candidates):
    m = MagicMock()
    m.query.return_value = {'state': 'queried_with_evidence', 'candidates': candidates}
    return m


def map_hit(name='洛阳站', address='某路1号', point=POINT):
    return [{'name': name, 'address': address, 'point': point}]


def planner(status='time_checked_draft'):
    calls = []

    def run(trip):
        calls.append(trip)
        return {'workflow': 'multi_day_v1', 'status': status,
                'days': [{'day': i + 1, 'date': d.plan.trip_date.isoformat(), 'result': {'status': status}}
                         for i, d in enumerate(trip.days)],
                'requested_days': len(trip.days), 'unplanned_days': [], 'warnings': []}

    run.calls = calls
    return run


class AutofillTests(unittest.TestCase):
    def test_only_base_location_remains_blocking(self):
        s, assumed = autofill(Slots(), today=TODAY)
        self.assertEqual(s.city, '洛阳')
        self.assertEqual(s.days, 1)
        self.assertEqual(s.start_date, date(2026, 10, 14))
        self.assertEqual(s.companions, '未说明')
        self.assertEqual(s.transport, '公共交通')
        questions = blocking_issues(s, TODAY)
        self.assertEqual(len(questions), 1)
        self.assertIn('出发', questions[0])
        self.assertTrue(any('未说明天数' in a for a in assumed))
        self.assertTrue(any('未说明开始日期' in a for a in assumed))

    def test_stated_slots_are_not_overwritten(self):
        s, assumed = autofill(Slots(city='洛阳市', days=3, companions='两位老人', transport='自驾'), today=TODAY)
        self.assertEqual(s.city, '洛阳')
        self.assertEqual(s.days, 3)
        self.assertEqual(s.companions, '两位老人')
        self.assertEqual(s.transport, '自驾')
        self.assertFalse(any('未说明天数' in a or '未说明交通方式' in a for a in assumed))


class IntakeTests(unittest.TestCase):
    def test_first_turn_asks_only_for_departure(self):
        m = MagicMock(); plan = planner()
        state, out = advance({}, '帮我安排三天', extractor=extractor(days=3), maps=m, planner=plan, today=TODAY)
        self.assertEqual(out['status'], 'needs_clarification')
        self.assertEqual(len([line for line in out['answer'].split('\n') if line.strip()]), 1)
        self.assertIn('出发', out['answer'])
        self.assertIn('洛阳 3天', out['summary'])
        self.assertTrue(out['assumptions'])
        m.query.assert_not_called(); self.assertEqual(plan.calls, [])

    def test_unique_exact_name_plans_without_a_confirmation_round(self):
        plan = planner()
        state, out = advance({}, '从洛阳站出发，安排三天', extractor=extractor(days=3, base_location='洛阳站'),
                             maps=maps(map_hit()), planner=plan, today=TODAY)
        self.assertEqual(out['status'], 'time_checked_draft')
        self.assertEqual(len(plan.calls), 1)
        self.assertEqual(out['departure_point'], POINT)
        self.assertEqual(len(out['compiled_request']['days']), 3)
        self.assertTrue(out['assumptions'])
        self.assertIn('本次自动补全', out['answer'])

    def test_ambiguous_name_asks_then_honours_the_selection(self):
        plan = planner()
        m = maps([{'name': '洛阳站', 'address': '车站', 'point': POINT},
                  {'name': '洛阳站', 'address': '同名公交站', 'point': OTHER}])
        state, out = advance({}, '从洛阳站出发，安排三天', extractor=extractor(days=3, base_location='洛阳站'),
                             maps=m, planner=plan, today=TODAY)
        self.assertEqual(out['status'], 'needs_clarification'); self.assertEqual(plan.calls, [])
        self.assertEqual(len(out['candidates']), 2)
        state, out = advance(state, '选2', extractor=extractor(days=3, base_location='洛阳站'),
                             maps=m, planner=plan, today=TODAY)
        self.assertEqual(len(plan.calls), 1); self.assertEqual(out['departure_point'], OTHER)

    def test_vague_base_location_is_not_accepted(self):
        m = MagicMock(); plan = planner()
        for vague in ('酒店', '家'):
            state, out = advance({}, '从酒店出发', extractor=extractor(days=2, base_location=vague),
                                 maps=m, planner=plan, today=TODAY)
            self.assertEqual(out['status'], 'needs_clarification')
        m.query.assert_not_called(); self.assertEqual(plan.calls, [])

    def test_unverifiable_constraints_and_unknown_names_still_block(self):
        for kw in ({'unsupported': ['总预算100元以内']}, {'must_visit': ['龙门']}, {'avoid': ['龙门']},
                   {'must_visit': ['龙门石窟'], 'avoid': ['龙门石窟']}):
            m = MagicMock(); plan = planner()
            state, out = advance({}, '帮我安排三天', extractor=extractor(days=3, base_location='洛阳站', **kw),
                                 maps=m, planner=plan, today=TODAY)
            self.assertEqual(out['status'], 'needs_clarification', kw)
            m.query.assert_not_called(); self.assertEqual(plan.calls, [])
            self.assertEqual(state['phase'], 'collect')

    def test_days_unstated_defaults_and_is_reported(self):
        plan = planner()
        state, out = advance({}, '帮我安排行程', extractor=extractor(base_location='洛阳站'),
                             maps=maps(map_hit()), planner=plan, today=TODAY)
        self.assertEqual(len(plan.calls[0].days), 1)
        self.assertTrue(any('未说明天数' in a for a in out['assumptions']))

    def test_locator_failure_does_not_plan(self):
        m = MagicMock(); m.query.return_value = {'state': 'queried_no_evidence', 'candidates': []}
        plan = planner()
        state, out = advance({}, '从洛阳站出发', extractor=extractor(days=2, base_location='洛阳站'),
                             maps=m, planner=plan, today=TODAY)
        self.assertEqual(out['status'], 'needs_clarification'); self.assertEqual(plan.calls, [])
        self.assertIn('地点查询未获得可选结果', out['answer'])


class MultiDayCompileTests(unittest.TestCase):
    def test_dates_are_consecutive_and_stops_never_repeat_across_days(self):
        plan = planner()
        state, out = advance({}, '帮我安排三天，从洛阳站出发',
                             extractor=extractor(days=3, base_location='洛阳站'),
                             maps=maps(map_hit()), planner=plan, today=TODAY)
        trip = plan.calls[0]
        self.assertEqual([d.plan.trip_date.isoformat() for d in trip.days],
                         ['2026-10-14', '2026-10-15', '2026-10-16'])
        self.assertTrue(all(d.plan.city == '洛阳' and d.plan.days == 1 for d in trip.days))
        self.assertTrue(all(d.departure_point == d.end_point and d.departure_point.name == '洛阳站'
                            and d.departure_point.uid == 'u1' for d in trip.days))
        used = [(d, name) for d in trip.days for name in POOL if name not in d.plan.avoid]
        names = [name for _, name in used]
        self.assertEqual(len(names), len(set(names)))
        self.assertEqual(len(names), 6)
        self.assertEqual({d.plan.transport for d in trip.days}, {'公共交通'})

    def test_required_stop_is_kept_out_of_other_days(self):
        plan = planner()
        state, out = advance({}, '必去龙门石窟，三天，从洛阳站出发',
                             extractor=extractor(days=3, base_location='洛阳站', must_visit=['龙门石窟']),
                             maps=maps(map_hit()), planner=plan, today=TODAY)
        trip = plan.calls[0]
        days_with = [d for d in trip.days if '龙门石窟' not in d.plan.avoid]
        self.assertEqual(len(days_with), 1)
        self.assertEqual(days_with[0].plan.must_visit, ['龙门石窟'])

    def test_walking_caps_one_stop_per_day(self):
        plan = planner()
        advance({}, '三天，步行，从洛阳站出发',
                extractor=extractor(days=3, base_location='洛阳站', transport='步行'),
                maps=maps(map_hit()), planner=plan, today=TODAY)
        trip = plan.calls[0]
        for day in trip.days:
            self.assertEqual(len([n for n in POOL if n not in day.plan.avoid]), 1)


class SessionLocationTests(unittest.TestCase):
    def chosen(self):
        state={'phase':'choose','slots':slots(city='洛阳',days=3,base_location='洛阳站',start_date=TOMORROW),
               'candidates':[{'name':'洛阳站','address':'车站','point':POINT},
                             {'name':'洛阳站-地下停车场','address':'道南路1号','point':{**OTHER,'name':'洛阳站-地下停车场'}}]}
        return state

    def test_full_displayed_name_address_confirms_without_search_or_extraction(self):
        m=MagicMock();e=MagicMock(side_effect=AssertionError('extractor not needed'));p=planner()
        state,out=advance(self.chosen(),'洛阳站-地下停车场 — 道南路1号',extractor=e,maps=m,planner=p,today=TODAY)
        self.assertEqual(out['departure_point']['name'],'洛阳站-地下停车场')
        self.assertEqual(state['confirmed_location']['point'],out['departure_point']);m.query.assert_not_called()

    def test_replace_stop_preserves_confirmed_origin_and_excludes_old_stop(self):
        p=planner();m=MagicMock()
        state,_=advance(self.chosen(),'选1',maps=m,planner=p,today=TODAY)
        state,out=advance(state,'天子驾六博物馆我去过了，换个行不',
                          extractor=extractor(city='洛阳',days=3,base_location='洛阳站',start_date=TOMORROW),
                          maps=m,planner=p,today=TODAY)
        m.query.assert_not_called();self.assertEqual(len(p.calls),2)
        self.assertTrue(all('天子驾六博物馆' in d.plan.avoid for d in p.calls[-1].days))
        self.assertEqual(out['departure_point'],POINT)

    def test_changed_base_requires_new_identity_confirmation(self):
        p=planner();state,_=advance(self.chosen(),'选1',planner=p,today=TODAY)
        m=maps([{'name':'新地点候选','address':'新路','point':OTHER}])
        _,out=advance(state,'改从洛阳龙门站出发',extractor=extractor(city='洛阳',days=3,base_location='洛阳龙门站'),
                      maps=m,planner=p,today=TODAY)
        m.query.assert_called_once();self.assertEqual(out['status'],'needs_clarification');self.assertEqual(len(p.calls),1)

    def test_duplicate_name_needs_number_and_does_not_requery(self):
        state=self.chosen();state['candidates'][1]['name']='洛阳站';m=MagicMock();p=planner()
        _,out=advance(state,'洛阳站',maps=m,planner=p,today=TODAY)
        self.assertEqual(out['status'],'needs_clarification');m.query.assert_not_called();self.assertEqual(len(p.calls),0)

    def test_legacy_session_recovers_prior_itinerary_origin(self):
        state=self.chosen();state['phase']='complete';state.pop('candidates')
        state['result']={'days':[{'result':{'legs':[{'route':{'origin':POINT}}]}}]}
        m=MagicMock();p=planner()
        state,out=advance(state,'天子驾六博物馆我去过了，换个行不',
                          extractor=extractor(city='洛阳',days=3,base_location='洛阳站',start_date=TOMORROW),
                          maps=m,planner=p,today=TODAY)
        self.assertEqual(out['departure_point'],POINT);m.query.assert_not_called()

    def test_replacement_does_not_exclude_requested_alternative(self):
        state,_=advance(self.chosen(),'选1',planner=planner(),today=TODAY)
        _,out=advance(state,'不去天子驾六博物馆，换个洛阳博物馆',
                      extractor=extractor(city='洛阳',days=3,base_location='洛阳站'),
                      planner=planner(),today=TODAY)
        self.assertIn('天子驾六博物馆',out['slots']['avoid']);self.assertNotIn('洛阳博物馆',out['slots']['avoid'])


class EndpointTests(unittest.TestCase):
    def test_endpoint_requires_the_chat_flag(self):
        with patch.dict(os.environ, {'RAG_PLAN_CHAT_ENABLED': '0', 'RAG_MAPS_ENABLED': '1'}):
            self.assertFalse(chat_enabled())
            self.assertEqual(TestClient(server.app).post('/plan/chat', json={'message': '帮我安排三天'}).status_code, 404)

    def test_endpoint_disabled_without_maps(self):
        with patch.dict(os.environ, {'RAG_PLAN_CHAT_ENABLED': '1', 'RAG_MAPS_ENABLED': '0'}):
            self.assertEqual(TestClient(server.app).post('/plan/chat', json={'message': '帮我安排三天'}).status_code, 404)

    def test_endpoint_passes_through_when_enabled(self):
        with patch.dict(os.environ, {'RAG_PLAN_CHAT_ENABLED': '1', 'RAG_MAPS_ENABLED': '1'}), \
                patch.object(server, '_MODEL_READY', True), \
                patch.object(server, 'chat', return_value={'status': 'needs_clarification'}) as fn:
            response = TestClient(server.app).post('/plan/chat', json={'message': '帮我安排三天'})
            self.assertEqual(response.status_code, 200); fn.assert_called_once()


class MarkdownAnswerTests(unittest.TestCase):
    def test_citations_stay_structured_and_out_of_body(self):
        from service.plan_chat import render
        c={'source_id':'P1','name':'景点A','quotes':['真实片段'],'source_url':'https://example.com'}
        result={'days':[{'day':1,'date':'2026-10-14','result':{'status':'time_checked_draft',
            'schedule':[{'name':'景点A','arrival_time':'2026-10-14T10:27:07+08:00','visit_duration_minutes':90,'citations':[c]}],
            'estimated_finish_time':'2026-10-14T13:10:07+08:00'}}],'unplanned_days':[]}
        text=render(result)
        self.assertIn('### 第1天',text);self.assertIn('**景点A**',text);self.assertIn('10:27',text)
        self.assertIn('[1]',text);self.assertNotIn('source_id',text);self.assertNotIn('真实片段',text)
        self.assertNotIn('time_checked_draft',text);self.assertNotIn('T10:',text)
        self.assertEqual(result['days'][0]['result']['schedule'][0]['citations'][0],c)

    def test_partial_and_uncertain_times_are_not_formatted_as_known(self):
        from service.plan_chat import render
        text=render({'days':[{'day':1,'date':'2026-10-14','result':{'status':'partial',
            'schedule':[{'name':'景点A','arrival_time':None,'visit_duration_minutes':90,'citations':[]}],
            'issues':['路线查询失败']}}],'unplanned_days':[2]})
        self.assertIn('无法确认',text);self.assertIn('路线查询失败',text);self.assertIn('尚未安排第 2 天',text)


class OptionalDepartureTests(unittest.TestCase):
    def test_missing_departure_offers_skip_and_custom_last(self):
        m=MagicMock()
        _,out=actual_advance({},'带老人去洛阳三天',extractor=extractor(days=3),maps=m,today=TODAY)
        self.assertEqual(out['status'],'needs_clarification')
        self.assertTrue(out['clarification']['options'][-1]['custom'])
        self.assertEqual(out['clarification']['options'][0]['planning_mode'],'guide');m.query.assert_not_called()

    def test_a_place_name_alone_does_not_autosearch(self):
        m=MagicMock()
        _,out=actual_advance({},'汉庭酒店吧',extractor=extractor(days=3,base_location='汉庭酒店'),maps=m,today=TODAY)
        self.assertEqual(out['status'],'needs_clarification');self.assertTrue(out['clarification']['options'][-1]['custom'])
        m.query.assert_not_called()

    def test_skip_reuses_slots_and_never_calls_maps_or_route_planner(self):
        state={'phase':'collect','slots':slots(days=3,start_date=TOMORROW,companions='老人')}
        m=MagicMock();p=MagicMock();e=MagicMock();g=MagicMock(return_value=({'status':'guide_draft','days':[]},'攻略'))
        new,out=actual_advance(state,'不选出发点，只给攻略',planning_mode='guide',maps=m,planner=p,extractor=e,guide_tool=g,today=TODAY)
        self.assertEqual(out['status'],'guide_draft');self.assertEqual(new['planning_mode'],'guide')
        self.assertEqual(g.call_args.args[0].days,3);m.query.assert_not_called();p.assert_not_called();e.assert_not_called()

    def test_guide_does_not_drop_budget_or_ambiguity_constraints(self):
        g=MagicMock();m=MagicMock()
        _,out=actual_advance({},'只给攻略',planning_mode='guide',extractor=extractor(days=3,unsupported=['预算100元']),guide_tool=g,maps=m,today=TODAY)
        self.assertEqual(out['status'],'needs_clarification');g.assert_not_called();m.query.assert_not_called()

    def test_guide_stays_guide_when_replacing_a_poi(self):
        state={'planning_mode':'guide','slots':slots(days=3,start_date=TOMORROW)}
        g=MagicMock(return_value=({'status':'guide_draft','days':[]},'攻略'));m=MagicMock()
        _,out=actual_advance(state,'不去天子驾六博物馆，换个景点',extractor=extractor(days=3,start_date=TOMORROW),guide_tool=g,maps=m,today=TODAY)
        self.assertIn('天子驾六博物馆',g.call_args.args[0].avoid);self.assertEqual(out['status'],'guide_draft');m.query.assert_not_called()

    def test_guide_has_citations_but_no_times_and_does_not_repeat_pois(self):
        requests=[]
        def draft(p):
            requests.append(p)
            name=next(n for n in POOL if n not in p.avoid)
            return {'status':'draft','stops':[{'name':name,'citations':[{'source_id':name,'quotes':['原文']}]}]}
        s,_=autofill(Slots(days=3,start_date=TOMORROW),TODAY)
        result,text=guide_trip(s,draft_tool=draft)
        self.assertEqual(result['status'],'guide_draft');self.assertEqual(len(requests),3)
        names=[d['result']['schedule'][0]['name'] for d in result['days']];self.assertEqual(len(names),len(set(names)))
        for d in result['days']:
            self.assertEqual(d['result']['time_check'],'not_checked')
            self.assertIsNone(d['result']['schedule'][0]['arrival_time']);self.assertTrue(d['result']['schedule'][0]['citations'])
        self.assertNotIn('预计到达',text);self.assertNotIn('source_id',text)


if __name__ == '__main__':
    unittest.main()
