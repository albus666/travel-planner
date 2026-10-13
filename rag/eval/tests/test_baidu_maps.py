import json
import os
import unittest
from unittest.mock import Mock,patch
from datetime import datetime,timedelta

from pydantic import ValidationError
from service.baidu_maps import BaiduMaps,Point,RouteQuery,MatrixQuery,MapError,CN
from service.route_plan import RoutePlanRequest,plan_with_routes

P={'lat':34.63,'lng':112.45,'coord_type':'bd09ll','name':'起点'}
Q={**P,'lat':34.55,'name':'终点'}


def body(**changes):
    request={'plan':{'trip_date':(datetime.now(CN).date()+timedelta(days=1)).isoformat(),'departure':'起点','companions':'两位成人','preferences':['历史文化'],'pace':'轻松','transport':'自驾'},
        'departure_point':P,'end_point':Q,'start_time':'09:00','end_time':'17:00','visit_minutes':{'景点A':60,'景点B':60}}
    request.update(changes);return RoutePlanRequest.model_validate(request)


def draft(_):
    return {'status':'draft','slots':{'trip_date':(datetime.now(CN).date()+timedelta(days=1)).isoformat()},
        'stops':[{'poi_id':1,'name':'景点A','citations':[]},{'poi_id':2,'name':'景点B','citations':[]}]}


def points(_):return {1:Point(**P),2:Point(**Q)}


