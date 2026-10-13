"""Narrow deterministic ticket snapshot lookup; fixed parameterized read-only SQL."""
from __future__ import annotations

from datetime import timedelta, timezone
import os

import psycopg
from service.intent_classifier import Store, classify_intent

from retrieval.search_chunks import require_database_url

CATALOG_SQL = 'SELECT poi_id, name FROM v2.attractions ORDER BY poi_id'
TICKET_SQL = '''SELECT a.poi_id, a.name, a.source_url, d.poi_id AS detail_poi_id,
    d.ticket_raw, d.detail_meta, d.collected_at, d.verify_status
    FROM v2.attractions a LEFT JOIN v2.poi_details d ON d.poi_id=a.poi_id
    WHERE a.poi_id=%s'''


def is_ticket_question(question):
    if not any(word in question for word in ('门票', '票价', '票钱')):
        return False
    if not any(word in question for word in ('多少钱', '价格', '票价', '售价', '原文', '资料', '记载', '费用', '怎么收费')):
        return False
    # Keep preferential and mixed non-price questions on the frozen vector path.
    if any(word in question for word in ('优惠', '免票', '半价', '路线', '历史', '介绍', '设施', '停车',
        '交通', '缆车', '索道', '轮椅', '讲解', '住宿', '餐饮', '开放', '开园', '闭园', '房态')):
        return False
    return True


def matching_pois(question, catalog):
    matches = []
    for poi_id, name in catalog:
        if not name or len(name) < 2:
            continue
        start = question.find(name)
        while start != -1:
            matches.append((start, start + len(name), poi_id, name))
            start = question.find(name, start + 1)
    # Ignore short names wholly inside a longer full name, not separate mentions.
    maximal = [m for m in matches if not any(other[0] <= m[0] and other[1] >= m[1]
                and other[1] - other[0] > m[1] - m[0] for other in matches)]
    targets = {m[2]: m[3] for m in maximal}
    return list(targets.items())


def resolve_poi(question, catalog):
    targets = matching_pois(question, catalog)
    if len(targets) == 1:
        return targets[0]
    return None


def format_ticket(row, question):
    poi_id, name, catalog_url, detail_id, raw, meta, collected, verified = row
    meta = meta if isinstance(meta, dict) else {}
    source_url = meta.get('source_url') or catalog_url
    timestamp = collected.astimezone(timezone(timedelta(hours=8))).isoformat() if collected else None
    structured = {'poi_id': poi_id, 'name': name, 'ticket_raw': raw,
        'detail_exists': detail_id is not None, 'source_table': 'v2.poi_details',
        'field': 'ticket_raw', 'source_url': source_url, 'source': meta.get('source'),
        'collected_at': timestamp, 'verify_status': verified}
    warnings = ['门票文案为采集快照，不代表实时售价；请核对采集时间和官方购票渠道。']
    if verified != 'verified':
        warnings.append('来源资料尚未经人工核验。')
    if not timestamp:
        warnings.append('采集时间未记录，无法判断资料时效。')
    base = {'route': 'sql_ticket', 'structured_data': structured, 'warnings': warnings,
            'retrieved_sources': [], 'citations': []}
    if detail_id is None or not isinstance(raw, str) or not raw.strip():
        reason = '没有详情记录' if detail_id is None else '门票原文字段为空'
        return {**base, 'status': 'insufficient_evidence',
            'answer': f'无法确认：{name}的资料中{reason}，不能据此推断免费或当前售价。'}
    citation = {'source_id': 'SQL1', 'chunk_id': None, 'poi_id': poi_id, 'name': name,
        'theme': 'ticket', 'theme_label': '门票原文', 'source_table': 'v2.poi_details',
        'field': 'ticket_raw', 'record_ref': f'v2.poi_details:{poi_id}:ticket_raw',
        'source_url': source_url, 'collected_at': timestamp, 'verify_status': verified, 'quotes': [raw]}
    base['citations'] = [citation]
    text = f'{name}的门票资料原文为：\n{raw}\n[SQL1：{name}／门票原文]'
    specific = any(word in question for word in ('成人', '儿童', '学生', '老人', '双人', '套票', '联票'))
    realtime = any(word in question for word in ('今天', '当前', '现在', '实时', '此刻', '今晚', '明天', '保证', '最新'))
    if realtime or specific:
        text = '无法确认所问的实时或特定票种准确售价；以下仅为采集资料，不作当前价格或票种对应保证。\n' + text
    text += '\n这是采集时的原始文案，未换算为统一数值；“起”不等于固定票价。'
    if timestamp:
        text += f'\n采集时间：{timestamp}。'
    return {**base, 'status': 'insufficient_evidence' if realtime or specific else 'answered', 'answer': text}


def try_ticket_answer(question, database_url=None, *, intent=None, entity_question=None):
    if os.environ.get('RAG_SQL_TICKET_ENABLED', '1').lower() in ('0', 'false', 'off'):
        return None
    if (intent or classify_intent(question)).store != Store.TICKET_RAW:
        return None
    url = require_database_url(database_url)
    with psycopg.connect(url, options='-c default_transaction_read_only=on -c statement_timeout=5000') as conn:
        catalog = conn.execute(CATALOG_SQL).fetchall()
        entity_q = entity_question if entity_question is not None else question
        matches = matching_pois(entity_q, catalog)
        target = resolve_poi(entity_q, catalog)
        if target is None:
            if len(matches) > 1:
                text = '当前门票查询一次只支持一个景点。识别到：' + '、'.join(dict.fromkeys(n for _,n in matches)) + '。请选择其中一个完整景点名称后查询。'
                reason = 'multiple_matches'
            else:
                text = '无法确认：现有目录未找到唯一匹配的景点记录。若已提供名称，请核对该名称；简称或名称缺失时请补充完整景点名称。未找到记录不代表免费。'
                reason = 'no_unique_match'
            return {'route': 'sql_ticket', 'status': 'insufficient_evidence',
                'answer': text,
                'citations': [], 'warnings': ['尚未定位景点，未推断门票价格。'],
                'retrieved_sources': [], 'structured_data': None, 'ticket_lookup_executed':False,
                'entity_resolution':{'status':reason,'matches':[{'poi_id':i,'name':n} for i,n in matches]}}
        row = conn.execute(TICKET_SQL, (target[0],)).fetchone()
    if row is None:
        return {'route': 'sql_ticket', 'status': 'insufficient_evidence',
                'answer': '无法确认：没有查到该景点的记录。', 'citations': [],
                'warnings': [], 'retrieved_sources': [], 'structured_data': None}
    return {**format_ticket(row, question), 'ticket_lookup_executed':True,
            'entity_resolution':{'status':'resolved','matches':[{'poi_id':target[0],'name':target[1]}]}}
