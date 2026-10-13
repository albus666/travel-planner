"""Offline prefix-normalization collision audit; never changes entity resolution."""
import argparse
import ast
import hashlib
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCENARIOS = {
    'geographic': ['河南省洛阳市', '河南省洛阳', '河南洛阳', '洛阳市', '洛阳'],
    'geographic_and_dynasty_experiment': ['河南省洛阳市', '河南省洛阳', '河南洛阳', '隋唐洛阳城', '洛阳市', '洛阳', '隋唐', '北魏', '东汉', '西汉'],
}

def normalize(name, prefixes):
    core = name
    removed = []
    while True:
        prefix = next((p for p in sorted(prefixes, key=len, reverse=True) if core.startswith(p) and len(core) - len(p) >= 2), None)
        if prefix is None:
            return core, removed
        removed.append(prefix)
        core = core[len(prefix):]

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=ROOT/'crawler/data/clean/attractions.jsonl')
    parser.add_argument('--output', type=Path, default=ROOT/'rag/eval/reports/entity_core_uniqueness.json')
    args = parser.parse_args()
    records = [json.loads(s)['attraction'] for s in args.input.read_text(encoding='utf8').splitlines() if s.strip()]
    assert len({r['poi_id'] for r in records}) == len(records)
    rows = [{'poi_id':r['poi_id'],'name':r['name'],'city':r.get('city')} for r in records]
    result = {'dataset_sha256':hashlib.sha256(args.input.read_bytes()).hexdigest(), 'poi_count':len(rows), 'scope':'offline lexical collision analysis; uniqueness does not establish user intent or safe automatic resolution', 'scenarios':{}}
    for scenario, prefixes in SCENARIOS.items():
        transformed = [{**r, 'core':normalize(r['name'],prefixes)[0], 'removed':normalize(r['name'],prefixes)[1]} for r in rows]
        by_core = defaultdict(list)
        for r in transformed: by_core[r['core']].append(r['poi_id'])
        changed = []
        for r in transformed:
            if not r['removed']: continue
            hits = [x for x in transformed if r['core'] in x['name'] or r['core'] in x['core']]
            changed.append({**r,'same_core_ids':by_core[r['core']], 'substring_candidates':[{'poi_id':x['poi_id'],'name':x['name']} for x in hits]})
        result['scenarios'][scenario] = {'prefixes':prefixes,'changed_count':len(changed),'unchanged_count':len(rows)-len(changed),'all_exact_unique_count':sum(len(by_core[r['core']])==1 for r in transformed),'changed_exact_unique_count':sum(len(r['same_core_ids'])==1 for r in changed),'changed_substring_unique_count':sum(len(r['substring_candidates'])==1 for r in changed),'changed_records':changed,'collisions':{k:v for k,v in by_core.items() if len(v)>1}}
    tree=ast.parse((ROOT/'rag/service/ticket_service.py').read_text(encoding='utf8'))
    functions=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ('matching_pois','resolve_poi')]
    namespace={};exec(compile(ast.Module(body=functions,type_ignores=[]),'<resolver_audit>','exec'),namespace)
    catalog=[(r['poi_id'],r['name']) for r in rows]
    result['probes']={q:{'substring_candidates':[r for r in rows if q in r['name']],'current_resolve_poi':namespace['resolve_poi'](q+'门票资料是什么？',catalog)} for q in ('龙门','应天门','应天门遗址','龙门海洋馆','龙门石窟')}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    lines=['# 景点核心词唯一性：离线统计','',f'数据：{len(rows)} 个 POI；数据 SHA-256：`{result["dataset_sha256"]}`。','', '规则预先列出；这是两个实验口径，不是语言学上已验证的核心词提取器。朝代前缀可能承载实体含义。唯一性只限当前数据快照，不能称安全解析率。','', '| 规则 | 改名数 | 未改名数 | 改名后核心词相等唯一 | 改名后子串候选唯一 |','|---|---:|---:|---:|---:|']
    for key,s in result['scenarios'].items():lines.append(f'| {key} | {s["changed_count"]} | {s["unchanged_count"]} | {s["changed_exact_unique_count"]} | {s["changed_substring_unique_count"]} |')
    lines+=['','未改名的 POI 不能计为短名解析的新增收益。核心词相等唯一与作为其他名字的子串唯一不是同一指标。','', '## 当前解析器实测','', '| 输入片段 | 库名子串候选数 | 当前完整名称解析结果 |','|---|---:|---|']
    for q,p in result['probes'].items():lines.append(f'| {q} | {len(p["substring_candidates"])} | {p["current_resolve_poi"]} |')
    for key,s in result['scenarios'].items():
        lines+=['',f'## {key}','', '前缀：'+ '、'.join(s['prefixes'])+'。仅匹配开头、优先最长、重复去除、至少保留两字。','', '| 原名 | 核心词 | 子串候选数 |','|---|---|---:|']
        lines += [f'| {r["name"]} | {r["core"]} | {len(r["substring_candidates"])} |' for r in s['changed_records']]
    lines+=['','## 结论边界','','当前 resolve_poi 是完整库名包含匹配加重叠消除，不是短名规范化匹配。龙门海洋馆的完整问法可以精确解析，不能将“龙门”歧义推导为所有包含龙门的完整问法都歧义。别名若设计为完整实体片段匹配并保留全名优先，并不必然屏蔽其他 POI；无条件子串替换才有该风险。','','/plan 的七景点能力池不等于全量实体目录；未来澄清应注明候选是否被规划支持。单个地域内唯一、词法唯一、用户意图明确是三个不同判断。此次仅分析，未修改路由/解析，未修 P05-01/P06-01。']
    args.output.with_suffix('.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
    print(json.dumps({k:{a:b for a,b in s.items() if a not in ('changed_records','collisions','prefixes')} for k,s in result['scenarios'].items()}))
    print(json.dumps({q:{'substring_count':len(p['substring_candidates']),'resolved':p['current_resolve_poi']} for q,p in result['probes'].items()},ensure_ascii=True))

if __name__=='__main__':main()
