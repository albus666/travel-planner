"""Evidence-based Luoyang one-day drafts; no travel-time or live-data inference."""
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
import os
import re
from typing import TypedDict

import psycopg
from pydantic import BaseModel, Field, ConfigDict

from retrieval.search_chunks import require_database_url
from service.answer_service import validate_answer

POOL=('龙门石窟','天子驾六博物馆','洛阳博物馆','隋唐洛阳城应天门遗址','隋唐城遗址植物园','王城公园','从政坊游园')
PREFERENCES={'历史文化':('历史','文化','遗址','石窟','北魏','隋唐','古代'),
    '博物馆':('博物馆','文物','展馆','展区'), '园林':('园林','植物','花卉','公园','牡丹'),
    '自然风光':('园林','植物','湖','花卉','风景','景观'), '亲子':('亲子','儿童','小朋友','游乐'), '不限':()}
CATALOG_SQL='''SELECT poi_id,name,city,source_url,collected_at,verify_status
    FROM v2.attractions WHERE city=%s AND name=ANY(%s) ORDER BY poi_id'''


class PlanRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    request: str=Field('给我安排洛阳一日游',min_length=1,max_length=2000)
    city: str=Field('洛阳',max_length=30)
    days: int=Field(1,ge=1,le=7)
    trip_date: date | None=None
    departure: str | None=Field(None,max_length=100)
    companions: str | None=Field(None,max_length=200)
    preferences: list[str]=Field(default_factory=list,max_length=6)
    pace: str | None=Field(None,max_length=30)
    transport: str | None=Field(None,max_length=30)
    must_visit: list[str]=Field(default_factory=list,max_length=7)
    avoid: list[str]=Field(default_factory=list,max_length=7)


def planning_enabled():return os.environ.get('RAG_PLANNING_ENABLED','0').lower() in ('1','true','on')


def collect(payload, today=None):
    today=today or datetime.now(timezone(timedelta(hours=8))).date()
    q=payload['request'];slots={k:payload.get(k) for k in ('trip_date','departure','companions','preferences','pace','transport')}
    for field in ('departure','companions','pace','transport'):
        if isinstance(slots[field],str):slots[field]=slots[field].strip() or None
    slots['preferences']=[p.strip() for p in (slots['preferences'] or []) if p.strip()]
    if payload['city']!='洛阳' or payload['days']!=1 or re.search(r'两日|二日|两天|2天|三日|三天|3天|多日',q):
        return slots,[{'field':'scope','question':'目前只支持洛阳一日游，请确认城市和天数。'}]
    if not slots['trip_date']:
        match=re.search(r'\b20\d{2}-\d{2}-\d{2}\b',q)
        if match:
            try:slots['trip_date']=date.fromisoformat(match.group()).isoformat()
            except ValueError:pass
        elif '明天' in q:slots['trip_date']=(today+timedelta(days=1)).isoformat()
        elif '今天' in q:slots['trip_date']=today.isoformat()
    if not slots['departure']:
        match=re.search(r'从([^，。；]{1,40}?)(?:出发|开始)',q)
        if match:slots['departure']=match.group(1).strip()
    if not slots['companions']:
        kinds=[w for w in ('爸妈','父母','老人','孩子','儿童','一个人','独自','朋友','两位成人') if w in q and not re.search(r'不(?:带|和)'+w,q)]
        if kinds:slots['companions']='、'.join(kinds)
    if not slots['preferences']:
        prefs=[]
        if any(w in q for w in ('历史','文化')) and not re.search(r'不(?:想|要|喜欢)(?:历史|文化)',q):prefs.append('历史文化')
        for p in ('博物馆','园林','自然风光','亲子'):
            if p in q and not re.search(r'不(?:去|要|喜欢)'+p,q):prefs.append(p)
        if any(w in q for w in ('不限','没偏好','随意')):prefs=['不限']
        slots['preferences']=prefs
    aliases={'pace':{'轻松':('轻松','慢节奏','悠闲'),'适中':('适中',),'紧凑':('紧凑',)},
        'transport':{'公共交通':('公共交通','公交','地铁'),'出租车':('出租车','打车','网约车'),'自驾':('自驾','开车'),'步行':('步行',)}}
    for field,choices in aliases.items():
        text=slots[field] or q
        found=[key for key,words in choices.items() if any(w in text and not re.search(r'不(?:想|要|打算)?'+w,text) for w in words)]
        if len(found)==1:slots[field]=found[0]
        elif not slots[field] or slots[field] not in choices:slots[field]=None
    questions=[]
    labels={'trip_date':'哪一天游览？请给日期。','departure':'从哪里出发？请给车站或具体地点。',
        'companions':'同行有哪些人？例如独自、成年人、老人或孩子。','preferences':'偏好哪些内容？历史文化、博物馆、园林、自然风光、亲子或不限。',
        'pace':'希望轻松、适中还是紧凑？','transport':'使用公共交通、出租车、自驾还是步行？'}
    for k,label in labels.items():
        if not slots[k] or (k=='departure' and slots[k].strip() in ('家','酒店','住处','民宿','不知道')):questions.append({'field':k,'question':label})
    if slots['trip_date']:
        try:
            if date.fromisoformat(str(slots['trip_date']))<today:questions.append({'field':'trip_date','question':'日期已过去，请提供今天或未来的游览日期。'})
        except ValueError:questions.append({'field':'trip_date','question':'请提供有效的YYYY-MM-DD日期。'})
    if slots['preferences'] and not set(slots['preferences'])<=PREFERENCES.keys():questions.append({'field':'preferences','question':labels['preferences']})
    hard_text=q+' '+str(slots['companions'] or '')
    if re.search(r'(?:预算|总花费).{0,8}(?:\d|以内|不能超过)|轮椅|必须无障碍|不爬山|不能爬|\d+\s*(?:分钟|小时)',hard_text):
        questions.append({'field':'constraints','question':'本版不能核实预算、无障碍或精确耗时等硬约束；请先放宽这些要求为待确认项，或等待对应资料/服务。'})
    return slots,questions


