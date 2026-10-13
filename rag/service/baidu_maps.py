"""Baidu Web API adapter; typed coordinates, redacted failures and fixed endpoints."""
from datetime import datetime, timedelta, timezone
import math
import os
from pathlib import Path
from typing import Literal

from dotenv import dotenv_values
from pydantic import BaseModel, ConfigDict, Field, model_validator
import requests

ROOT = Path(__file__).resolve().parents[2]
CN = timezone(timedelta(hours=8))


def maps_enabled():
    return os.getenv('RAG_MAPS_ENABLED','0') == '1'


def api_key():
    values=dotenv_values(ROOT/'key/.env')
    return os.getenv('BAIDU_MAP_AK') or values.get('BAIDU_MAP_AK') or values.get('baidu-apikey')


class Strict(BaseModel):
    model_config=ConfigDict(extra='forbid', allow_inf_nan=False)


class Point(Strict):
    lat: float=Field(ge=-90,le=90)
    lng: float=Field(ge=-180,le=180)
    coord_type: Literal['bd09ll','gcj02','wgs84']='bd09ll'
    name: str=Field('',max_length=150)
    uid: str | None=Field(None,max_length=100)

    def latlng(self):return f'{self.lat:.6f},{self.lng:.6f}'


class PlaceQuery(Strict):
    query: str=Field(min_length=2,max_length=100)
    region: str=Field('洛阳',min_length=2,max_length=50)


class GeocodeQuery(Strict):
    address: str=Field(min_length=5,max_length=200)
    city: str=Field('洛阳',min_length=2,max_length=50)


class ReverseQuery(Strict):
    point: Point


class RouteQuery(Strict):
    origin: Point
    destination: Point
    mode: Literal['driving','walking','riding','transit']='driving'
    advanced: bool=False

    @model_validator(mode='after')
    def validate_coordinates(self):
        if self.origin.coord_type!=self.destination.coord_type:
            raise ValueError('mixed coordinate systems; convert explicitly first')
        if self.advanced and self.mode!='driving':
            raise ValueError('advanced route supports driving in this integration')
        return self


class MatrixQuery(Strict):
    origins: list[Point]=Field(min_length=1,max_length=5)
    destinations: list[Point]=Field(min_length=1,max_length=5)
    mode: Literal['driving','walking','riding']='driving'

    @model_validator(mode='after')
    def validate_coordinates(self):
        if len({p.coord_type for p in self.origins+self.destinations})!=1:
            raise ValueError('mixed coordinate systems; convert explicitly first')
        return self


class ConvertQuery(Strict):
    points: list[Point]=Field(min_length=1,max_length=10)
    target: Literal['bd09ll','gcj02']='bd09ll'


SCHEMAS={'search':PlaceQuery,'suggest':PlaceQuery,'geocode':GeocodeQuery,'reverse':ReverseQuery,
    'route':RouteQuery,'matrix':MatrixQuery,'convert':ConvertQuery}


class MapRequest(Strict):
    action: Literal['search','suggest','geocode','reverse','route','matrix','convert']
    arguments: dict


class MapError(Exception):
    def __init__(self, code, state='query_failed'):
        self.code=str(code);self.state=state
        super().__init__(self.code)


def number(value):
    if isinstance(value,bool) or not isinstance(value,(float,int)) or not math.isfinite(value) or value<0:
        raise MapError('invalid_numeric_response')
    return value


