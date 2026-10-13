"""Narrow evidence guards over retrieved text, never authority/real-time inference."""
import re


def target_sources(question, sources):
    from service.ticket_service import matching_pois
    matches=matching_pois(question,[(s['poi_id'],s['name']) for s in sources])
    if len(matches)!=1:return []
    return [s for s in sources if s['poi_id']==matches[0][0]]


def evidence_guard(question, sources):
    """Known conflict pattern and scoped wheelchair documentation gap only."""
    relevant=target_sources(question,sources)
    if not relevant:return None
    if any(w in question for w in ('老人','老年','长辈','爸妈','父母','外国人','外籍','永久居留','国籍')):
        allowed=[];restricted=[]
        for source in relevant:
            if source['theme'] not in ('preferential','entry_policy'):continue
            for line in source['text'].splitlines():
                if re.search(r'老人\s*[：:]',line) and '免费' in line and re.search(
                    r'(?<!不)含\s*(?:中华人民共和国\s*)?外国人永久居留身份证',line):
                    allowed.append((source,line))
                if '免票' in line and re.search(r'(?:其他|其余).*(?:仅限|只限)中国公民',line):
                    restricted.append((source,line))
        if allowed and restricted:
            a,aq=allowed[0];b,bq=restricted[0]
            refs=[{'source_id':a['source_id'],'quote':aq},{'source_id':b['source_id'],'quote':bq}]
            raw={'status':'insufficient_evidence','statements':[
                {'text':f"采集资料的老人条目写为：{aq.lstrip('- ').strip()}",'evidence':[refs[0]]},
                {'text':f"同一景点的免票补充说明写为：{bq.strip()}",'evidence':[refs[1]]}],
                'limitations':'老人条目涉及外国人永久居留身份证，补充说明却限定其他免票仅限中国公民，两处口径存在冲突。仅凭本批资料无法确定老人免票的完整适用条件，请向景区官方核实；这些记载不是实时政策确认。',
                'limitations_evidence':refs}
            return raw,{'evidence_scope':'conflicting_policy','evidence_state':'queried_with_evidence',
                'evidence_issues':['foreign_residency_vs_citizenship_restriction']}
    if '轮椅' in question and not any('轮椅' in s['text'] for s in relevant):
        facilities=[s for s in relevant if s['theme']=='facilities']
        if facilities:
            # Cite every provided facilities entry; the claim is limited to these
            # entries, never all records or the availability at the actual POI.
            refs=[{'source_id':s['source_id'],'quote':s['text']} for s in facilities]
            entries=[line for s in facilities for line in s['text'].splitlines() if line.lstrip().startswith('-')]
            only_parking=bool(entries) and all(re.match(r'\s*-\s*停车场[：:]',line) for line in entries)
            name=facilities[0]['name']
            observation=(f'本次提供的{name}设施条目仅列出停车场，未提到轮椅设施。' if only_parking
                else f'本次提供的{name}设施条目未提到轮椅设施。')
            return {'status':'insufficient_evidence','statements':[{'text':observation,'evidence':refs}],
                'limitations':'因此无法确认是否提供轮椅设施；这些条目未提到不等于现场没有，请向景区核实。',
                'limitations_evidence':[]}, {'evidence_scope':'documentation_gap',
                'evidence_state':'queried_no_evidence','evidence_issues':['wheelchair_not_documented_in_provided_entries']}
    return None