class MapTests(unittest.TestCase):
    def tool(self,result):
        api=BaiduMaps(budget=False,key='TEST-SECRET');api.get=Mock(return_value=result);return api

    def test_route_lat_lng_and_units(self):
        api=self.tool({'result':{'routes':[{'distance':1200,'duration':120}]}})
        out=api.query('route',{'origin':P,'destination':Q})
        self.assertEqual(out['routes'][0]['duration_seconds'],120)
        self.assertEqual(api.get.call_args.args[1]['origin'],'34.630000,112.450000')

    def test_coordinate_mix_rejected_before_http(self):
        with self.assertRaises(ValidationError):RouteQuery(origin=P,destination={**Q,'coord_type':'wgs84'})

    def test_invalid_coordinate_and_mode(self):
        with self.assertRaises(ValidationError):Point(lat=float('nan'),lng=112)
        with self.assertRaises(ValidationError):Point(lat=120,lng=112)
        with self.assertRaises(ValidationError):RouteQuery(origin=P,destination=Q,mode='fly')

    def test_non_success_never_leaks_key(self):
        session=Mock();session.get.side_effect=RuntimeError('https://example/?ak=TEST-SECRET')
        out=BaiduMaps(budget=False,key='TEST-SECRET',session=session).query('route',{'origin':P,'destination':Q})
        self.assertEqual(out['state'],'query_failed');self.assertNotIn('TEST-SECRET',json.dumps(out))

    def test_quota_error_is_not_no_route(self):
        session=Mock();session.get.return_value.json.return_value={'status':302,'message':'secret'}
        out=BaiduMaps(budget=False,key='x',session=session).query('route',{'origin':P,'destination':Q})
        self.assertEqual(out['state'],'query_failed');self.assertEqual(out['reason'],'provider_302')

    def test_empty_route_not_zero(self):
        out=self.tool({'result':{'routes':[]}}).query('route',{'origin':P,'destination':Q})
        self.assertEqual(out['state'],'queried_no_evidence');self.assertNotIn('duration_seconds',out)

    def test_missing_duration_rejected(self):
        out=self.tool({'result':{'routes':[{'distance':2}]}}).query('route',{'origin':P,'destination':Q})
        self.assertEqual(out['state'],'query_failed')

    def test_matrix_direction_and_missing(self):
        api=self.tool({'result':[{'duration':{'value':1},'distance':{'value':2}}, {'status':7}]})
        out=api.query('matrix',{'origins':[P],'destinations':[P,Q]})
        self.assertEqual(out['pairs'][1]['destination_index'],1);self.assertIsNone(out['pairs'][1]['duration_seconds'])

    def test_matrix_dimension_mismatch(self):
        out=self.tool({'result':[]}).query('matrix',{'origins':[P],'destinations':[Q]})
        self.assertEqual(out['reason'],'invalid_matrix_dimensions')

    def test_matrix_limit(self):
        with self.assertRaises(ValidationError):MatrixQuery(origins=[P]*6,destinations=[Q])

    def test_conversion_lon_lat_and_model(self):
        api=self.tool({'result':[{'x':112.4,'y':34.6}]})
        out=api.query('convert',{'points':[P],'target':'gcj02'})
        self.assertEqual(api.get.call_args.args[1]['coords'],'112.450000,34.630000')
        self.assertEqual(api.get.call_args.args[1]['model'],5);self.assertEqual(out['points'][0]['coord_type'],'gcj02')

    def test_no_wgs84_conversion(self):
        with self.assertRaises(ValidationError):self.tool({}).query('convert',{'points':[P],'target':'wgs84'})

    def test_geocode_requires_user_confirmation(self):
        out=self.tool({'result':{'location':{'lat':34,'lng':112},'confidence':90}}).query('geocode',{'address':'洛阳市洛龙区某路1号'})
        self.assertTrue(out['requires_confirmation'])

    def test_suggestion_retains_multiple_candidates(self):
        out=self.tool({'result':[{'name':'站点A','uid':'u1','location':{'lat':34,'lng':112}},{'name':'站点B','uid':'u2','location':{'lat':34,'lng':112}}]}).query('suggest',{'query':'站点'})
        self.assertEqual(len(out['candidates']),2)

    def test_window_includes_return_and_buffers(self):
        api=Mock();api.query.return_value={'state':'queried_with_evidence','routes':[{'duration_seconds':600}]}
        result=plan_with_routes(body(),draft_tool=draft,points_tool=points,maps=api)
        self.assertEqual(len(result['legs']),3);self.assertIn('12:00:00',result['estimated_finish_time'])
        self.assertEqual(result['time_check'],'within_window')

    def test_excess_keeps_required_stops(self):
        api=Mock();api.query.return_value={'state':'queried_with_evidence','routes':[{'duration_seconds':600}]}
        result=plan_with_routes(body(end_time='10:00'),draft_tool=draft,points_tool=points,maps=api)
        self.assertEqual(result['status'],'constraint_conflict');self.assertEqual(len(result['schedule']),2)

    def test_route_failure_downstream_times_unknown(self):
        api=Mock();api.query.side_effect=[{'state':'query_failed'},{'state':'queried_with_evidence','routes':[{'duration_seconds':600}]}]*2
        result=plan_with_routes(body(),draft_tool=draft,points_tool=points,maps=api)
        self.assertIsNone(result['estimated_finish_time']);self.assertEqual(result['time_check'],'unknown')
        self.assertIsNone(result['schedule'][1]['arrival_time'])

    def test_missing_visit_minutes_does_not_guess(self):
        api=Mock();r=plan_with_routes(body(visit_minutes={}),draft_tool=draft,points_tool=points,maps=api)
        self.assertEqual(r['status'],'needs_clarification');api.query.assert_not_called()

    def test_transport_consistency(self):
        with self.assertRaises(ValidationError):body(mode='walking')

    def test_mapped_order_uses_directed_matrix(self):
        api=Mock()
        pairs=[{'origin_index':a,'destination_index':b,'state':'queried_with_evidence','duration_seconds':1 if (a,b) in ((0,2),(2,1),(1,3)) else 20} for a in range(4) for b in range(4)]
        api.query.side_effect=[{'state':'queried_with_evidence','pairs':pairs}]+[{'state':'queried_with_evidence','routes':[{'duration_seconds':600}]}]*3
        r=plan_with_routes(body(optimize_order=True),draft_tool=draft,points_tool=points,maps=api)
        self.assertEqual([s['poi_id'] for s in r['schedule']],[2,1])

    def test_api_disabled_and_bad_arguments(self):
        from service.retrieval_server import app
        from fastapi.testclient import TestClient
        with patch.dict(os.environ,{'RAG_MAPS_ENABLED':'0'}):
            self.assertEqual(TestClient(app).post('/maps/query',json={'action':'search','arguments':{'query':'洛阳'}}).status_code,404)
        with patch.dict(os.environ,{'RAG_MAPS_ENABLED':'1'}):
            self.assertEqual(TestClient(app).post('/maps/query',json={'action':'route','arguments':{'origin':P,'destination':Q,'url':'http://bad'}}).status_code,422)

    def test_agent_route_uses_confirmed_points(self):
        from service.travel_agent import AgentRequest,TravelContext
        with patch.dict(os.environ,{'RAG_MAPS_ENABLED':'1'}):
            ctx=TravelContext(AgentRequest(question='从起点开车到终点多久',map_points={'起点':P,'终点':Q}),[],Mock())
            ctx.maps=Mock();ctx.maps.query.return_value={'state':'queried_with_evidence','routes':[{'distance_m':1000,'duration_seconds':120}],
                'fetched_at':'2026-10-13T12:00:00+08:00','source_url':'https://lbsyun.baidu.com/','warnings':[]}
            out=ctx.dispatch('map_route',{'origin':'起点','destination':'终点','mode':'driving','region':'洛阳'})
            self.assertEqual(out['evidence'][0]['kind'],'map_route');self.assertIn('2.0分钟',out['evidence'][0]['text'])

    def test_agent_ambiguous_endpoint_does_not_route(self):
        from service.travel_agent import AgentRequest,TravelContext
        with patch.dict(os.environ,{'RAG_MAPS_ENABLED':'1'}):
            ctx=TravelContext(AgentRequest(question='从起点开车到终点多久'),[],Mock());ctx.maps=Mock()
            ctx.maps.query.return_value={'state':'queried_with_evidence','candidates':[{'name':'起点A','point':P},{'name':'起点B','point':Q}]}
            out=ctx.dispatch('map_route',{'origin':'起点','destination':'终点','mode':'driving','region':'洛阳'})
            self.assertTrue(ctx.map_pending);self.assertEqual(out['reason'],'map_endpoint_requires_confirmation')
            self.assertTrue(all(c.args[0]=='search' for c in ctx.maps.query.call_args_list))

    def test_agent_disallows_invented_city(self):
        from service.travel_agent import AgentRequest,TravelContext
        with patch.dict(os.environ,{'RAG_MAPS_ENABLED':'1'}):
            ctx=TravelContext(AgentRequest(question='从起点开车到终点多久'),[],Mock())
            out=ctx.dispatch('map_route',{'origin':'起点','destination':'终点','mode':'driving','region':'北京'})
            self.assertEqual(out['state'],'not_queried')


if __name__=='__main__':unittest.main()