def read_catalog():
    with psycopg.connect(require_database_url(),options='-c default_transaction_read_only=on -c statement_timeout=5000') as conn:
        return [{'poi_id':r[0],'name':r[1],'city':r[2],'source_url':r[3],
            'collected_at':r[4].isoformat() if r[4] else None,'verify_status':r[5]}
            for r in conn.execute(CATALOG_SQL,('洛阳',list(POOL))).fetchall()]


class PlanState(TypedDict,total=False):
    payload: dict
    slots: dict
    questions: list
    candidates: list
    evidence: list
    notes: list
    tasks: list
    trace: list
    result: dict


def create_plan_graph(catalog_tool,search_tool,sources_tool,*,today=None):
    from langgraph.graph import StateGraph,START,END
    def intake(s):
        slots,questions=collect(s['payload'],today)
        payload={**s['payload'],'must_visit':list(s['payload']['must_visit']),'avoid':list(s['payload']['avoid'])}
        q=payload['request']
        for name in POOL:
            if re.search(r'(?:必去|必须去|一定要去|只去)\s*'+re.escape(name),q) and name not in payload['must_visit']:payload['must_visit'].append(name)
            if re.search(r'(?:不去|不要去|排除)\s*'+re.escape(name),q) and name not in payload['avoid']:payload['avoid'].append(name)
        for match in re.finditer(r'(?:必去|必须去|一定要去|只去)([^，。；？]{1,50})',q):
            if not any(name in match.group(1) for name in POOL):questions.append({'field':'must_visit','question':'请明确必去景点全名；本版仅支持限定候选池，或请放宽必去要求。'})
        return {'payload':payload,'slots':slots,'questions':questions,'notes':[], 'tasks':[], 'trace':['collect']}
    def select(s):
        notes=[];tasks=[];questions=[]
        try:
            pool=catalog_tool();tasks.append({'tool':'catalog','state':'queried_with_evidence' if pool else 'queried_no_evidence'})
        except Exception:
            pool=[];notes.append('候选目录查询失败，不能据此认定没有景点。');tasks.append({'tool':'catalog','state':'query_failed'})
        if tasks[0]['state']=='queried_no_evidence':notes.append('本次限定候选目录未返回记录，不能生成有依据的草案。')
        required=s['payload']['must_visit'];avoid=set(s['payload']['avoid'])
        names={p['name'] for p in pool};limit=1 if s['slots']['transport']=='步行' else 2 if s['slots']['pace']=='轻松' else 3
        for name in required:
            if name not in names and tasks[0]['state']!='query_failed':questions.append({'field':'must_visit','question':f'必去景点“{name}”不在本版候选池或未查到，请核对完整名称或放宽要求；不能替换成相似景点。'})
            if name in avoid:questions.append({'field':'must_visit','question':f'“{name}”同时列为必去和排除，请选择保留哪项要求。'})
        for name in avoid:
            if name not in names and tasks[0]['state']!='query_failed':questions.append({'field':'avoid','question':f'排除景点“{name}”未匹配本版候选目录，请核对完整名称；不会自动展开简称或忽略排除要求。'})
        if len(set(required))>limit:questions.append({'field':'must_visit','question':f'必去数量超过当前节奏/交通的{limit}站上限，请减少景点或调整节奏/交通。'})
        if notes and (required or not pool):pool=[]
        else:
            pool=[p for p in pool if p['city']=='洛阳' and p['name'] in POOL and p['name'] not in avoid]
            if not pool and tasks[0]['state']=='queried_with_evidence':notes.append('当前候选已被范围或排除条件筛掉，没有可用候选。')
        return {'candidates':pool,'notes':notes,'tasks':tasks,'questions':questions,'trace':s['trace']+['select_candidates']}
    def retrieve(s):
        evidence=[];tasks=list(s['tasks']);notes=list(s['notes'])
        if not s['candidates']:tasks.append({'tool':'retrieve_chunks','state':'not_queried','reason':'no_eligible_candidate'})
        keys=tuple(k for p in s['slots']['preferences'] for k in PREFERENCES[p])
        for poi in s['candidates']:
            task={'tool':'retrieve_chunks','poi_id':poi['poi_id'],'name':poi['name'],'state':'queried_no_evidence','evidence_ids':[]}
            try:
                hits=search_tool(poi['name']+' '+' '.join(s['slots']['preferences'])+' 景点介绍 游览',top_k=5)
                hits=[h for h in hits if h['poi_id']==poi['poi_id'] and h['theme'] in ('overview','history_culture','visit_tips')]
                sources=sources_tool(hits);task['retrieved_count']=len(hits)
                options=[]
                for source in sources:
                    for line in source['text'].splitlines():
                        if line.startswith('【') or len(line.strip())<8:continue
                        for piece in re.split(r'(?<=[。；\n])',line):
                            piece=piece.strip()[:220]
                            if len(piece)<8:continue
                            score=sum(k in piece for k in keys)
                            if score or not keys or poi['name'] in s['payload']['must_visit']:
                                options.append((score,source,piece[:220]))
                if options:
                    score,source,quote=max(options,key=lambda v:v[0])
                    sid=f"P{poi['poi_id']}-S1";source={**source,'source_id':sid}
                    raw={'status':'answered','statements':[{'text':'采集资料记载：'+quote,
                        'evidence':[{'source_id':sid,'quote':quote}]}],'limitations':''}
                    checked=validate_answer(raw,[source],poi['name'])
                    if checked['citations']:
                        evidence.append({'poi':poi,'score':score,'basis':checked['answer'],'citations':checked['citations']})
                        task.update(state='queried_with_evidence',evidence_ids=[sid])
                if task['state']=='queried_no_evidence':notes.append(f"{poi['name']}：本次没有找到支持偏好或介绍的可引用证据。")
            except Exception:
                task['state']='query_failed';notes.append(f"{poi['name']}：检索或来源查询失败，未据此判定资料不存在。")
            tasks.append(task)
        return {'evidence':evidence,'tasks':tasks,'notes':notes,'trace':s['trace']+['retrieve_evidence']}
    def draft(s):
        required=list(dict.fromkeys(s['payload']['must_visit']));items=s.get('evidence',[]);notes=list(s['notes'])
        missing=[n for n in required if n not in {i['poi']['name'] for i in items}]
        if missing:notes.append('必去景点缺少可引用依据：'+'、'.join(missing)+'；不生成满足全部约束的行程。');items=[]
        limit=1 if s['slots']['transport']=='步行' else 2 if s['slots']['pace']=='轻松' else 3
        items=sorted(items,key=lambda i:(i['poi']['name'] not in required,
            i['poi']['name'] not in s['slots']['departure'],-i['score'],i['poi']['poi_id']))[:limit]
        stops=[{'order':n,'poi_id':i['poi']['poi_id'],'name':i['poi']['name'],'selection_basis':i['basis'],
            'citations':i['citations'],'sequence_status':'draft_unverified','arrival_time':None,'visit_duration_minutes':None}
            for n,i in enumerate(items,1)]
        warnings=['这是候选景点草案，不保证一天内可完成；顺序按必去、字面出发点名称与偏好组织，不是最优地理路线。',
            '跨景点路线、车程、实时交通与精确时间表均未核实。',
            '尚未确认指定日期的开放、预约、票价或活动状态；引用为采集资料，请核对采集时间及官方渠道。',
            '出发地已记录，未核实其位置及到景点的路程。']
        if any(w in s['slots']['companions'] for w in ('老人','爸妈','父母')):warnings.append('同行老人：步行量、台阶和无障碍设施尚未核实，不能保证适合老人。')
        if any(w in s['slots']['companions'] for w in ('孩子','儿童')):warnings.append('同行儿童：年龄适用条件与设施尚未核实，不能保证亲子适用。')
        result={'status':'draft' if stops else 'insufficient_evidence','slots':s['slots'],'questions':[],
            'stops':stops,'constraints':{'city':'洛阳','days':1,'max_stops':limit,'must_visit':required,'avoid':s['payload']['avoid']},
            'legs':[{'from':a['name'],'to':b['name'],'travel_minutes':None,'state':'not_queried'} for a,b in zip(stops,stops[1:])],
            'limitations':notes,'warnings':warnings,'tasks':s['tasks'],'citations':[c for i in stops for c in i['citations']]}
        return {'result':result,'trace':s['trace']+['draft_validate']}
    def finish(s):
        tasks=list(s.get('tasks',[])) or [{'tool':'catalog','state':'not_queried'}]
        if not any(t['tool']=='retrieve_chunks' for t in tasks):tasks.append({'tool':'retrieve_chunks','state':'not_queried','reason':'clarification_required'})
        result=s.get('result') or {'status':'needs_clarification','slots':s['slots'],'questions':s['questions'],
            'stops':[],'legs':[],'tasks':tasks,
            'citations':[],'warnings':[],'limitations':s.get('notes',[])}
        return {'result':{**result,'workflow':'luoyang_one_day_v1','node_trace':s['trace']+['finish']}}
    graph=StateGraph(PlanState)
    for name,node in (('collect',intake),('select_candidates',select),('retrieve_evidence',retrieve),('draft_validate',draft),('finish',finish)):graph.add_node(name,node)
    graph.add_edge(START,'collect');graph.add_conditional_edges('collect',lambda s:'finish' if s['questions'] else 'select_candidates',{'finish':'finish','select_candidates':'select_candidates'})
    graph.add_conditional_edges('select_candidates',lambda s:'finish' if s['questions'] else 'retrieve_evidence',{'finish':'finish','retrieve_evidence':'retrieve_evidence'})
    graph.add_edge('retrieve_evidence','draft_validate');graph.add_edge('draft_validate','finish');graph.add_edge('finish',END)
    return graph.compile()


@lru_cache(maxsize=1)
def plan_graph():
    from retrieval.search_chunks import search
    from service.answer_service import attach_sources
    return create_plan_graph(read_catalog,search,attach_sources)


def plan_trip(body:PlanRequest):return plan_graph().invoke({'payload':body.model_dump(mode='json')},config={'recursion_limit':12})['result']