class BaiduMaps:
    def __init__(self,key=None,session=None,timeout=10,budget=True):
        self.key=key or api_key();self.session=session or requests.Session();self.timeout=timeout
        self.budget=budget;self.cache_info=None

    def get(self,path,params):
        if not self.key:raise MapError("missing_baidu_key","not_queried")
        if not self.budget:return self._get(path,params)
        from service.map_budget import MapBudget,BudgetDenied
        try:
            data,at,hit=MapBudget().fetch(path,params,lambda:self._get(path,params))
            self.cache_info={"cache_hit":hit,"fetched_at":datetime.fromtimestamp(at,CN).isoformat(timespec="seconds")}
            return data
        except BudgetDenied as e:raise MapError(str(e),"not_queried") from None
        except (OSError, __import__("sqlite3").Error):raise MapError("budget_store_unavailable","not_queried") from None

    def _get(self,path,params):
        if not self.key:raise MapError('missing_baidu_key','not_queried')
        try:
            r=self.session.get('https://api.map.baidu.com/'+path,params={**params,'ak':self.key,'output':'json'},timeout=self.timeout)
            r.raise_for_status();data=r.json()
        except Exception as exc:
            # Never propagate a requests exception containing the AK query string.
            raise MapError('transport_'+type(exc).__name__) from None
        if not isinstance(data,dict):raise MapError('invalid_schema')
        if data.get('status') not in (0,'0'):
            code=data.get('status','missing_status')
            raise MapError('provider_'+str(code),'queried_no_evidence' if code in (7,1001,1003) else 'query_failed')
        return data

    def query(self,action,args):
        self.cache_info=None
        body=SCHEMAS[action].model_validate(args)
        metadata={'provider':'baidu','fetched_at':datetime.now(CN).isoformat(timespec='seconds'),
            'source_url':'https://lbsyun.baidu.com/','action':action}
        try:
            data=getattr(self,action)(body)
            return {**metadata,'state':'queried_with_evidence',**data,**(self.cache_info or {})}
        except MapError as e:
            return {**metadata,'state':e.state,'reason':e.code}

    def search(self,b):
        root=self.get('place/v2/search',{'query':b.query,'region':b.region,'city_limit':'true','scope':2,'page_size':10})
        return self.places(root.get('results'),b.region)

    def suggest(self,b):
        root=self.get('place/v2/suggestion',{'query':b.query,'region':b.region,'city_limit':'true'})
        return self.places(root.get('result'),b.region)

    @staticmethod
    def places(rows,region):
        if not isinstance(rows,list):raise MapError('invalid_places_schema')
        output=[]
        for row in rows[:10]:
            loc=row.get('location') or {}
            try:point=Point(lat=loc['lat'],lng=loc['lng'],name=row['name'],uid=row['uid'])
            except (KeyError,ValueError,TypeError):continue
            output.append({'name':row['name'],'uid':row['uid'],'city':row.get('city'),
                'area':row.get('area',row.get('district')),'address':row.get('address'),
                'point':point.model_dump(),'query_region':region})
        return {'state':'queried_with_evidence' if output else 'queried_no_evidence','candidates':output,
            'identity_note':'Baidu UID is not a Ctrip poi_id; result is a candidate, not automatic confirmation'}

    def geocode(self,b):
        root=self.get('geocoding/v3/',{'address':b.address,'city':b.city,'ret_coordtype':'bd09ll'})
        row=root.get('result') or {};loc=row.get('location') or {}
        try:point=Point(lat=loc['lat'],lng=loc['lng'],name=b.address)
        except (KeyError,ValueError,TypeError):raise MapError('invalid_geocode_schema') from None
        return {'point':point.model_dump(),'precise':row.get('precise'),'confidence':row.get('confidence'),
            'comprehension':row.get('comprehension'),'requires_confirmation':True}

    def reverse(self,b):
        root=self.get('reverse_geocoding/v3/',{'location':b.point.latlng(),'coordtype':b.point.coord_type,'extensions_poi':0})
        row=root.get('result') or {}
        if not row.get('formatted_address'):raise MapError('missing_address','queried_no_evidence')
        return {'address':row['formatted_address'],'address_components':row.get('addressComponent'),
            'point':b.point.model_dump()}

    def route(self,b):
        path='direction/v2/driving' if b.advanced else 'directionlite/v1/'+b.mode
        params={'origin':b.origin.latlng(),'destination':b.destination.latlng(),'coord_type':b.origin.coord_type,'steps_info':0}
        if b.origin.uid:params['origin_uid']=b.origin.uid
        if b.destination.uid:params['destination_uid']=b.destination.uid
        root=self.get(path,params);routes=(root.get('result') or {}).get('routes')
        if not isinstance(routes,list) or not routes:raise MapError('no_route','queried_no_evidence')
        output=[]
        for row in routes[:3]:
            output.append({'distance_m':number(row.get('distance')),'duration_seconds':number(row.get('duration')),
                'toll_yuan':row.get('toll'),'traffic_condition':row.get('traffic_condition')})
        return {'origin':b.origin.model_dump(),'destination':b.destination.model_dump(),'mode':b.mode,'routes':output,
            'selected_route_index':0,'duration_scope':'estimate_at_query_time_not_future_departure_prediction',
            'warnings':['预计交通耗时，不含游览、排队、停车、打车等候；不保证未来出行时耗时相同。','景点中心坐标不一定是入口；需确认出入口或停车场。']}

    def matrix(self,b):
        root=self.get('routematrix/v2/'+b.mode,{'origins':'|'.join(p.latlng() for p in b.origins),
            'destinations':'|'.join(p.latlng() for p in b.destinations),'coord_type':b.origins[0].coord_type})
        rows=root.get('result');size=len(b.origins)*len(b.destinations)
        if not isinstance(rows,list) or len(rows)!=size:raise MapError('invalid_matrix_dimensions')
        values=[]
        for i,row in enumerate(rows):
            if row.get('status',0) not in (0,'0'):
                values.append({'origin_index':i//len(b.destinations),'destination_index':i%len(b.destinations),'state':'queried_no_evidence','duration_seconds':None});continue
            try:duration=number((row.get('duration') or {}).get('value'));distance=number((row.get('distance') or {}).get('value'))
            except MapError:
                values.append({'origin_index':i//len(b.destinations),'destination_index':i%len(b.destinations),'state':'queried_no_evidence','duration_seconds':None});continue
            values.append({'origin_index':i//len(b.destinations),'destination_index':i%len(b.destinations),
                'state':'queried_with_evidence','duration_seconds':duration,'distance_m':distance})
        return {'state':'queried_with_evidence' if any(v['state']=='queried_with_evidence' for v in values) else 'queried_no_evidence',
            'pairs':values,'mode':b.mode,'billable_route_pairs':size,'note':'Directional matrix; A to B is not assumed equal to B to A.'}

    def convert(self,b):
        source={p.coord_type for p in b.points}
        if len(source)!=1:raise MapError('mixed_conversion_sources','not_queried')
        source=source.pop()
        if source==b.target:return {'points':[p.model_dump() for p in b.points],'conversion':'identity'}
        model={('gcj02','bd09ll'):1,('wgs84','bd09ll'):2,('bd09ll','gcj02'):5}.get((source,b.target))
        if model is None:raise MapError('unsupported_conversion','not_queried')
        root=self.get('geoconv/v2/',{'coords':';'.join(f'{p.lng:.6f},{p.lat:.6f}' for p in b.points),'model':model})
        rows=root.get('result')
        if not isinstance(rows,list) or len(rows)!=len(b.points):raise MapError('invalid_conversion_schema')
        try:points=[Point(lat=r['y'],lng=r['x'],coord_type=b.target,name=p.name).model_dump() for p,r in zip(b.points,rows)]
        except (KeyError,ValueError,TypeError):raise MapError('invalid_conversion_point') from None
        return {'points':points,'conversion':f'{source}_to_{b.target}','note':'No conversion to WGS84 is provided.'}
