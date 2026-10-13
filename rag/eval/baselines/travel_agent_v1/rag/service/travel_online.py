"""Read-only online adapters. Provider data is evidence, never instructions."""
from datetime import date, datetime, timedelta, timezone
import re

import requests

CN = timezone(timedelta(hours=8))
SEARCH_URL = 'https://m.ctrip.com/restapi/soa2/30668/search'
DETAIL_URL = 'https://m.ctrip.com/restapi/soa2/18254/json/getPoiMoreDetail'
COMMENT_URL = 'https://m.ctrip.com/restapi/soa2/13444/json/getCommentCollapseList'
WEATHER_URL = 'https://api.open-meteo.com/v1/forecast'
GEO_URL = 'https://geocoding-api.open-meteo.com/v1/search'


def now():
    return datetime.now(CN).isoformat(timespec='seconds')


def text(value):
    from html import unescape
    return unescape(re.sub('<[^>]+>', ' ', str(value or ''))).strip()


def stamp(value):
    match = re.fullmatch(r'/Date\((\d+)(?:[+-]\d{4})?\)/', str(value or ''))
    if match:
        return datetime.fromtimestamp(int(match[1])/1000, CN).isoformat()
    return None


def sight_url(poi_id):
    return f'https://m.ctrip.com/webapp/you/gspoi/sight/0/0.html?poiId={poi_id}'


class OnlineTravel:
    def __init__(self, session=None, timeout=12):
        self.session = session or requests.Session()
        self.session.headers.update({'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'})
        self.timeout = timeout

    def json(self, method, url, **kwargs):
        r = self.session.request(method, url, timeout=self.timeout, **kwargs)
        r.raise_for_status()
        result = r.json()
        if not isinstance(result, dict):
            raise ValueError('invalid_provider_schema')
        status = result.get('ResponseStatus') or {}
        if status.get('Ack') not in (None, 'Success') or result.get('error'):
            raise ValueError('provider_error')
        return result

    def search(self, keyword):
        root = self.json('POST', SEARCH_URL, params={'action':'globalonline', 'source':'globalonline', 'keyword':keyword},
            data='', headers={'Content-Type':'application/x-www-form-urlencoded'})
        if not isinstance(root.get('data'), list):
            raise ValueError('invalid_search_schema')
        candidates = {}
        for row in root['data']:
            pid = row.get('poiId')
            if row.get('type') != 'sight' or not isinstance(pid, int) or pid <= 0:
                continue
            name = text(row.get('word'))
            if name:
                candidates[pid] = {'poi_id':pid, 'name':name, 'district':row.get('districtName'),
                    'source_url':sight_url(pid), 'source':'ctrip_online_search'}
        return list(candidates.values())[:15]

    def detail(self, poi_id, expected_name):
        root = self.json('POST', DETAIL_URL, json={'poiId':poi_id, 'scene':'basic', 'head':{'lang':'01','cver':'1.0','extension':[]}})
        # Same template/module layout as crawler.extract_luoyang, without its batch CLI imports.
        modules=[m for t in root.get('templateList',[]) for m in t.get('moduleList',[])]
        by_type={m.get('moduleType'):m for m in modules}
        by_name={m.get('moduleName'):m for m in modules}
        basic = (by_type.get('basicInfo') or by_name.get('基础信息') or {}).get('poiBasicModule') or {}
        if basic.get('poiId') != poi_id:
            raise ValueError('poi_identity_mismatch')
        actual_name = basic.get('name') or basic.get('poiName')
        if actual_name and actual_name != expected_name:
            raise ValueError('poi_name_mismatch')
        selected = []
        # Keep the original module fields for transparent evidence; no ticket price inference.
        for kind, title in [('ticketAndAppointment','门票&预约信息'),('opentime','开放时间'),('notice','公告'),('preferential','优待政策')]:
            mod = by_type.get(kind) or by_name.get(title)
            if not mod:
                continue
            import json
            body = text(json.dumps(mod, ensure_ascii=False))
            selected.append({'theme':kind,'text':body[:5000]})
        return selected

    def comments(self, poi_id, limit=8):
        root = self.json('POST', COMMENT_URL, json={'arg':{'channelType':2,'collapseType':0,'commentTagId':0,
            'pageIndex':1,'pageSize':limit,'poiId':poi_id,'sourceType':1,'sortType':3,'starType':0},
            'head':{'lang':'01','cver':'1.0','extension':[]}})
        result = root.get('result')
        if not isinstance(result, dict) or not isinstance(result.get('items'), list):
            raise ValueError('invalid_comments_schema')
        output = []
        seen = set()
        for row in result['items'][:limit]:
            pid = (row.get('poiInfo') or {}).get('poiId')
            if pid not in (None, poi_id):
                raise ValueError('comment_poi_mismatch')
            cid = row.get('commentId')
            if cid is None or cid in seen or not text(row.get('content')):
                continue
            seen.add(cid)
            link = row.get('jumpH5Url')
            if not isinstance(link, str) or not link.startswith('https://'):
                link = sight_url(poi_id)
            output.append({'comment_id':cid,'text':text(row['content'])[:3500],'score':row.get('score'),
                'published_at':stamp(row.get('publishTime')), 'source_url':link})
        return output

    def weather(self, city, day):
        target = date.fromisoformat(day)
        delta = (target-datetime.now(CN).date()).days
        if delta < 0 or delta > 6:
            return {'state':'not_queried','reason':'outside_supported_7_day_forecast'}
        canonical = '洛阳市' if city in ('洛阳','洛阳市') else city
        geo = self.json('GET', GEO_URL, params={'name':canonical,'count':10,'language':'zh','format':'json','countryCode':'CN'})
        candidates = [r for r in geo.get('results',[]) if r.get('country_code')=='CN'
            and r.get('name') in (canonical,canonical.removesuffix('市'))
            and (canonical!='洛阳市' or r.get('admin1') in ('河南','河南省'))]
        if len(candidates) != 1:
            return {'state':'queried_no_evidence','reason':'weather_location_requires_clarification',
                'candidates':[{'name':r.get('name'),'region':r.get('admin1'),'country':r.get('country')} for r in geo.get('results',[])[:10]]}
        location = candidates[0]
        root = self.json('GET', WEATHER_URL, params={'latitude':location['latitude'],'longitude':location['longitude'],
            'daily':'temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code',
            'timezone':'Asia/Shanghai','forecast_days':7})
        daily = root.get('daily') or {}
        if day not in daily.get('time',[]):
            return {'state':'queried_no_evidence','reason':'forecast_date_missing'}
        i=daily['time'].index(day)
        fields={k:v[i] for k,v in daily.items() if isinstance(v,list) and len(v)>i}
        if not any(v is not None for k,v in fields.items() if k!='time'):
            return {'state':'queried_no_evidence','reason':'forecast_fields_missing'}
        return {'state':'queried_with_evidence','city':location['name'],'region':location.get('admin1'),
            'date':day,'fields':fields,'units':root.get('daily_units',{}),'source_url':'https://open-meteo.com/',
            'provider_updated_at':None,'scope':'city_forecast_not_attraction_live_conditions'}
