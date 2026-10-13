import os
import tempfile
import unittest
from datetime import timedelta
from unittest.mock import Mock,patch
from pydantic import ValidationError
from service.map_budget import MapBudget,BudgetDenied
from service.trip_service import TripRequest,repair_route,plan_trip_days
from eval.tests.test_baidu_maps import body,draft,points,P


class BudgetTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.now=1800000000
        self.path=self.temp.name+'/budget.sqlite3'
        self.b=MapBudget(self.path,clock=lambda:self.now)
    def tearDown(self):self.temp.cleanup()
    def test_cache_survives_instances_and_keeps_timestamp(self):
        loader=Mock(return_value={'status':0})
        self.b.fetch('place/v2/search',{'query':'A'},loader)
        self.now+=1
        r=MapBudget(self.path,clock=lambda:self.now).fetch('place/v2/search',{'query':'A'},loader)
        self.assertTrue(r[2]);self.assertEqual(r[1],self.now-1);self.assertEqual(loader.call_count,1)
    def test_expired_cache_requeries(self):
        loader=Mock(return_value={'status':0})
        self.b.fetch('directionlite/v1/driving',{},loader);self.now+=301
        self.assertFalse(self.b.fetch('directionlite/v1/driving',{},loader)[2]);self.assertEqual(loader.call_count,2)
    def test_matrix_budget_counts_pairs(self):
        with patch.dict(os.environ,{'BAIDU_DAILY_MATRIX':'3'}):
            loader=Mock()
            with self.assertRaises(BudgetDenied):self.b.fetch('routematrix/v2/driving',{'origins':'a|b','destinations':'a|b'},loader)
            loader.assert_not_called()
    def test_place_and_suggestion_share_budget(self):
        with patch.dict(os.environ,{'BAIDU_DAILY_PLACE':'1'}):
            self.b.fetch('place/v2/search',{},lambda:{})
            with self.assertRaises(BudgetDenied):self.b.fetch('place/v2/suggestion',{},lambda:{})
            self.now+=86400
            self.b.fetch('place/v2/suggestion',{},lambda:{})
    def test_failed_request_charged_not_cached(self):
        with self.assertRaises(RuntimeError):self.b.fetch('place/v2/search',{},Mock(side_effect=RuntimeError()))
        self.assertEqual(self.b.status()['usage']['place'],1)
    def test_queue_is_bounded(self):
        with patch('service.map_budget.time.sleep'):
            for i in range(4):self.b.fetch('place/v2/search',{'q':i},lambda:{})
            with self.assertRaises(BudgetDenied):self.b.fetch('place/v2/search',{'q':5},lambda:{})


def fake_maps():
    api=Mock();api.query.return_value={'state':'queried_with_evidence','routes':[{'duration_seconds':600}]}
    return api


class TripTests(unittest.TestCase):
    def test_optional_removed_then_rechecked(self):
        b=body(end_time='10:40');b.plan.must_visit=['景点A']
        r=repair_route(b,draft_tool=draft,points_tool=points,maps=fake_maps())
        self.assertEqual(r['status'],'time_checked_draft');self.assertEqual(r['removed_optional'],['景点B'])
        self.assertEqual(r['replan_count'],1);self.assertEqual(len(r['legs']),2)
    def test_required_never_removed(self):
        b=body(end_time='09:30');b.plan.must_visit=['景点A','景点B']
        r=repair_route(b,draft_tool=draft,points_tool=points,maps=fake_maps())
        self.assertEqual(r['status'],'constraint_conflict');self.assertEqual(r['removed_optional'],[])
    def test_no_retry_on_missing_evidence(self):
        api=fake_maps();api.query.return_value={'state':'not_queried','reason':'daily_budget_exhausted'}
        r=repair_route(body(),draft_tool=draft,points_tool=points,maps=api)
        self.assertEqual(r['status'],'partial');self.assertEqual(r['replan_count'],0)
    def test_zero_repair_budget(self):
        r=repair_route(body(end_time='09:30'),0,draft_tool=draft,points_tool=points,maps=fake_maps())
        self.assertEqual(r['replan_count'],0)
    def days(self):
        a=body(end_point=P);b=body(end_point=P);b.plan.trip_date=a.plan.trip_date+timedelta(days=1)
        return a,b
    def test_consecutive_dates_and_overnight(self):
        a,b=self.days();TripRequest(days=[a,b])
        b.plan.trip_date+=timedelta(days=1)
        with self.assertRaises(ValidationError):TripRequest(days=[a,b])
        a,b=self.days();b.departure_point.lat+=1
        with self.assertRaises(ValidationError):TripRequest(days=[a,b])
    def test_duplicate_required_rejected(self):
        a,b=self.days();a.plan.must_visit=b.plan.must_visit=['景点A']
        with self.assertRaises(ValidationError):TripRequest(days=[a,b])
    def test_future_required_reserved_and_no_duplicates(self):
        a,b=self.days();b.plan.must_visit=['景点B'];seen=[]
        def choose(p):
            seen.append(set(p.avoid));d=draft(p);d['slots']['trip_date']=p.trip_date.isoformat()
            d['stops']=[s for s in d['stops'] if s['name'] not in p.avoid];return d
        r=plan_trip_days(TripRequest(days=[a,b]),draft_tool=choose,points_tool=points,maps=fake_maps())
        self.assertEqual(r['status'],'time_checked_draft');self.assertIn('景点B',seen[0]);self.assertIn('景点A',seen[1])
        self.assertEqual([d['result']['schedule'][0]['name'] for d in r['days']],['景点A','景点B'])
    def test_failure_stops_next_day(self):
        a,b=self.days();a.end_time='09:01';a.plan.must_visit=['景点A','景点B']
        r=plan_trip_days(TripRequest(days=[a,b]),draft_tool=draft,points_tool=points,maps=fake_maps())
        self.assertEqual(r['unplanned_days'],[2]);self.assertEqual(r['status'],'constraint_conflict')

    def test_http_endpoints_with_fake_dependencies(self):
        from fastapi.testclient import TestClient
        import service.retrieval_server as server
        with patch.dict(os.environ,{'RAG_MAPS_ENABLED':'1'}),patch.object(server,'_MODEL_READY',True):
            with patch.object(server,'repair_route',return_value={'status':'constraint_conflict'}) as repair:
                response=TestClient(server.app).post('/plan/replan',json={'route':body().model_dump(mode='json')})
                self.assertEqual(response.status_code,200);repair.assert_called_once()
            a,b=self.days()
            with patch.object(server,'plan_trip_days',return_value={'status':'time_checked_draft'}) as trip:
                response=TestClient(server.app).post('/plan/multi-day',json={'days':[d.model_dump(mode='json') for d in [a,b]]})
                self.assertEqual(response.status_code,200);trip.assert_called_once()
